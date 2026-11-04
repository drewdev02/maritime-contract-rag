FROM python:3.12-slim-bookworm

WORKDIR /app

# Instalar dependencias del sistema requeridas para compilación y utilidades
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalar uv de forma segura y portable
RUN pip install --no-cache-dir uv

# Solo los archivos de dependencias: así esta capa (la más lenta) no se invalida al editar
# código ni documentación.
COPY pyproject.toml uv.lock ./

# Instalar dependencias congeladas en el entorno virtual
RUN uv sync --frozen --no-dev --no-install-project

# Copiar código fuente y configuración de migraciones (README.md lo exige la metadata del paquete)
COPY README.md ./
COPY src/ ./src
COPY migrations/ ./migrations
COPY alembic.ini ./

# Instalar el proyecto en el entorno virtual
RUN uv sync --frozen --no-dev

# `uv run` en los comandos de compose no debe volver a sincronizar (descargaría las
# dependencias de desarrollo al arrancar): el entorno ya quedó construido arriba.
ENV UV_NO_SYNC=1

# Crear directorio para almacenamiento de contratos
RUN mkdir -p /app/storage/contracts

EXPOSE 8000
