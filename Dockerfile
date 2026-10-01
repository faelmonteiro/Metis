FROM python:3.11-slim AS builder

WORKDIR /build

COPY requirements.txt .

RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1

# O app resolve o config em METIS_CONFIG_DIR (default ~/.config/metis). Definir
# explicitamente faz o container gravar no volume montado, em vez de num diretório
# efêmero que se perde quando o container é recriado.
ENV METIS_CONFIG_DIR=/app/.config/metis

COPY --from=builder /install /usr/local

COPY app.py .
COPY config_models.json .
COPY assets ./assets
COPY agente ./agente

RUN mkdir -p /app/historico /app/.config/metis \
    && useradd -m -u 1000 -g 1000 appuser 2>/dev/null || useradd -m appuser \
    && chown -R appuser:appuser /app
USER appuser

CMD ["python", "app.py"]
