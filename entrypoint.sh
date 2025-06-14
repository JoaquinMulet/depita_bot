#!/bin/bash

# Salir inmediatamente si un comando falla
set -e

echo "Iniciando Entrypoint Script..."

# Carga las variables de entorno definidas en Railway en un archivo
# para que estén disponibles para los trabajos cron.
echo "Exportando variables de entorno a /etc/environment"
printenv | sed 's/=\(.*\)/="\1"/' > /etc/environment

echo "Instalando crontab..."
# Añade el archivo crontab al sistema cron
crontab /app/crontab

# Inicia el demonio de cron y lo mantiene en primer plano.
# El comando `cron -f` es lo que mantiene el contenedor vivo.
# El `tail -f /var/log/cron.log` es una alternativa para ver los logs de cron si es necesario.
echo "Iniciando demonio cron..."
cron -f