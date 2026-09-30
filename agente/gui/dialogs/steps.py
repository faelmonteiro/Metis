"""Dialogo que pergunta quantos passos extras o agente deve executar.

Aparece quando o servico marca `max_iterations` como esgotado: o agente ainda
quer continuar working, mas o contrato da chamada acabou. A resposta volta em
`dialogo.passos` — um inteiro positivo para continuar, `None` para parar.

O campo vem com "s" selecionado de proposito: e a resposta que quase sempre
serve (+3 passos), e o usuario que quiser outra coisa digita por cima sem
precisar apagar nada.
"""

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QFrame,
)

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from agente.gui.dialogs.common import _constrain_dialog_to_parent
from agente.gui.theme_bridge import build_dynamic_qss

# O que "s" significa. Vive aqui porque o rotulo do dialogo e a docstring
# precisam concordar: se o atalho mudar em um so dos dois, o usuario digita "s"
# e recebe outra coisa sem nenhum aviso.
PASSOS_DO_ATALHO_S = 3

# Atalho que o usuario digita para parar, alem do botao "Parar".
ATALHO_DE_PARAR = "n"


class PassosContinuacaoDialog(QDialog):
    def __init__(self, parent=None, passos_usados: int = 5, rodadas_restantes: int = 3):
        super().__init__(parent)
        self.setWindowTitle("Metis • Continuar a tarefa")
        _constrain_dialog_to_parent(self, 470, 320, parent)
        self.setStyleSheet(build_dynamic_qss())

        # `None` = parar. O worker le isto depois do `exec()`.
        self.passos = None

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        root.addLayout(self._build_header(passos_usados, rodadas_restantes))
        root.addLayout(self._build_campo())
        root.addLayout(self._build_atalhos())
        root.addLayout(self._build_footer())

    def _build_header(self, passos_usados, rodadas_restantes):
        h = QHBoxLayout()
        icone = QLabel("⚡")
        icone.setFont(QFont("Sans Serif", 16))
        icone.setStyleSheet("background: transparent;")
        h.addWidget(icone)

        textos = QVBoxLayout()
        textos.setSpacing(2)

        titulo = QLabel("A TAREFA AINDA NÃO TERMINOU")
        titulo.setFont(QFont("Sans Serif", 13, QFont.Weight.Bold))
        titulo.setStyleSheet("color: #fad094; background: transparent;")
        textos.addWidget(titulo)

        self.lbl_sub = QLabel(self._texto_de_rodadas(passos_usados, rodadas_restantes))
        self.lbl_sub.setFont(QFont("Sans Serif", 9))
        self.lbl_sub.setStyleSheet("color: #94a3b8; background: transparent;")
        self.lbl_sub.setWordWrap(True)
        textos.addWidget(self.lbl_sub)

        h.addLayout(textos)
        h.addStretch()
        return h

    def _texto_de_rodadas(self, passos_usados, rodadas_restantes):
        plural = "passo" if passos_usados == 1 else "passos"
        base = f"O agente parou no limite de {passos_usados} {plural} desta rodada."
        if rodadas_restantes <= 1:
            return f"{base} Esta e a ultima continuacao desta tarefa."
        if rodadas_restantes == 2:
            return f"{base} Voce pode continuar mais {rodadas_restantes} vez."
        return f"{base} Voce pode continuar ate {rodadas_restantes} vezes."

    def _build_campo(self):
        # O cartao precisa ficar em `self`: ele e criado sem pai, e o wrapper
        # do Python manda no tempo de vida do objeto C++. Um local aqui seria
        # liberado na saida do metodo e o `addLayout` receberia um ponteiro
        # morto — que e o que o PyQt6 transforma em RuntimeError.
        self.cartao_resposta = QFrame()
        self.cartao_resposta.setProperty("class", "ApiCard")
        layout = QVBoxLayout(self.cartao_resposta)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        self.lbl_pergunta = QLabel("Quantos passos extras devo executar?")
        self.lbl_pergunta.setFont(QFont("Sans Serif", 9, QFont.Weight.Bold))
        self.lbl_pergunta.setStyleSheet("color: #cbd5e1; background: transparent;")
        layout.addWidget(self.lbl_pergunta)

        self.txt_resposta = QLineEdit("s")
        self.txt_resposta.setPlaceholderText("s ou um numero")
        self.txt_resposta.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # "s" ja pronto: o Enter sem mexer em nada e o caminho comum, e quem
        # quer outro valor digita por cima do que esta selecionado.
        self.txt_resposta.selectAll()
        self.txt_resposta.returnPressed.connect(self.aceitar)
        layout.addWidget(self.txt_resposta)

        self.lbl_erro = QLabel("")
        self.lbl_erro.setFont(QFont("Sans Serif", 8))
        self.lbl_erro.setStyleSheet("color: #ef4444; background: transparent;")
        self.lbl_erro.setWordWrap(True)
        self.lbl_erro.setVisible(False)
        layout.addWidget(self.lbl_erro)

        return layout

    def _build_atalhos(self):
        """A regra de leitura do campo, escrita uma vez e exibida uma vez."""
        linha = QHBoxLayout()
        texto = QLabel(
            f"<b>s</b> = +{PASSOS_DO_ATALHO_S} passos &nbsp;•&nbsp; "
            f"<b>numero</b> = passos exatos &nbsp;•&nbsp; "
            f"<b>{ATALHO_DE_PARAR}</b> = parar"
        )
        texto.setFont(QFont("Sans Serif", 9))
        texto.setStyleSheet("color: #64748b; background: transparent;")
        texto.setWordWrap(True)
        linha.addWidget(texto)
        return linha

    def _build_footer(self):
        linha = QHBoxLayout()

        self.btn_mais = QPushButton(f"+{PASSOS_DO_ATALHO_S} passos")
        self.btn_mais.setProperty("class", "SecondaryBtn")
        self.btn_mais.clicked.connect(self._aceitar_com(PASSOS_DO_ATALHO_S))
        linha.addWidget(self.btn_mais)

        linha.addStretch()

        self.btn_parar = QPushButton("Parar")
        self.btn_parar.setProperty("class", "DangerBtn")
        self.btn_parar.clicked.connect(self.parar)
        linha.addWidget(self.btn_parar)

        self.btn_continuar = QPushButton("Continuar")
        self.btn_continuar.setProperty("class", "PrimaryBtn")
        self.btn_continuar.setDefault(True)
        self.btn_continuar.clicked.connect(self.aceitar)
        linha.addWidget(self.btn_continuar)

        return linha

    def _aceitar_com(self, passos):
        return lambda: self._fecha_com(passos)

    def _fecha_com(self, passos):
        self.passos = passos
        self.accept()

    def aceitar(self):
        """Le o campo. Entrada invalida nao fecha o dialogo.

        Fechar com entrada invalida devolveria `None` ao worker, que leria como
        "parar" — o usuario achou que pediu mais passos e a tarefa foi abortada
        sem ele ter pedido.
        """
        bruto = self.txt_resposta.text().strip().lower()

        if bruto == ATALHO_DE_PARAR:
            self._fecha_com(None)
            return

        if bruto == "s":
            self._fecha_com(PASSOS_DO_ATALHO_S)
            return

        try:
            passos = int(bruto)
        except ValueError:
            passos = 0

        if passos <= 0:
            self._mostra_erro("Digite 's', um numero positivo ou 'n' para parar.")
            self.txt_resposta.setFocus()
            self.txt_resposta.selectAll()
            return

        self._fecha_com(passos)

    def parar(self):
        self._fecha_com(None)

    def _mostra_erro(self, mensagem):
        self.lbl_erro.setText(mensagem)
        self.lbl_erro.setVisible(True)
