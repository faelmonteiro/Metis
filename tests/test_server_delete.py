"""
Exclusão de servidores de IA — persistência real no arquivo.

Estes testes existem porque a exclusão "funcionava" na tela mas deixava sobras
em disco: a entrada sumia da lista em memória, `active_models`/`.env` mantinham
referências pendentes e as cópias legadas do config nunca eram atualizadas.
"""
import json

import pytest

from agente.models import (
    add_custom_server,
    get_custom_server,
    get_custom_servers,
    load_config,
    remove_custom_server,
    save_env_var,
    get_env_var,
    save_config,
)
from agente.models.custom import get_server_models
from agente.models.preferences import ENV_FILE


@pytest.fixture(autouse=True)
def _config_isolado():
    """Restaura config_models.json e .env ao estado original de cada teste."""
    cfg_path = ENV_FILE.parent / "config_models.json"
    cfg_origem = cfg_path.read_bytes() if cfg_path.exists() else None
    env_origem = ENV_FILE.read_bytes() if ENV_FILE.exists() else None

    yield

    if cfg_origem is None:
        cfg_path.unlink(missing_ok=True)
    else:
        cfg_path.write_bytes(cfg_origem)
    if env_origem is None:
        ENV_FILE.unlink(missing_ok=True)
    else:
        ENV_FILE.write_bytes(env_origem)
    load_config(force_reload=True)


def _sem_servidor(server_id: str) -> bool:
    """Relê o arquivo do zero e confirma que o servidor não está mais lá."""
    cfg = json.loads((ENV_FILE.parent / "config_models.json").read_text(encoding="utf-8"))
    return not any(
        s.get("id", "").lower() == server_id.lower()
        or s.get("nome", "").lower() == server_id.lower()
        for s in cfg.get("custom_servers", [])
    )


def test_exclusao_grava_no_arquivo():
    """A exclusão precisa chegar ao config_models.json, não só à memória."""
    add_custom_server(
        nome="DeepSeek",
        base_url="https://api.deepseek.com/v1/chat/completions",
        modelo_padrao="deepseek-chat",
    )
    assert get_custom_server("deepseek") is not None

    assert remove_custom_server("deepseek") is True

    # Relê do disco, ignorando qualquer cache em memória.
    assert _sem_servidor("deepseek")
    assert get_custom_server("deepseek") is None


def test_exclusao_por_nome_funciona():
    add_custom_server(nome="Together", base_url="https://api.together.xyz/v1")
    assert remove_custom_server("Together") is True
    assert _sem_servidor("together")


def test_exclusao_de_id_inexistente_retorna_false():
    """Sem isso a GUI confirmava exclusões que nunca aconteceram."""
    assert remove_custom_server("nao-existe-123") is False
    assert len(get_custom_servers()) >= 1


def test_exclusao_limpa_referencias_pendentes():
    """active_models e active_provider não podem continuar apontando ao servidor morto."""
    add_custom_server(nome="Fireworks", base_url="https://api.fireworks.ai/v1")
    save_env_var("FIREWORKS_API_KEY", "chave-secreta")
    save_env_var("FIREWORKS_MODEL", "llama-v3")

    cfg = load_config()
    prefs = cfg.setdefault("preferences", {})
    prefs.setdefault("active_models", {})["fireworks"] = "llama-v3"
    prefs["last_active_provider"] = "custom:fireworks"
    prefs["active_model"] = "llama-v3"
    prefs["last_active_model"] = "llama-v3"
    cfg["active_provider"] = "fireworks"
    cfg["active_model"] = "llama-v3"
    save_config(cfg)

    assert remove_custom_server("fireworks") is True

    cfg = load_config(force_reload=True)
    assert "fireworks" not in cfg["preferences"]["active_models"]
    assert cfg["active_provider"] != "fireworks"
    assert cfg["active_model"] != "llama-v3"
    assert cfg["preferences"]["last_active_provider"] != "custom:fireworks"
    assert cfg["preferences"]["active_model"] != "llama-v3"


