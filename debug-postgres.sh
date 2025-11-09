#!/bin/bash
# Script para diagnosticar problemas con PostgreSQL

echo "🔍 Diagnóstico de PostgreSQL"
echo "=============================="

# 1. Verificar archivos de secrets
echo -e "\n1️⃣ Verificando archivos de secrets:"
for file in secrets/db_user.txt secrets/db_password.txt; do
    if [ -f "$file" ]; then
        echo "✅ $file existe"
        echo "   Tamaño: $(wc -c < $file) bytes"
        echo "   Contenido (primeros 20 chars): $(head -c 20 $file)..."
    else
        echo "❌ $file NO existe"
    fi
done

# 2. Ver logs de PostgreSQL
echo -e "\n2️⃣ Logs de PostgreSQL:"
docker logs trading_postgres_db 2>&1 | tail -50

# 3. Intentar conectar manualmente
echo -e "\n3️⃣ Intentando conexión manual:"
docker exec trading_postgres_db pg_isready 2>&1 || echo "❌ PostgreSQL no responde"

# 4. Ver estado del contenedor
echo -e "\n4️⃣ Estado del contenedor:"
docker inspect trading_postgres_db --format='{{.State.Status}}: {{.State.Health.Status}}' 2>&1 || echo "Contenedor no existe"