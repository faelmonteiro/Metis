"""`PassosContinuacaoDialog`: o que o usuario digita vira quantos passos.

O worker le `dialogo.passos` depois do `exec()`, e o valor errado nao aparece
como bug: um `None` onde se esperava um inteiro simplesmente encerra a tarefa,
e o usuario viu o agente parar no meio sem ter pedido. Por isso o contrato de
cada entrada esta testado aqui, e nao so o "funciona".

O dialogo tambem nao esta no `DIALOGOS` do smoke test: aquele registro exige
baseline em `gui_dialogos/`, e um baseline novo so poderia ser gerado nesta
maquina — a geometria impressa sai diferente em cada tela.
"""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_APP = None


def _app():
    global _APP
    from PyQt6.QtWidgets import QApplication
    _APP = QApplication.instance() or QApplication([])
    return _APP


def _dialogo(**kw):
    from agente.gui.dialogs.steps import PassosContinuacaoDialog
    return PassosContinuacaoDialog(**kw)


class TestLeituraDaResposta(unittest.TestCase):
    def setUp(self):
        _app()

    def _responde(self, texto, **kw):
        d = _dialogo(**kw)
        d.txt_resposta.setText(texto)
        d.aceitar()
        return d

    # o atalho ---------------------------------------------------------------

    def test_o_atalho_s_vale_tres_passos(self):
        self.assertEqual(self._responde("s").passos, 3)

    def test_o_atalho_s_aceita_caixa_alta(self):
        """O campo vem com `s` selecionado; digitar `S` e o mesmo gesto."""
        self.assertEqual(self._responde("S").passos, 3)

    def test_o_atalho_s_ignora_espaco(self):
        self.assertEqual(self._responde(" s ").passos, 3)

    # numero exato ------------------------------------------------------------

    def test_numero_vira_o_limite_da_rodada(self):
        self.assertEqual(self._responde("12").passos, 12)

    def test_numero_com_espaco_no_canto(self):
        self.assertEqual(self._responde("  7 ").passos, 7)

    # parar -------------------------------------------------------------------

    def test_n_para(self):
        self.assertIsNone(self._responde("n").passos)

    def test_botao_parar_para(self):
        d = _dialogo()
        d.btn_parar.click()
        self.assertIsNone(d.passos)

    def test_botao_de_atalho_entrega_o_padrao(self):
        d = _dialogo()
        d.btn_mais.click()
        self.assertEqual(d.passos, 3)

    # entrada invalida --------------------------------------------------------

    def test_texto_sem_numero_nao_encerra_a_tarefa(self):
        """Fechar com entrada invalida devolveria `None`, lido como "parar".

        O usuario acharia que pediu mais passos e a tarefa acabaria ali — sem
        nenhum aviso de que foi isso.
        """
        d = self._responde("abc")
        self.assertIsNone(d.passos)
        self.assertTrue(d.lbl_erro.text())

    def test_zero_e_negativo_sao_recusados(self):
        for texto in ("0", "-2"):
            with self.subTest(texto=texto):
                d = self._responde(texto)
                self.assertTrue(d.lbl_erro.text())

    def test_o_campo_continua_editavel_apos_o_erro(self):
        """Fechar o dialogo no erro seria o mesmo que desistir."""
        d = self._responde("abc")
        self.assertFalse(d.lbl_erro.isHidden())
        self.assertFalse(d.result(), "o dialogo fechou sozinho, e o worker le None")
        d.txt_resposta.setText("4")
        d.aceitar()
        self.assertEqual(d.passos, 4)

    def test_o_erro_desaparece_quando_o_valor_vale(self):
        d = self._responde("abc")
        d.txt_resposta.setText("4")
        d.aceitar()
        self.assertEqual(d.passos, 4)

    # o texto que explica a regra ---------------------------------------------

    def test_a_regra_dos_atalhos_esta_na_tela(self):
        """`s`, numero e `n` so helps se o usuario ve que existem."""
        from PyQt6.QtWidgets import QLabel
        textos = " ".join(l.text() for l in _dialogo().findChildren(QLabel))
        self.assertIn("= +3 passos", textos)
        self.assertIn("passos exatos", textos)
        self.assertIn("= parar", textos)

    def test_o_texto_muda_com_a_ultima_rodada(self):
        """Na ultima, o usuario precisa saber que e a ultima."""
        primeira = _dialogo(rodadas_restantes=3).lbl_sub.text()
        ultima = _dialogo(rodadas_restantes=1).lbl_sub.text()
        self.assertIn("ate 3 vezes", primeira)
        self.assertIn("ultima continuacao", ultima)

    def test_o_singular_do_passo(self):
        self.assertIn("limite de 1 passo ", _dialogo(passos_usados=1).lbl_sub.text())


if __name__ == "__main__":
    unittest.main()
