FROM python:3.12-slim AS training

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    MLFLOW_DISABLE_AGENT_HINT=1

RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv==0.12.23 \
    && useradd --create-home --uid 10001 atlas

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable
COPY --chown=atlas:atlas configs ./configs
COPY --chown=atlas:atlas scripts ./scripts
COPY --chown=atlas:atlas .streamlit ./.streamlit
COPY --chown=atlas:atlas deploy ./deploy
RUN mkdir -p artifacts data/processed reports mlruns && chown -R atlas:atlas /app
USER atlas

EXPOSE 8000 8501
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=4)"
CMD ["atlas", "serve", "--host", "0.0.0.0"]

# Build the tiny public synthetic bundle once, never during a cloud cold start.
FROM training AS demo-build
RUN python scripts/bootstrap.py

# Default target is a self-contained Docker demo exposing one hosting port.
FROM training AS cloud
COPY --from=caddy:2.10.2-alpine /usr/bin/caddy /usr/local/bin/caddy
COPY --from=demo-build --chown=atlas:atlas /app/artifacts/synthetic-v1 /app/artifacts/synthetic-v1
ENV PORT=10000
EXPOSE 10000
HEALTHCHECK --interval=15s --timeout=10s --start-period=30s --retries=3 \
    CMD python scripts/cloud_entrypoint.py --healthcheck
CMD ["python", "scripts/cloud_entrypoint.py"]
