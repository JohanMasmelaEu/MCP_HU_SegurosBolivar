FROM python:3.12-slim

LABEL maintainer="Equipo Arquitectura - Seguros Bolivar"
LABEL description="MCP Server para analisis de Historias de Usuario con panel de expertos y memoria contextual"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN mkdir -p /app/static/vendor && \
    python -c "import urllib.request; \
    urllib.request.urlretrieve('https://unpkg.com/cytoscape@3.30.4/dist/cytoscape.min.js', '/app/static/vendor/cytoscape.min.js'); \
    urllib.request.urlretrieve('https://unpkg.com/layout-base@2.0.1/layout-base.js', '/app/static/vendor/layout-base.js'); \
    urllib.request.urlretrieve('https://unpkg.com/cose-base@2.2.0/cose-base.js', '/app/static/vendor/cose-base.js'); \
    urllib.request.urlretrieve('https://unpkg.com/cytoscape-cose-bilkent@4.1.0/cytoscape-cose-bilkent.js', '/app/static/vendor/cytoscape-cose-bilkent.js')"

COPY src/ ./src/

VOLUME ["/workspace"]

ENV PYTHONUNBUFFERED=1
ENV MCP_WORKSPACE_PATH=/workspace

EXPOSE 9751

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:9751/api/eco/ecosystems')" || exit 1

ENTRYPOINT ["python", "-m", "src.server"]
