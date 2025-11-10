#!/bin/bash
# Script mejorado para diagnosticar problemas con PostgreSQL

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🔍 Diagnóstico de PostgreSQL${NC}"
echo "=============================="

# Cargar variables de entorno
if [ -f ".env.production" ]; then
    set -a
    source .env.production
    set +a
    echo -e "${GREEN}✅ Variables de entorno cargadas${NC}"
else
    echo -e "${RED}❌ .env.production no encontrado${NC}"
fi

# 1. Estado del contenedor
echo -e "\n${YELLOW}1️⃣ Estado del Contenedor:${NC}"
if docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.State}}" | grep trading_postgres_db > /dev/null 2>&1; then
    docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.State}}" | grep trading_postgres_db

    # Health status
    HEALTH=$(docker inspect --format='{{.State.Health.Status}}' trading_postgres_db 2>/dev/null || echo "no-healthcheck")
    if [ "$HEALTH" = "healthy" ]; then
        echo -e "${GREEN}✅ Health: $HEALTH${NC}"
    else
        echo -e "${RED}❌ Health: $HEALTH${NC}"
    fi
else
    echo -e "${RED}❌ Contenedor trading_postgres_db no existe${NC}"
    exit 1
fi

# 2. Variables de entorno del contenedor
echo -e "\n${YELLOW}2️⃣ Variables de Entorno PostgreSQL:${NC}"
docker exec trading_postgres_db env | grep POSTGRES || echo -e "${RED}No se pueden leer variables${NC}"

# 3. Verificar conectividad básica
echo -e "\n${YELLOW}3️⃣ Verificando Conectividad:${NC}"
if docker exec trading_postgres_db pg_isready -U ${POSTGRES_USER:-trading_user} 2>&1; then
    echo -e "${GREEN}✅ PostgreSQL responde a pg_isready${NC}"
else
    echo -e "${RED}❌ PostgreSQL no responde${NC}"
fi

# 4. Intentar conexión a la base de datos específica
echo -e "\n${YELLOW}4️⃣ Probando Conexión a Base de Datos:${NC}"
if docker exec trading_postgres_db psql -U ${POSTGRES_USER:-trading_user} -d ${DB_NAME:-trading_bot} -c "SELECT version();" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Conexión exitosa a ${DB_NAME:-trading_bot}${NC}"
    docker exec trading_postgres_db psql -U ${POSTGRES_USER:-trading_user} -d ${DB_NAME:-trading_bot} -c "SELECT version();"
else
    echo -e "${RED}❌ No se puede conectar a ${DB_NAME:-trading_bot}${NC}"
fi

# 5. Listar bases de datos
echo -e "\n${YELLOW}5️⃣ Bases de Datos Disponibles:${NC}"
docker exec trading_postgres_db psql -U ${POSTGRES_USER:-trading_user} -c "\l" 2>&1 || echo -e "${RED}Error listando bases de datos${NC}"

# 6. Ver logs completos
echo -e "\n${YELLOW}6️⃣ Logs de PostgreSQL (últimas 50 líneas):${NC}"
docker logs trading_postgres_db --tail=50 2>&1

# 7. Verificar volumen de datos
echo -e "\n${YELLOW}7️⃣ Información del Volumen:${NC}"
docker volume inspect bot--btcalt--juan-lopez_postgres_data 2>&1 || echo -e "${YELLOW}Volumen no encontrado o nombre diferente${NC}"

# 8. Verificar procesos dentro del contenedor
echo -e "\n${YELLOW}8️⃣ Procesos PostgreSQL:${NC}"
docker exec trading_postgres_db ps aux 2>&1 || echo -e "${RED}No se pueden listar procesos${NC}"

# 9. Verificar archivos de configuración
echo -e "\n${YELLOW}9️⃣ Verificar PGDATA:${NC}"
docker exec trading_postgres_db ls -la /var/lib/postgresql/data/pgdata 2>&1 || echo -e "${RED}PGDATA no accesible${NC}"

# 10. Test de escritura
echo -e "\n${YELLOW}🔟 Test de Escritura en DB:${NC}"
if docker exec trading_postgres_db psql -U ${POSTGRES_USER:-trading_user} -d ${DB_NAME:-trading_bot} -c "CREATE TABLE IF NOT EXISTS healthcheck (id serial, check_time timestamp); INSERT INTO healthcheck (check_time) VALUES (NOW()); SELECT * FROM healthcheck ORDER BY check_time DESC LIMIT 1;" 2>&1; then
    echo -e "${GREEN}✅ Escritura exitosa${NC}"
else
    echo -e "${RED}❌ Error en escritura${NC}"
fi

# 11. Verificar configuración del healthcheck
echo -e "\n${YELLOW}1️⃣1️⃣ Configuración del Healthcheck:${NC}"
docker inspect trading_postgres_db --format='{{json .State.Health}}' 2>&1 | python3 -m json.tool || echo "Sin healthcheck configurado"

# 12. Recomendaciones
echo -e "\n${BLUE}📋 Recomendaciones:${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

if [ "$HEALTH" != "healthy" ]; then
    echo -e "${YELLOW}⚠️ PostgreSQL no está healthy. Posibles causas:${NC}"
    echo "   1. El contenedor está iniciando (espera 30s más)"
    echo "   2. Credenciales incorrectas en .env.production"
    echo "   3. Volumen corrupto (ejecuta: docker volume rm bot--btcalt--juan-lopez_postgres_data)"
    echo "   4. Puerto 5432 ocupado en el host"
    echo ""
    echo -e "${YELLOW}🔧 Acciones sugeridas:${NC}"
    echo "   - Reiniciar: docker compose -f docker-compose.prod.yml restart postgres"
    echo "   - Ver logs: docker logs -f trading_postgres_db"
    echo "   - Cleanup: ./cleanup.sh && ./setup-env.sh && ./deploy.sh"
else
    echo -e "${GREEN}✅ PostgreSQL está funcionando correctamente${NC}"
fi

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"