def test_exclusao_remove_credenciais_do_env():
    """A chave de API do servidor excluído não pode ficar órfã no .env."""
    add_custom_server(
        nome="GroqAlt",
        base_url="https://api.groq.com/openai/v1",
        api_key="gk-super-secreta",
    )
    assert get_env_var("GROQALT_API_KEY") == "gk-super-secreta"

    assert remove_custom_server("groqalt") is True

    assert get_env_var("GROQALT_API_KEY") == ""
    assert get_env_var("GROQALT_MODEL") == ""
    assert "GROQALT_API_KEY" not in ENV_FILE.read_text(encoding="utf-8")


def test_nao_apaga_servidores_iguais_ao_apagar_outro():
    """Regressão: purga por nome/id não pode varrer servidores vizinhos."""
    add_custom_server(nome="ServidorA", base_url="https://a.example/v1")
    add_custom_server(nome="ServidorB", base_url="https://b.example/v1")

    assert remove_custom_server("servidora") is True

    restantes = {s["id"] for s in get_custom_servers()}
    assert "servidorb" in restantes
    assert "servidora" not in restantes


def test_readd_nao_ressuscita_modelos_do_servidor_removido():
    """Recriar com o mesmo nome começa limpo, sem herdar a lista antiga."""
    add_custom_server(
        nome="Antigo",
        base_url="https://antigo.example/v1",
        modelos_iniciais=["modelo-velho-1", "modelo-velho-2"],
    )
    assert remove_custom_server("antigo") is True

    novo = add_custom_server(
        nome="Antigo",
        base_url="https://novo.example/v1",
        modelos_iniciais=["modelo-novo"],
    )

    assert novo["modelos"] == ["modelo-novo"]
    assert get_server_models("antigo") == ["modelo-novo"]


def test_add_com_id_de_provedor_builtin_e_rejeitado():
    """'g4f' como nome customizado mudaria o significado da entrada silenciosamente."""
    from agente.models.custom import BUILTIN_PROVIDER_IDS

    with pytest.raises(ValueError, match="provedor embutido"):
        add_custom_server(nome="G4F", base_url="https://exemplo.invalid/v1")


def test_cadastro_rejeitado_nao_deixa_segredo_no_env():
    """O .env era gravado antes da validação: recusa deixava credencial órfã."""
    with pytest.raises(ValueError):
        add_custom_server(
            nome="G4F",
            base_url="https://exemplo.invalid/v1",
            api_key="segredo-que-nao-deveria-existir",
        )

    texto_env = ENV_FILE.read_text(encoding="utf-8") if ENV_FILE.exists() else ""
    assert "segredo-que-nao-deveria-existir" not in texto_env
    assert get_env_var("G4F_API_KEY") == ""


def test_exclusao_permanente_nao_deixa_marca_em_removed_servers():
    """Excluir de vez não pode marcar o servidor como 'removido': some da lista."""
    from agente.models.preferences import get_removed_servers, remove_server
    from agente.providers_manager import remover_servidor_provedor

    add_custom_server(nome="Marca", base_url="https://marca.example/v1")
    remove_server("marca")
    assert "marca" in get_removed_servers()

    assert remover_servidor_provedor("marca") is True

    cfg = load_config(force_reload=True)
    persistidos = {r.get("id", "").lower() for r in cfg.get("removed_servers", [])}
    assert "marca" not in persistidos
    assert "marca" not in get_removed_servers()


def test_recadastrar_servidor_antigo_apaga_marca_de_removido():
    """Recriar o mesmo nome precisa destravar o provedor para a sessão seguinte."""
    from agente.models.preferences import is_server_removed, remove_server

    add_custom_server(nome="Volta", base_url="https://volta.example/v1")
    remove_server("volta")
    assert is_server_removed("volta") is True

    add_custom_server(nome="Volta", base_url="https://volta2.example/v1")

    assert is_server_removed("volta") is False
    cfg = load_config(force_reload=True)
    assert "volta" not in {r.get("id", "").lower() for r in cfg.get("removed_servers", [])}


def test_exclusao_de_builtin_reporta_se_removeu():
    """remover_servidor_provedor retornava True mesmo sem ter removido nada."""
    from agente.providers_manager import remover_servidor_provedor

    assert remover_servidor_provedor("provedor-que-nao-existe") is False
