import logging

import httpx

from agente import config
from agente.services.base import BaseService, parse_openai_sse_stream

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

    from agente.services.base import format_openai_messages

    # NVIDIA API não suporta tool calling — mensagens de ferramenta são descartadas
    # e a mídia não é enviada (formato de texto puro, como antes).
    clean_messages = format_openai_messages(mensagens, descartar_tools=True, incluir_midia=False)

    payload = {
        "model": model or config.NVIDIA_MODEL,
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
    model_name = model or config.NVIDIA_MODEL
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

                tool_calls_map = {}
                yield from parse_openai_sse_stream(res.iter_lines(), tool_calls_map)
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
        self.model = model or config.NVIDIA_MODEL

    @property
    def nome_provedor(self) -> str:
        return f"NVIDIA ({self.model})"

    def gerar_resposta_stream(self, mensagens: list):
        self._aborted = False
        return gerar_resposta_stream(mensagens, model=self.model, service=self)
