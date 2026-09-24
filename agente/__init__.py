"""Módulo principal do agente Llama + SearXNG."""
import logging
logger = logging.getLogger(__name__)

try:
    import readline
except ImportError as _silent_e:
    logger.debug("Exceção silenciosa tratada: %s", _silent_e, exc_info=True)
