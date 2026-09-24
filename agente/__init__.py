"""Módulo principal do agente Llama + SearXNG."""
import logging
logger = logging.getLogger(__name__)

try:
    import readline  # NOQA: efeito colateral intencional (histórico/edição no input())
except ImportError as _silent_e:
    logger.debug("Exceção silenciosa tratada: %s", _silent_e, exc_info=True)
