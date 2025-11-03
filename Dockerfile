FROM python:3.11-alpine

WORKDIR /src

# Instalar dependencias del sistema
RUN apk update && apk add --no-cache \
  gcc \
  musl-dev \
  postgresql-dev \
  python3-dev

# Copiar solo los archivos de dependencias
COPY requirements.txt ./

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar solo el .env de producción
COPY .env ./

# Copiar el código fuente
COPY src/ ./src/

CMD ["python", "src/main.py"]
