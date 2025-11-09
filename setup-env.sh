#!/bin/bash
set -e

# Colores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}🔧 Configurando variables de entorno${NC}"

# Verificar si .env.production ya existe
if [ -f ".env.production" ]; then
    echo -e "${YELLOW}⚠️  .env.production ya existe${NC}"
    read -p "¿Quieres sobrescribirlo? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Operación cancelada"
        exit 0
    fi
fi

# Solicitar credenciales
echo -e "\n${YELLOW}📝 Ingresa las credenciales:${NC}"

read -p "Binance API Key: " BINANCE_API_KEY
read -sp "Binance API Secret: " BINANCE_API_SECRET
echo

read -p "PostgreSQL Password (dejar vacío para generar): " POSTGRES_PASSWORD
if [ -z "$POSTGRES_PASSWORD" ]; then
    POSTGRES_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)
    echo "✅ Password generado automáticamente"
fi

read -p "Nombre de la base de datos [trading_bot]: " DB_NAME
DB_NAME=${DB_NAME:-trading_bot}

read -p "Modo de operación (REAL/TEST) [REAL]: " MODE
MODE=${MODE:-REAL}

# Crear archivo .env.production
cat > .env.production << EOF
# Trading Bot - Production Environment Variables
# Generado: $(date)

# Binance API
BINANCE_API_KEY=${BINANCE_API_KEY}
BINANCE_API_SECRET=${BINANCE_API_SECRET}

# Database
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
DB_NAME=${DB_NAME}

# Bot Configuration
MODE=${MODE}
EOF

# Asegurar permisos
chmod 600 .env.production

echo -e "\n${GREEN}✅ Archivo .env.production creado exitosamente${NC}"
echo -e "${YELLOW}📋 Configuración guardada:${NC}"
echo "  - Base de datos: ${DB_NAME}"
echo "  - Modo: ${MODE}"
echo "  - Password DB: ${POSTGRES_PASSWORD}"
echo -e "\n${RED}⚠️  IMPORTANTE: Este archivo contiene información sensible${NC}"
echo "   No lo compartas ni lo subas a Git"