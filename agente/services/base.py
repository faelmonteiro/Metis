import json
import logging
from abc import ABC, abstractmethod
from typing import Iterator, Dict, Any, Generator

logger = logging.getLogger(__name__)

class BaseService(ABC):
    def __init__(self):
        self._active_stream = None
        self._aborted = False

    def abort(self):
        """Interrompe qualquer conexão HTTP ou stream ativo imediatamente."""
        self._aborted = True
        if hasattr(self, "_active_stream") and self._active_stream is not None:
            try:
                self._active_stream.close()
            except Exception:
                pass
            self._active_stream = None

    @abstractmethod
    def gerar_resposta_stream(self, mensagens: list) -> Iterator[str]:
        """Gera a resposta da LLM via streaming, fazendo yield de chunks de string."""
        pass
        
    @property
    @abstractmethod
    def nome_provedor(self) -> str:
        """Retorna o nome do provedor para exibição (ex: 'OLLAMA', 'GROQ', etc)."""
        pass


def parse_openai_sse_stream(
    lines_iterator: Iterator[str],
    tool_calls_map: Dict[int, Dict[str, Any]]
) -> Generator[str, None, None]:
    """
    Parseia linhas SSE no padrão OpenAI (data: {...}), fazendo yield de content e populando tool_calls_map.
    """
    for line in lines_iterator:
        if not line.startswith("data: "):
            continue
        if line.strip() == "data: [DONE]":
            break
        try:
            data = json.loads(line[6:])
            choices = data.get("choices", [])
            if not choices:
                continue
            delta = choices[0].get("delta", {})
            
            content = delta.get("content")
            if content:
                yield content
                
            if "tool_calls" in delta:
                for tc in delta["tool_calls"]:
                    tc_idx = tc.get("index", 0)
                    if tc_idx not in tool_calls_map:
                        tool_calls_map[tc_idx] = {"id": "", "name": "", "args_str": ""}
                    if tc.get("id"):
                        tool_calls_map[tc_idx]["id"] = tc["id"]
                    if tc.get("function"):
                        if tc["function"].get("name"):
                            tool_calls_map[tc_idx]["name"] = tc["function"]["name"]
                        if tc["function"].get("arguments"):
                            tool_calls_map[tc_idx]["args_str"] += tc["function"]["arguments"]
        except (json.JSONDecodeError, KeyError, IndexError):
            pass


def process_tool_calls_map(
    tool_calls_map: Dict[int, Dict[str, Any]],
    mensagens: list,
    iteration: int = 0
) -> bool:
    """
    Executa as ferramentas reconstruídas a partir de tool_calls_map e anexa as mensagens ao histórico.
    Retorna True se houve ferramentas executadas.
    """
    if not tool_calls_map:
        return False
    from agente.services.tool_executor import executar_tool
    has_executed = False
    for tc_idx in sorted(tool_calls_map.keys()):
        tc_data = tool_calls_map[tc_idx]
        name = tc_data.get("name")
        if not name:
            continue

        args = {}
        json_error = None
        if tc_data.get("args_str"):
            try:
                args = json.loads(tc_data["args_str"])
            except Exception as e:
                json_error = str(e)
                logger.warning(f"Erro ao decodificar JSON dos argumentos de {name}: {e}")

        call_id = tc_data.get("id") or f"call_{tc_idx}_{iteration}"
        func_call = {
            "id": call_id,
            "name": name,
            "args": args if json_error is None else {}
        }
        mensagens.append({
            "role": "functionCall",
            "functionCall": func_call
        })

        if json_error:
            result = (
                f"Erro: os argumentos enviados para a ferramenta '{name}' contêm JSON inválido ({json_error}). "
                f"Texto recebido: {tc_data.get('args_str')}. Por favor, envie novamente com argumentos formatados em JSON válido."
            )
        else:
            result = executar_tool(name, args)

        mensagens.append({
            "role": "functionResponse",
            "id": call_id,
            "name": name,
            "content": result
        })
        has_executed = True
    return has_executed
