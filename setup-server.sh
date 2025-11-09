#!/bin/bash
set -e

echo "Configurando servidor Ubuntu 24.04 LTS para Trading Bot"

# 1. Actualizar sistema
echo "Actualizando paquetes del sistema..."
sudo apt-get update
sudo apt-get upgrade -y

# 2. Instalar Docker
echo "Instalando Docker..."
sudo apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

# Agregar GPG key oficial de Docker
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Configurar repositorio
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Instalar Docker Engine
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# 3. Agregar usuario actual al grupo docker
echo "Configurando permisos de usuario..."
sudo usermod -aG docker $USER

# 4. Configurar firewall
echo "Configurando firewall..."
sudo apt-get install -y ufw
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 22/tcp
sudo ufw --force enable

# 5. Configurar límites del sistema
echo "Optimizando configuración del sistema..."
cat << EOF | sudo tee -a /etc/sysctl.conf
# Optimizaciones para trading bot
vm.swappiness=10
net.core.somaxconn=1024
net.ipv4.tcp_max_syn_backlog=2048
fs.file-max=65536
EOF
sudo sysctl -p

# 6. Configurar swap (para recursos limitados)
if [ ! -f /swapfile ]; then
    echo "Creando swap de 2GB..."
    sudo fallocate -l 2G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
fi

# 7. Instalar herramientas de monitoreo
echo "Instalando herramientas de monitoreo..."
sudo apt-get install -y htop iotop nethogs

# 8. Configurar logs rotation
echo "Configurando rotación de logs..."
cat << 'EOF' | sudo tee /etc/logrotate.d/trading-bot
/home/*/trading-bot/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    notifempty
    create 0640 $USER $USER
    sharedscripts
}
EOF

# 9. Crear directorio del proyecto
echo "Creando estructura de directorios..."
mkdir -p ~/trading-bot
cd ~/trading-bot

# 10. Configurar auto-start con systemd
echo "Configurando auto-start..."
cat << EOF | sudo tee /etc/systemd/system/trading-bot.service
[Unit]
Description=Trading Bot Docker Compose
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/home/$USER/trading-bot
ExecStart=/usr/bin/docker compose -f docker-compose.prod.yml up -d
ExecStop=/usr/bin/docker compose -f docker-compose.prod.yml down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable trading-bot.service

# 11. Instalar fail2ban para protección SSH
echo "Instalando fail2ban..."
sudo apt-get install -y fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban

# 12. Configurar unattended-upgrades
echo "Configurando actualizaciones automáticas..."
sudo apt-get install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades

echo ""
echo "Servidor configurado exitosamente!"
echo ""
echo "IMPORTANTE: Cierra sesión y vuelve a entrar para aplicar permisos de Docker"
echo ""
echo "Próximos pasos:"
echo "  1. Clona tu repositorio en ~/trading-bot"
echo "  2. Crea los archivos de secrets en ~/trading-bot/secrets/"
echo "  3. Ejecuta ./deploy.sh"