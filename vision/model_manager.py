"""
Gerenciador de Modelos e Provedores do Metis / ScreenAI.
Permite carregar, salvar, adicionar, editar e remover modelos por categoria com persistência em JSON.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional

DEFAULT_CONFIG_PATH = Path(__file__).parent / "config_models.json"
METIS_CONFIG_PATHS = [
    Path.home() / "Metis" / "config_models.json",
    Path.home() / ".ZSH" / "ai" / "config_models.json"
]

# Nota de arquitetura: A chave 'builtin_models' armazena tanto modelos nativos quanto
# modelos adicionados/customizados pelo usuário para garantir compatibilidade.
DEFAULT_MODELS_DATA = {
    "schema_version": 1,
    "builtin_models": {
        "NVIDIA": [
            "meta/llama-3.2-11b-vision-instruct",
            "meta/llama-3.2-90b-vision-instruct",
            "deepseek-ai/deepseek-r1",
            "meta/llama-3.1-70b-instruct"
        ],
        "Gemini": [
            "gemini-2.0-flash",
            "gemini-1.5-flash",
            "gemini-1.5-pro",
            "gemini-2.0-flash-lite-preview-02-05"
        ],
        "OpenRouter": [
            "google/gemini-2.0-flash-exp:free",
            "openrouter/free",
            "stealth/ox-alpha"
        ],
        "Ollama": [
            "llama3.2-vision:11b",
            "qwen3.5:9b",
            "qwen3.5:4b",
            "llama3.2:3b",
            "qwen2.5-coder:7b"
        ],
        "Groq": [
            "openai/gpt-oss-120b"
        ],
        "G4F": [
            "gpt-4o-mini",
            "gpt-4o",
            "deepseek-r1",
            "llama-3.3-70b",
            "qwen-2.5-coder-32b"
        ]
    },
    "active_provider": "nvidia",
    "active_model": "meta/llama-3.2-11b-vision-instruct"
}

def get_config_path() -> Path:
    """Retorna o caminho do arquivo de configuração ativo (sincronizado com o Metis)."""
    # 1. Procura primeiro no diretório raiz do Metis (~/Metis/config_models.json)
    root_config = Path(__file__).resolve().parent.parent / "config_models.json"
    if root_config.exists():
        return root_config
    
    for mp in METIS_CONFIG_PATHS:
        if mp.exists():
            return mp

    return DEFAULT_CONFIG_PATH

def ensure_config_exists() -> Path:
    """Garante que o arquivo de configuração existe, inicializando ou mesclando se necessário."""
    target_path = get_config_path()
    if not target_path.exists():
        save_models_config(DEFAULT_MODELS_DATA)
    return target_path

_CONFIG_CACHE: Optional[dict] = None

def load_models_config(force_reload: bool = False) -> dict:
    """Carrega o JSON de modelos com cache in-memory para alto desempenho."""
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None and not force_reload:
        return _CONFIG_CACHE
    p = ensure_config_exists()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if "builtin_models" not in data:
            data["builtin_models"] = DEFAULT_MODELS_DATA["builtin_models"]
        _CONFIG_CACHE = data
        return data
    except Exception:
        _CONFIG_CACHE = dict(DEFAULT_MODELS_DATA)
        return _CONFIG_CACHE

def save_models_config(data: dict):
    """Salva a configuração no arquivo JSON compartilhado e atualiza cache."""
    global _CONFIG_CACHE
    p = get_config_path()
    
    # Preserva chaves existentes no JSON do Metis (como custom_servers, removed_models, preferences)
    if p.exists():
        try:
            existing = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(existing, dict):
                for k, v in existing.items():
                    if k not in data:
                        data[k] = v
        except Exception:
            pass

    _CONFIG_CACHE = data
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

def get_providers() -> List[str]:
    """Retorna a lista de provedores/categorias disponíveis (incluindo servidores customizados)."""
    cfg = load_models_config(force_reload=True)
    provs = list(cfg.get("builtin_models", {}).keys())
    for srv in cfg.get("custom_servers", []):
        nome = srv.get("nome")
        if nome and nome not in provs:
            provs.append(nome)
    return provs

def get_models_for_provider(provider: str) -> List[str]:
    """Retorna a lista de modelos de uma categoria específica."""
    cfg = load_models_config(force_reload=True)
    builtin = cfg.get("builtin_models", {})
    for k, v in builtin.items():
        if k.lower() == provider.lower():
            return v
    
    for srv in cfg.get("custom_servers", []):
        if srv.get("nome", "").lower() == provider.lower() or srv.get("id", "").lower() == provider.lower():
            return srv.get("modelos", [])
            
    return []

def add_model_to_provider(provider: str, model_id: str) -> bool:
    """Adiciona um novo modelo a uma categoria."""
    model_id = model_id.strip()
    if not model_id:
        return False
    cfg = load_models_config(force_reload=True)
    if "builtin_models" not in cfg:
        cfg["builtin_models"] = {}
        
    matched_prov = None
    for k in cfg["builtin_models"].keys():
        if k.lower() == provider.lower():
            matched_prov = k
            break
            
    if not matched_prov:
        matched_prov = provider
        cfg["builtin_models"][matched_prov] = []
        
    if model_id not in cfg["builtin_models"][matched_prov]:
        cfg["builtin_models"][matched_prov].append(model_id)
        save_models_config(cfg)
        return True
    return False

def remove_model_from_provider(provider: str, model_id: str) -> bool:
    """Remove um modelo de uma categoria."""
    cfg = load_models_config(force_reload=True)
    for k, mlist in cfg.get("builtin_models", {}).items():
        if k.lower() == provider.lower() and model_id in mlist:
            mlist.remove(model_id)
            save_models_config(cfg)
            return True
    return False

def edit_model_in_provider(provider: str, old_model_id: str, new_model_id: str) -> bool:
    """Edita um modelo existente."""
    new_model_id = new_model_id.strip()
    if not new_model_id:
        return False
    cfg = load_models_config(force_reload=True)
    for k, mlist in cfg.get("builtin_models", {}).items():
        if k.lower() == provider.lower() and old_model_id in mlist:
            idx = mlist.index(old_model_id)
            mlist[idx] = new_model_id
            save_models_config(cfg)
            return True
    return False

def get_active_model() -> Tuple[str, str]:
    """Retorna (provedor_ativo, modelo_ativo)."""
    cfg = load_models_config()
    prov = cfg.get("active_provider", "nvidia")
    mod = cfg.get("active_model", "meta/llama-3.2-11b-vision-instruct")
    return prov, mod

def set_active_model(provider: str, model_id: str):
    """Salva o modelo ativo selecionado."""
    cfg = load_models_config(force_reload=True)
    cfg["active_provider"] = provider.lower()
    cfg["active_model"] = model_id
    save_models_config(cfg)

def get_user_setting(key: str, default=None):
    """Obtém uma preferência persistida do usuário."""
    cfg = load_models_config()
    return cfg.get("user_settings", {}).get(key, default)

def set_user_setting(key: str, value):
    """Salva uma preferência do usuário no arquivo de configuração."""
    cfg = load_models_config(force_reload=True)
    if "user_settings" not in cfg or not isinstance(cfg["user_settings"], dict):
        cfg["user_settings"] = {}
    cfg["user_settings"][key] = value
    save_models_config(cfg)

def get_flat_model_list() -> List[Tuple[str, str, str]]:
    """
    Retorna lista plana de todos os modelos para o combobox da barra:
    [(Nome Exibição, provedor_key, model_id), ...]
    """
    cfg = load_models_config(force_reload=True)
    items = []
    
    icons = {
        "nvidia": "⚡",
        "gemini": "✨",
        "openrouter": "🌐",
        "ollama": "💻",
        "groq": "🚀",
        "g4f": "🤖"
    }

    # 1. Modelos em builtin_models
    for prov_name, models_list in cfg.get("builtin_models", {}).items():
        prov_key = prov_name.lower()
        icon = icons.get(prov_key, "🤖")
        for m in models_list:
            short_name = m.split("/")[-1]
            display_name = f"{icon} {prov_name} • {short_name}"
            items.append((display_name, prov_key, m))

    # 2. Modelos em custom_servers (se houver)
    for srv in cfg.get("custom_servers", []):
        srv_nome = srv.get("nome", "Custom")
        srv_id = srv.get("id", "custom").lower()
        srv_icon = icons.get(srv_id, "🌐")
        for m in srv.get("modelos", []):
            short_name = m.split("/")[-1]
            display_name = f"{srv_icon} {srv_nome} • {short_name}"
            items.append((display_name, srv_id, m))

    return items
