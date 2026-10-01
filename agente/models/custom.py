"""
CRUD para servidores customizados (OpenRouter, DeepSeek, etc.).
"""
import copy as _copy
import re
from typing import List, Dict, Optional
from .storage import (
    load_config,
    save_config,
    purge_model_from_legacy_files,
    purge_server_from_legacy_files,
)


def _normalize_server_id(name: str) -> str:
    """Gera ID único a partir do nome."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", name.strip().lower()).strip("_")


# IDs reservados: provedores embutidos que não podem virar servidores customizados.
BUILTIN_PROVIDER_IDS = frozenset({"ollama", "gemini", "groq", "nvidia", "g4f"})


def _find_server_index(config: Dict, server_id: str) -> int:
    """Encontra índice do servidor pelo ID ou nome (case-insensitive)."""
    server_id_lower = server_id.strip().lower()
    for i, s in enumerate(config.get("custom_servers", [])):
        if (
            s.get("id", "").strip().lower() == server_id_lower
            or s.get("nome", "").strip().lower() == server_id_lower
        ):
            return i
    return -1


def get_custom_servers() -> List[Dict]:
    """Retorna todos os servidores customizados cadastrados."""
    config = load_config()
    return config.get("custom_servers", [])


def get_custom_server(server_id: str) -> Optional[Dict]:
    """Busca um servidor customizado pelo ID."""
    servers = load_config().get("custom_servers", [])
    idx = _find_server_index({"custom_servers": servers}, server_id)
    if 0 <= idx < len(servers):
        return _copy.deepcopy(servers[idx])
    return None


def add_custom_server(
    nome: str,
    base_url: str,
    api_key: str = "",
    modelo_padrao: str = "",
    api_key_env: str = "",
    modelos_iniciais: Optional[List[str]] = None,
) -> Dict:
    """Adiciona ou atualiza um servidor customizado."""
    config = load_config()

    server_id = _normalize_server_id(nome)
    if not server_id:
        server_id = f"custom_server_{len(config.get('custom_servers', [])) + 1}"

    if not api_key_env:
        api_key_env = f"{server_id.upper()}_API_KEY"

    idx = _find_server_index(config, server_id)

    # Colisão de ID com um provider builtin (ex.: "g4f", "ollama"): mudava o
    # significado da entrada sem avisar. Rejeita em vez de misturar os dois.
    if idx < 0 and server_id.strip().lower() in BUILTIN_PROVIDER_IDS:
        raise ValueError(
            f"'{server_id}' colide com um provedor embutido. "
            "Escolha outro nome para o servidor personalizado."
        )

    # Só grava a chave depois das validações: um cadastro recusado não pode
    # deixar credencial órfã no .env (e em os.environ) para o resto da sessão.
    if api_key:
        from .preferences import save_env_var
        save_env_var(api_key_env, api_key)

    server_data = {
        "id": server_id,
        "nome": nome.strip(),
        "base_url": base_url.strip(),
        "api_key_env": api_key_env,
        "modelos": modelos_iniciais or [],
        "modelo_atual": modelo_padrao.strip() or (modelos_iniciais[0] if modelos_iniciais else ""),
    }

    if idx >= 0:
        # Atualiza preservando modelos existentes
        existing = config["custom_servers"][idx]
        existing_modelos = existing.get("modelos", [])
        for m in server_data["modelos"]:
            if m not in existing_modelos:
                existing_modelos.append(m)
        server_data["modelos"] = existing_modelos
        if not server_data["modelo_atual"] and existing.get("modelo_atual"):
            server_data["modelo_atual"] = existing["modelo_atual"]
        config["custom_servers"][idx] = server_data
    else:
        config["custom_servers"].append(server_data)

    # Cadastrar/atualizar desfaz o soft delete: um id que ficou em
    # `removed_servers` esconderia o servidor recém-criado de todas as listas.
    from .preferences import drop_server_from_removed_list
    drop_server_from_removed_list(config, server_id)

    save_config(config)
    return server_data


def remove_custom_server(server_id: str) -> bool:
    """
    Remove permanentemente um servidor customizado.

    Apaga a entrada de `custom_servers`, limpa as referências pendentes
    (active_models / active_provider / .env) e propaga para as cópias legadas
    do config, para que a exclusão não deixe sobras em outros arquivos.
    """
    config = load_config()
    idx = _find_server_index(config, server_id)
    if idx < 0:
        return False

    removed = config["custom_servers"].pop(idx)
    # Exclusão permanente também desfaz o soft delete: com o id em
    # `removed_servers`, recriar um servidor com o mesmo nome o trazia de volta
    # já marcado como removido (e portanto invisível nas listas da GUI).
    from .preferences import drop_server_from_removed_list
    drop_server_from_removed_list(config, removed.get("id") or server_id)
    save_config(config)

    purge_server_from_legacy_files(
        removed.get("id", server_id),
        removed.get("nome", ""),
    )
    from .preferences import purge_server_references
    purge_server_references(removed.get("id") or server_id)
    return True


def update_custom_server(server_id: str, **kwargs) -> bool:
    """Atualiza campos de um servidor customizado."""
    config = load_config()
    idx = _find_server_index(config, server_id)
    if idx < 0:
        return False

    server = config["custom_servers"][idx]
    allowed_fields = {"nome", "base_url", "api_key_env", "modelo_atual"}
    for key, value in kwargs.items():
        if key in allowed_fields and value is not None:
            server[key] = value

    save_config(config)
    return True


def add_model_to_server(server_id: str, model_id: str) -> bool:
    """Adiciona modelo a um servidor customizado ou provedor builtin."""
    config = load_config()
    idx = _find_server_index(config, server_id)
    if idx >= 0:
        model_id = model_id.strip()
        if model_id and model_id not in config["custom_servers"][idx].get("modelos", []):
            config["custom_servers"][idx].setdefault("modelos", []).append(model_id)
            save_config(config)
            return True
        return True

    # Se não for custom server, tenta provedor builtin (ex: G4F, Ollama)
    from .builtin import _canonical_provider_name
    canon = _canonical_provider_name(server_id)
    if "builtin_models" not in config:
        config["builtin_models"] = {}
    if canon in config["builtin_models"] or canon in ["G4F", "Ollama"]:
        config["builtin_models"].setdefault(canon, [])
        model_id = model_id.strip()
        if model_id and model_id not in config["builtin_models"][canon]:
            config["builtin_models"][canon].append(model_id)
            save_config(config)
            return True
        return True

    return False


def remove_model_from_server(server_id: str, model_id: str) -> bool:
    """Remove modelo de um servidor customizado ou provedor builtin."""
    config = load_config()
    idx = _find_server_index(config, server_id)
    if idx >= 0:
        model_id = model_id.strip()
        modelos = config["custom_servers"][idx].get("modelos", [])
        if model_id in modelos:
            modelos.remove(model_id)
            # Atualiza modelo_atual se era o removido
            if config["custom_servers"][idx].get("modelo_atual") == model_id:
                config["custom_servers"][idx]["modelo_atual"] = modelos[0] if modelos else ""
            save_config(config)
            purge_model_from_legacy_files(model_id)
            return True
        return False

    # Provedor builtin
    from .builtin import _canonical_provider_name
    canon = _canonical_provider_name(server_id)
    if "builtin_models" in config and canon in config["builtin_models"]:
        model_id = model_id.strip()
        if model_id in config["builtin_models"][canon]:
            config["builtin_models"][canon].remove(model_id)
            save_config(config)
            purge_model_from_legacy_files(model_id)
            return True

    return False


def set_server_active_model(server_id: str, model_id: str) -> bool:
    """Define modelo ativo para um servidor."""
    config = load_config()
    idx = _find_server_index(config, server_id)
    if idx < 0:
        return False

    model_id = model_id.strip()
    modelos = config["custom_servers"][idx].get("modelos", [])
    if model_id in modelos:
        config["custom_servers"][idx]["modelo_atual"] = model_id
        save_config(config)
        return True
    return False


def get_server_models(server_id: str) -> List[str]:
    """Retorna modelos de um servidor customizado OU provedor builtin."""
    # 1. Tenta servidor customizado
    server = get_custom_server(server_id)
    if server:
        return server.get("modelos", [])
    
    # 2. Tenta provedor builtin (case-insensitive)
    from .builtin import get_models_for_provider
    return get_models_for_provider(server_id)


def get_all_models_for_provider(provider: str) -> List[str]:
    """Retorna todos os modelos (builtin + custom_servers) para um provedor."""
    from .builtin import get_models_for_provider
    builtin = get_models_for_provider(provider)
    custom = get_server_models(provider)  # já mescla ambos
    # Merge sem duplicatas
    seen = set()
    result = []
    for m in builtin + custom:
        if m not in seen:
            seen.add(m)
            result.append(m)
    return result


def sync_from_config(config_data: Dict) -> None:
    """Sincroniza servidores customizados vindos de outro config (ex: providers_manager)."""
    # Esta função é usada para migração/importação
    pass