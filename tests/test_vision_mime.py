"""
MIME de imagem do motor de visão.

O payload saía sempre rotulado como `image/jpeg`, qualquer que fosse o arquivo.
Pior: o fallback cobria também o que nem é imagem (SVG, ICO, arquivo vazio), que
passava pelo gate da UI e só era rejeitado dentro da API, com erro genérico.
"""
import base64

import pytest

from vision.ai_engine import (
    _MIME_FALLBACK,
    _imagem_suportada,
    _mime_da_imagem,
)

# PNG 1x1 real: prova que a detecção funciona com bytes de verdade, não só com
# a assinatura colada num buffer.
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8"
    "BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

ASSINATURAS_RASTER = [
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff\xe0\x00\x10JFIF", "image/jpeg"),
    (b"RIFF\x00\x00\x00\x00WEBPVP8 ", "image/webp"),
    (b"GIF89a", "image/gif"),
    (b"GIF87a", "image/gif"),
]


@pytest.mark.parametrize("assinatura,mime_esperado", ASSINATURAS_RASTER)
def test_raster_suportado_e_identificado(assinatura, mime_esperado):
    dados = assinatura + b"\x00\x01\x02\x03lixo depois da assinatura"
    assert _mime_da_imagem(dados) == mime_esperado
    assert _imagem_suportada(dados) is True


def test_png_real_e_suportado():
    assert _mime_da_imagem(PNG_1X1) == "image/png"
    assert _imagem_suportada(PNG_1X1) is True


@pytest.mark.parametrize(
    "assinatura,mime_esperado",
    [(b"BM\x00\x00\x00\x00", "image/bmp"), (b"II*\x00", "image/tiff")],
)
def test_raster_reconhecido_porem_fora_do_aceito(assinatura, mime_esperado):
    """BMP/TIFF são imagens, mas não no conjunto que as APIs de visão aceitam."""
    assert _mime_da_imagem(assinatura) == mime_esperado
    assert _imagem_suportada(assinatura) is False


@pytest.mark.parametrize(
    "dados",
    [
        b"",
        b"   ",
        b"nao sou imagem nenhuma",
        b"<svg xmlns='http://www.w3.org/2000/svg'></svg>",  # vetor
        b"\x00\x00\x01\x00" + b"\x00" * 20,  # cabeçalho de ICO
    ],
)
def test_nao_imagem_nao_passa_como_jpeg(dados):
    """O fallback JPEG era a falha real: mascaráva conteúdo inválido."""
    assert _mime_da_imagem(dados) is None
    assert _imagem_suportada(dados) is False


def test_fallback_nao_mentira_que_e_jpeg():
    assert _MIME_FALLBACK != "image/jpeg"


def test_magic_bytes_sofrem_prefixo_de_whitespace():
    """Screenshot base64 às vezes chega com whitespace antes do cabeçalho."""
    assert _mime_da_imagem(b"\n \t" + PNG_1X1) == "image/png"
    assert _imagem_suportada(b"\n \t" + PNG_1X1) is True