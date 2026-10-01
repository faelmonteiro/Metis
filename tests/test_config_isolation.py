"""
Isolamento do DEFAULT_CONFIG.

`load_config` devolvia `dict(DEFAULT_CONFIG)`: um shallow copy. O chamador recebia
o mesmo dicionário `preferences` e as mesmas listas `custom_servers` /
`removed_servers` do default do processo, então um `append` de servidor ou uma
preferência salva num config ausente voltava no config "limpo" seguinte — dentro
da mesma sessão.
"""
import json

from agente.models import storage


def _config_inexistente(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "CONFIG_FILE", tmp_path / "config_models.json")
    return tmp_path / "config_models.json"


def test_config_ausente_nao_compartilha_listas_e_dicts(tmp_path, monkeypatch):
    _config_inexistente(tmp_path, monkeypatch)

    cfg = storage.load_config(force_reload=True)
    cfg["custom_servers"].append({"id": "fantasma"})
    cfg["removed_servers"].append("fantasma")
    cfg["preferences"]["active_models"] = {"fantasma": "modelo-fantasma"}

    outro = storage.load_config(force_reload=True)

    assert outro is not cfg
    assert outro["custom_servers"] == []
    assert "fantasma" not in json.dumps(outro, ensure_ascii=False)


def test_config_corrompido_nao_contamina_o_default(tmp_path, monkeypatch):
    cfg_path = _config_inexistente(tmp_path, monkeypatch)
    cfg_path.write_text("{isto nao e json", encoding="utf-8")

    cfg = storage.load_config(force_reload=True)
    cfg["custom_servers"].append({"id": "fantasma"})

    outro = storage.load_config(force_reload=True)
    assert "fantasma" not in json.dumps(outro, ensure_ascii=False)


def test_default_config_intacto_apos_todas_as_cargas(tmp_path, monkeypatch):
    """Guarda final: o default do processo não pode ter acumulado nada."""
    antes = json.dumps(storage.DEFAULT_CONFIG, ensure_ascii=False, sort_keys=True)

    _config_inexistente(tmp_path, monkeypatch)
    storage.load_config(force_reload=True)["custom_servers"].append({"id": "fantasma"})

    cfg_path = storage.CONFIG_FILE
    cfg_path.write_text("{quebrado", encoding="utf-8")
    storage.load_config(force_reload=True)["custom_servers"].append({"id": "outro"})

    depois = json.dumps(storage.DEFAULT_CONFIG, ensure_ascii=False, sort_keys=True)
    assert antes == depois