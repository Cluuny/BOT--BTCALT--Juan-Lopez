#!/bin/bash
set -e  # Exit on error

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Iniciando deployment en GCP...${NC}"

# 1. Verificar que estamos en el directorio correcto
if [ ! -f "docker-compose.prod.yml" ]; then
    echo -e "${RED}❌ Error: docker-compose.prod.yml no encontrado${NC}"
    exit 1
fi

# 2. Verificar archivo .env.production
echo -e "${YELLOW}🔐 Verificando configuración...${NC}"
if [ ! -f ".env.production" ]; then
    echo -e "${RED}❌ Error: .env.production no encontrado${NC}"
    echo -e "${YELLOW}Ejecuta primero: ./setup-env.sh${NC}"
    exit 1
fi

# Cargar variables de entorno
set -a
source .env.production
set +a

# 4. Crear directorio de logs
echo -e "${YELLOW}📝 Configurando logs...${NC}"
mkdir -p logs
chmod 755 logs

# 5. Pull de imágenes base (ahorra tiempo)
echo -e "${YELLOW}⬇️ Descargando imágenes base...${NC}"
docker pull postgres:16-alpine
docker pull python:3.12-slim

# 6. Build de la imagen del bot
echo -e "${YELLOW}🔨 Construyendo imagen del bot...${NC}"
docker-compose -f docker-compose.prod.yml build --no-cache

# 7. Detener servicios antiguos si existen
echo -e "${YELLOW}🛑 Deteniendo servicios antiguos...${NC}"
docker-compose -f docker-compose.prod.yml down || true

# 8. Limpiar contenedores huérfanos y volúmenes no usados
echo -e "${YELLOW}🧹 Limpiando recursos no usados...${NC}"
docker system prune -f
docker volume prune -f

# 9. Iniciar servicios
echo -e "${YELLOW}🚀 Iniciando servicios...${NC}"
docker-compose -f docker-compose.prod.yml up -d

# 10. Esperar a que los servicios estén healthy
echo -e "${YELLOW}⏳ Esperando a que los servicios estén listos...${NC}"
sleep 10

# 11. Verificar estado de los servicios
echo -e "${YELLOW}🔍 Verificando estado de servicios...${NC}"
docker-compose -f docker-compose.prod.yml ps

# 12. Mostrar logs iniciales
echo -e "${GREEN}✅ Deployment completado!${NC}"
echo -e "${YELLOW}📊 Logs iniciales:${NC}"
docker-compose -f docker-compose.prod.yml logs --tail=50

# 13. Comandos útiles
echo -e "\n${GREEN}📋 Comandos útiles:${NC}"
echo "  Ver logs:     docker-compose -f docker-compose.prod.yml logs -f"
echo "  Detener:      docker-compose -f docker-compose.prod.yml down"
echo "  Reiniciar:    docker-compose -f docker-compose.prod.yml restart"
echo "  Estado:       docker-compose -f docker-compose.prod.yml ps"
echo "  Shell bot:    docker exec -it trading_bot /bin/bash"
echo "  Shell DB:     docker exec -it trading_postgres_db psql -U \$(cat secrets/db_user.txt) trading_bot"