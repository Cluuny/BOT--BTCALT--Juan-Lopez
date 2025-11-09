#!/bin/bash
# Script de monitoreo para trading bot con recursos limitados

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Umbrales de alerta
CPU_THRESHOLD=80
MEMORY_THRESHOLD=85
DISK_THRESHOLD=90

echo "Trading Bot Monitor - $(date)"
echo "=================================="

# 1. Estado de contenedores
echo -e "\n${YELLOW}Estado de Contenedores:${NC}"
docker-compose -f docker-compose.prod.yml ps

# 2. Uso de recursos
echo -e "\n${YELLOW}Uso de Recursos:${NC}"
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}"

# 3. Verificar CPU
CPU_USAGE=$(top -bn1 | grep "Cpu(s)" | sed "s/.*, *\([0-9.]*\)%* id.*/\1/" | awk '{print 100 - $1}')
CPU_USAGE_INT=${CPU_USAGE%.*}
if [ $CPU_USAGE_INT -gt $CPU_THRESHOLD ]; then
    echo -e "${RED}CPU alta: ${CPU_USAGE}%${NC}"
else
    echo -e "${GREEN}CPU: ${CPU_USAGE}%${NC}"
fi

# 4. Verificar memoria
MEMORY_USAGE=$(free | grep Mem | awk '{print ($3/$2) * 100.0}')
MEMORY_USAGE_INT=${MEMORY_USAGE%.*}
if [ $MEMORY_USAGE_INT -gt $MEMORY_THRESHOLD ]; then
    echo -e "${RED}⚠Memoria alta: ${MEMORY_USAGE}%${NC}"
else
    echo -e "${GREEN}Memoria: ${MEMORY_USAGE}%${NC}"
fi

# 5. Verificar disco
DISK_USAGE=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')
if [ $DISK_USAGE -gt $DISK_THRESHOLD ]; then
    echo -e "${RED}⚠Disco alto: ${DISK_USAGE}%${NC}"
else
    echo -e "${GREEN}Disco: ${DISK_USAGE}%${NC}"
fi

# 6. Logs recientes de errores
echo -e "\n${YELLOW}Errores Recientes:${NC}"
docker-compose -f docker-compose.prod.yml logs --tail=20 | grep -i "error\|critical\|exception" || echo "Sin errores"

# 7. Health checks
echo -e "\n${YELLOW}❤Health Checks:${NC}"
for container in trading_bot trading_postgres_db; do
    HEALTH=$(docker inspect --format='{{.State.Health.Status}}' $container 2>/dev/null || echo "unknown")
    if [ "$HEALTH" = "healthy" ]; then
        echo -e "${GREEN}✓ $container: $HEALTH${NC}"
    else
        echo -e "${RED}✗ $container: $HEALTH${NC}"
    fi
done

# 8. Conexiones de red activas
echo -e "\n${YELLOW}Conexiones Activas:${NC}"
docker exec trading_bot netstat -an 2>/dev/null | grep ESTABLISHED | wc -l || echo "N/A"

# 9. Tamaño de logs
echo -e "\n${YELLOW}Tamaño de Logs:${NC}"
du -sh logs/ 2>/dev/null || echo "N/A"

# 10. Uptime de contenedores
echo -e "\n${YELLOW}Uptime:${NC}"
docker ps --format "table {{.Names}}\t{{.Status}}" | grep -E "trading_bot|trading_postgres"

# 11. Verificar última actualización de precios
echo -e "\n${YELLOW}Última Actividad:${NC}"
docker-compose -f docker-compose.prod.yml logs --tail=5 trading_bot | grep -E "BUY|SELL|actualizado" || echo "Sin actividad reciente"

# 12. Backup check
echo -e "\n${YELLOW}Último Backup DB:${NC}"
if [ -d "backups" ]; then
    ls -lht backups/*.sql 2>/dev/null | head -1 || echo "Sin backups"
else
    echo "Directorio de backups no configurado"
fi

echo -e "\n${GREEN}=================================="
echo -e "Monitor completado - $(date)${NC}"

# Función para alertas (opcional: integrar con Telegram/Discord)
send_alert() {
    local message="$1"
    # Descomenta y configura según tu servicio de alertas
    # curl -X POST https://api.telegram.org/bot<TOKEN>/sendMessage -d "chat_id=<CHAT_ID>&text=$message"
    echo "ALERTA: $message"
}

# Verificar condiciones críticas
if [ $CPU_USAGE_INT -gt 90 ] || [ $MEMORY_USAGE_INT -gt 90 ]; then
    send_alert "⚠Recursos críticos en trading bot: CPU ${CPU_USAGE}% | MEM ${MEMORY_USAGE}%"
fi