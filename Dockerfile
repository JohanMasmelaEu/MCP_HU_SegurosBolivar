FROM python:3.12-slim

LABEL maintainer="Equipo Arquitectura - Seguros Bolivar"
LABEL description="MCP Server para analisis de Historias de Usuario con panel de expertos y memoria contextual"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

VOLUME ["/workspace"]

ENV PYTHONUNBUFFERED=1
ENV MCP_WORKSPACE_PATH=/workspace

ENTRYPOINT ["python", "-m", "src.server"]
