
#!/bin/bash
set -e

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}🚀 Iniciando deployment del Trading Bot...${NC}"

# 1. Verificar directorio correcto
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

# 3. Verificar variables críticas
echo -e "${BLUE}🔍 Verificando variables de entorno...${NC}"
if [ -z "$BINANCE_API_KEY" ] || [ -z "$BINANCE_API_SECRET" ]; then
    echo -e "${RED}❌ Error: Credenciales de Binance no configuradas${NC}"
    exit 1
fi

if [ -z "$POSTGRES_PASSWORD" ]; then
    echo -e "${RED}❌ Error: Password de PostgreSQL no configurado${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Variables de entorno verificadas${NC}"

# 4. Crear directorios necesarios
echo -e "${YELLOW}📁 Creando directorios...${NC}"
mkdir -p logs
mkdir -p init-scripts
chmod 755 logs
chmod 755 init-scripts

# 5. Detener servicios antiguos
echo -e "${YELLOW}🛑 Deteniendo servicios antiguos...${NC}"
docker compose -f docker-compose.prod.yml down -v 2>/dev/null || true

# 6. Limpiar recursos
echo -e "${YELLOW}🧹 Limpiando recursos...${NC}"
docker system prune -f
docker volume prune -f

# 7. Pull de imágenes base
echo -e "${YELLOW}⬇️ Descargando imágenes base...${NC}"
docker pull postgres:16-alpine
docker pull python:3.12-slim

# 8. Build de la imagen del bot
echo -e "${YELLOW}🔨 Construyendo imagen del bot...${NC}"
docker compose -f docker-compose.prod.yml build --no-cache

# 9. Iniciar servicios
echo -e "${YELLOW}🚀 Iniciando servicios...${NC}"
docker compose -f docker-compose.prod.yml up -d

# 10. Esperar a PostgreSQL
echo -e "${YELLOW}⏳ Esperando a PostgreSQL...${NC}"
MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if docker exec trading_postgres_db pg_isready -U ${POSTGRES_USER:-trading_user} -d ${DB_NAME:-trading_bot} > /dev/null 2>&1; then
        echo -e "${GREEN}✅ PostgreSQL está listo${NC}"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo -e "${BLUE}   Intento $RETRY_COUNT/$MAX_RETRIES...${NC}"
    sleep 2
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo -e "${RED}❌ PostgreSQL no se pudo iniciar${NC}"
    echo -e "${YELLOW}📋 Mostrando logs de PostgreSQL:${NC}"
    docker logs trading_postgres_db
    exit 1
fi

# 11. Verificar estado de servicios
echo -e "${YELLOW}🔍 Verificando servicios...${NC}"
sleep 5
docker compose -f docker-compose.prod.yml ps

# 12. Verificar health checks
echo -e "${YELLOW}❤️ Verificando health checks...${NC}"
sleep 5

for service in trading_postgres_db trading_bot; do
    HEALTH=$(docker inspect --format='{{.State.Health.Status}}' $service 2>/dev/null || echo "unknown")
    if [ "$HEALTH" = "healthy" ] || [ "$HEALTH" = "starting" ]; then
        echo -e "${GREEN}✅ $service: $HEALTH${NC}"
    else
        echo -e "${RED}❌ $service: $HEALTH${NC}"
        echo -e "${YELLOW}📋 Logs de $service:${NC}"
        docker logs $service --tail=20
    fi
done

# 13. Mostrar logs iniciales
echo -e "\n${GREEN}✅ Deployment completado!${NC}"
echo -e "${YELLOW}📊 Logs iniciales:${NC}"
docker compose -f docker-compose.prod.yml logs --tail=30

# 14. Información de conexión
echo -e "\n${GREEN}📊 Información del Deployment:${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "Base de datos: ${DB_NAME:-trading_bot}"
echo -e "Usuario DB:    ${POSTGRES_USER:-trading_user}"
echo -e "Usuario DB:    ${POSTGRES_PASSWORD:-trading_pass}"
echo -e "Modo:          ${MODE:-REAL}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# 15. Comandos útiles
echo -e "\n${GREEN}📋 Comandos útiles:${NC}"
echo -e "  ${YELLOW}Ver logs (todos):${NC}     docker compose -f docker-compose.prod.yml logs -f"
echo -e "  ${YELLOW}Ver logs (bot):${NC}       docker logs -f trading_bot"
echo -e "  ${YELLOW}Ver logs (DB):${NC}        docker logs -f trading_postgres_db"
echo -e "  ${YELLOW}Estado servicios:${NC}     docker compose -f docker-compose.prod.yml ps"
echo -e "  ${YELLOW}Reiniciar bot:${NC}        docker compose -f docker-compose.prod.yml restart trading-bot"
echo -e "  ${YELLOW}Detener todo:${NC}         docker compose -f docker-compose.prod.yml down"
echo -e "  ${YELLOW}Shell bot:${NC}            docker exec -it trading_bot /bin/bash"
echo -e "  ${YELLOW}Shell DB (psql):${NC}      docker exec -it trading_postgres_db psql -U ${POSTGRES_USER:-trading_user} ${DB_NAME:-trading_bot}"
echo -e "  ${YELLOW}Monitorear:${NC}           ./monitor.sh"
echo -e "  ${YELLOW}Backup DB:${NC}            ./backup.sh"

echo -e "\n${GREEN}🎉 Bot desplegado exitosamente!${NC}"