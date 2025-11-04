FROM python:3.12-slim

WORKDIR /src

# Instalar dependencias del sistema CORREGIDO
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements de producción
COPY requirements-prod.txt ./

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements-prod.txt

# Copiar el código fuente
COPY .env ./
COPY src/ ./src/

CMD ["python", "src/main.py"]