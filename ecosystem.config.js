// ecosystem.config.js
module.exports = {
    apps: [
      {
        name: 'scraper-pipeline',
        script: 'scraper.py', // Script principal a ejecutar
        interpreter: 'python3',
        args: '&& python3 analyzer.py', // El siguiente paso del pipeline
        exec_mode: 'fork', // Necesario para que el '&&' funcione
        instances: 1,
        autorestart: false, // No queremos que se reinicie automáticamente
        cron_restart: '0 12 * * *', // Formato cron para ejecutarlo diariamente
        watch: false,
      },
      {
        name: 'monitor',
        script: 'monitor.py',
        interpreter: 'python3',
        exec_mode: 'fork',
        instances: 1,
        autorestart: false,
        cron_restart: '0 14 * * *', // Se ejecuta 2 horas después del pipeline principal
        watch: false,
      },
    ],
  };