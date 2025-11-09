#!/bin/bash
# Script para limpiar y reiniciar desde cero

set -e

RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${RED}⚠️  Este script eliminará todos los contenedores y volúmenes${NC}"
read -p "¿Estás seguro? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 0
fi

echo -e "${YELLOW}🧹 Limpiando...${NC}"

# Detener y eliminar contenedores
docker compose -f docker-compose.prod.yml down -v 2>/dev/null || true

# Limpiar imágenes
docker rmi bot--btcalt--juan-lopez-trading-bot 2>/dev/null || true

# Limpiar sistema
docker system prune -f

echo -e "${YELLOW}✅ Limpieza completada${NC}"
echo "Ahora puedes ejecutar: ./deploy.sh"