# monitor.py
# -*- coding: utf-8 -*-

import os
import psycopg2
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# --- Configuración ---
DATABASE_URL = os.getenv('DATABASE_URL')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

def send_telegram_alert(message):
    # ... (misma función de notificación de alerta)
    pass

def check_last_execution():
    conn = None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        with conn.cursor() as cur:
            # Revisa la última ejecución del scraper
            cur.execute("""
                SELECT script_name, status, start_time, error_message
                FROM log_ejecucion
                WHERE script_name = 'scraper.py'
                ORDER BY start_time DESC
                LIMIT 1;
            """)
            last_run = cur.fetchone()

            if not last_run:
                send_telegram_alert("MONITOR: No se ha encontrado ningún registro de ejecución para `scraper.py`.")
                return

            script_name, status, start_time, error_message = last_run
            
            # Chequea si la última ejecución fue hace mucho tiempo
            if pd.Timestamp.now(tz='utc') - start_time > pd.Timedelta(days=1, hours=2):
                 send_telegram_alert(f"MONITOR: El script `{script_name}` no se ejecuta desde {start_time.strftime('%Y-%m-%d %H:%M')}. ¡Revisar cron job!")
            
            # Chequea si la última ejecución reportó fallo (esto es redundante si el script ya notifica, pero es una buena doble verificación)
            if status == 'FAILURE':
                send_telegram_alert(f"MONITOR: La última ejecución de `{script_name}` falló. Revisa los logs para el error: `{error_message}`")

    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error en el monitor: {error}")
        send_telegram_alert(f"El propio script de monitoreo (`monitor.py`) ha fallado: `{error}`")
    finally:
        if conn: conn.close()

if __name__ == "__main__":
    print("Ejecutando chequeo de monitoreo...")
    check_last_execution()
    print("Chequeo finalizado.")