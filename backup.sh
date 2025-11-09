#!/bin/bash
set -e

# Configuración
BACKUP_DIR="./backups"
RETENTION_DAYS=7
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DB_USER=$(cat secrets/db_user.txt)
DB_NAME="trading_bot"

echo "Iniciando backup de base de datos..."

# Crear directorio de backups
mkdir -p $BACKUP_DIR

# Nombre del archivo de backup
BACKUP_FILE="$BACKUP_DIR/trading_bot_$TIMESTAMP.sql"

# Realizar backup
docker exec trading_postgres_db pg_dump -U $DB_USER $DB_NAME > $BACKUP_FILE

# Comprimir backup
gzip $BACKUP_FILE
echo "Backup creado: ${BACKUP_FILE}.gz"

# Tamaño del backup
BACKUP_SIZE=$(du -h "${BACKUP_FILE}.gz" | cut -f1)
echo "Tamaño: $BACKUP_SIZE"

# Limpiar backups antiguos
echo "Limpiando backups antiguos (> $RETENTION_DAYS días)..."
find $BACKUP_DIR -name "*.sql.gz" -mtime +$RETENTION_DAYS -delete

# Listar backups disponibles
echo "Backups disponibles:"
ls -lh $BACKUP_DIR/*.sql.gz

# Opcional: Subir a Google Cloud Storage
# gsutil cp "${BACKUP_FILE}.gz" gs://tu-bucket/backups/

echo "Backup completado"