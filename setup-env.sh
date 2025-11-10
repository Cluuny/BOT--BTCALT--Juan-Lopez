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

# PostgreSQL configuración
POSTGRES_USER="trading_user"
read -p "PostgreSQL Password (dejar vacío para generar): " POSTGRES_PASSWORD
if [ -z "$POSTGRES_PASSWORD" ]; then
    POSTGRES_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)
    echo "✅ Password generado automáticamente: ${POSTGRES_PASSWORD}"
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
POSTGRES_USER=${POSTGRES_USER}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
DB_NAME=${DB_NAME}

# Bot Configuration
MODE=${MODE}
EOF

# Asegurar permisos
chmod 600 .env.production

# Crear directorio para scripts de inicialización
mkdir -p init-scripts

# Crear script de inicialización de base de datos
cat > init-scripts/01-init-db.sql << EOF
-- Script de inicialización de base de datos
-- Se ejecuta automáticamente al crear el contenedor por primera vez

-- Verificar que la base de datos existe
SELECT 'Base de datos creada correctamente' as status;

-- Crear extensiones útiles si es necesario
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Log de inicialización
DO \$\$
BEGIN
    RAISE NOTICE 'Base de datos trading_bot inicializada exitosamente';
END \$\$;
EOF

chmod +x init-scripts/01-init-db.sql

echo -e "\n${GREEN}✅ Configuración completada exitosamente${NC}"
echo -e "${YELLOW}📋 Configuración guardada:${NC}"
echo "  - Usuario DB: ${POSTGRES_USER}"
echo "  - Base de datos: ${DB_NAME}"
echo "  - Modo: ${MODE}"
echo "  - Password DB: ${POSTGRES_PASSWORD}"
echo -e "\n${GREEN}✅ Script de inicialización DB creado en init-scripts/${NC}"
echo -e "\n${RED}⚠️  IMPORTANTE: Guarda estas credenciales de forma segura${NC}"
echo "   No compartas ni subas .env.production a Git"