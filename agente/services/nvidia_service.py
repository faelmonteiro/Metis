import json
import logging

import httpx

from agente import config
from agente.services.base import BaseService

logger = logging.getLogger(__name__)

API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"


def _build_request(mensagens: list, stream: bool = False, model: str = None) -> tuple:
    """Constrói headers e payload para a NVIDIA API."""
    if not config.NVIDIA_API_KEY:
        raise RuntimeError("NVIDIA_API_KEY não configurada.")

    headers = {
        "Authorization": f"Bearer {config.NVIDIA_API_KEY}",
        "Content-Type": "application/json"
    }

    # Formata mensagens para garantir compatibilidade com formato OpenAI
    # Nota: NVIDIA API não suporta tool calling — mensagens de ferramenta são descartadas
    clean_messages = []
    for m in mensagens:
        role = m.get("role", "user")
        if role in ["system", "user", "assistant"]:
            clean_messages.append({"role": role, "content": str(m.get("content", ""))})
        elif role in ["functionCall", "functionResponse"]:
            logger.warning(f"NVIDIA API não suporta tool calling — mensagem '{role}' descartada")

    payload = {
        "model": model or getattr(config, "NVIDIA_MODEL", "moonshotai/kimi-k3"),
        "messages": clean_messages,
        "stream": stream,
        "max_tokens": getattr(config, "MAX_OUTPUT_TOKENS", config.NVIDIA_MAX_TOKENS),
        "temperature": getattr(config, "NVIDIA_TEMPERATURE", getattr(config, "DEFAULT_TEMPERATURE", 0.7)),
    }

    return headers, payload


def _handle_error(res):
    """Trata erros HTTP da NVIDIA API."""
    if res.status_code == 401:
        raise RuntimeError("NVIDIA_API_KEY inválida.")
    if res.status_code == 429:
        raise RuntimeError("Rate limit da NVIDIA API atingido.")
    res.raise_for_status()




def gerar_resposta_stream(mensagens: list, model: str = None, service=None):
    """Gera resposta via streaming SSE da NVIDIA API (formato OpenAI)."""
    model_name = model or getattr(config, "NVIDIA_MODEL", "moonshotai/kimi-k3")
    headers, payload = _build_request(mensagens, stream=True, model=model_name)

    timeout = httpx.Timeout(connect=10.0, read=300.0, write=10.0, pool=10.0)

    try:
        from agente.services.http_client import get_http_client
        client = get_http_client()
        with client.stream("POST", API_URL, headers=headers, json=payload, timeout=timeout) as res:
            if service:
                service._active_stream = res
            try:
                _handle_error(res)

                for line in res.iter_lines():
                    if service and getattr(service, "_aborted", False):
                        break
                    if not line.startswith("data: "):
                        continue
                    if line.strip() == "data: [DONE]":
                        break
                    try:
                        data = json.loads(line[6:])
                        content = data["choices"][0]["delta"].get("content", "")
                        if content:
                            yield content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        pass
            finally:
                if service:
                    service._active_stream = None
    except httpx.RequestError as e:
        if service and getattr(service, "_aborted", False):
            return
        raise RuntimeError(f"Erro de conexão com NVIDIA API: {e}")

class NvidiaService(BaseService):
    def __init__(self, model: str = None):
        super().__init__()
        self.model = model or getattr(config, "NVIDIA_MODEL", "moonshotai/kimi-k3")

    @property
    def nome_provedor(self) -> str:
        return f"NVIDIA ({self.model})"

    def gerar_resposta_stream(self, mensagens: list):
        self._aborted = False
        return gerar_resposta_stream(mensagens, model=self.model, service=self)
