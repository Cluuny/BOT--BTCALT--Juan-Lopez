FROM python:3.12-slim

# Metadata
LABEL maintainer="vistrent834@gmail.com"
LABEL version="1.0"

WORKDIR /src

# 1. Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 2. Copiar solo requirements
COPY requirements-prod.txt ./

# 3. Instalar dependencias Python
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copiar código fuente (sin .env)
COPY src/ ./src/

# 5. Crear usuario no-root para seguridad
RUN useradd -m -u 1000 tradingbot && \
    chown -R tradingbot:tradingbot /src

USER tradingbot

# 6. Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD python -c "import sys; sys.exit(0)"

# 7. Variables de entorno se inyectan en runtime
ENV PYTHONUNBUFFERED=1
ENV MODE=REAL

CMD ["python", "src/main.py"]