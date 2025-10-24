FROM python:3.11-alpine

WORKDIR /src

# Instalar dependencias de sistema necesarias
RUN apk add gcc musl-dev postgresql-dev python3-dev

# Copiar requirements.txt y .env primero
COPY requirements.txt .env ./
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "src/main.py"]
