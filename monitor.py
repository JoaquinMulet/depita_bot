# monitor.py (versión final y adaptada)
# -*- coding: utf-8 -*-

import os
import sys
import re
import psycopg2
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# --- Configuración ---
DATABASE_URL = os.getenv('DATABASE_URL')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# --- CONFIGURACIÓN DE MONITOREO ---
# Define aquí los scripts que quieres vigilar y su umbral de alerta en horas.
# Si un script no se ha ejecutado exitosamente en este lapso, se enviará una alerta.
SCRIPTS_A_VIGILAR = {
    'scraper.py': 26,   # Alerta si no ha corrido en 26 horas
    'analyzer.py': 26,  # Alerta si no ha corrido en 26 horas
}

# --- Funciones de Utilidad ---

def escape_markdown_v2(text: str) -> str:
    """Escapa caracteres especiales para el formato MarkdownV2 de Telegram."""
    if not isinstance(text, str):
        return ""
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

def send_telegram_alert(message: str):
    """Envía una notificación de alerta formateada a Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("ALERTA: Variables de Telegram no configuradas.")
        return

    # Construimos el mensaje final con el formato de alerta
    # Escapamos el contenido del mensaje para seguridad
    full_message_escaped = f"🚨 *ALERTA DEL MONITOR* 🚨\n\n{escape_markdown_v2(message)}"

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': full_message_escaped,
        'parse_mode': 'MarkdownV2'
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        print(f"-> Alerta de monitoreo enviada a Telegram.")
    except requests.exceptions.RequestException as e:
        print(f"Error al enviar alerta a Telegram: {e}")
        if e.response is not None:
            print(f"Respuesta de la API de Telegram: {e.response.text}")


def check_script_health(conn, script_name, threshold_hours):
    """
    Verifica la salud de un script específico basado en su último log de ejecución.
    Devuelve True si está saludable, False si se envió una alerta.
    """
    print(f"--- Verificando salud de `{script_name}`...")
    with conn.cursor() as cur:
        cur.execute("""
            SELECT status, start_time, error_message
            FROM log_ejecucion
            WHERE script_name = %s
            ORDER BY start_time DESC
            LIMIT 1;
        """, (script_name,))
        last_run = cur.fetchone()

        # Caso 1: El script nunca se ha ejecutado
        if not last_run:
            msg = f"No se ha encontrado ningún registro de ejecución para `{script_name}`."
            send_telegram_alert(msg)
            print(f"ALERTA: {msg}")
            return False

        status, start_time, error_message = last_run
        
        # Calculamos el tiempo transcurrido desde la última ejecución
        time_since_run = pd.Timestamp.now(tz='utc') - start_time
        
        # Caso 2: La última ejecución fue hace demasiado tiempo
        if time_since_run > pd.Timedelta(hours=threshold_hours):
            days = time_since_run.days
            hours = time_since_run.seconds // 3600
            msg = (f"El script `{script_name}` no se ejecuta desde hace {days} día(s) y {hours} hora(s) "
                   f"(última vez: {start_time.strftime('%Y-%m-%d %H:%M')} UTC). ¡Revisar el scheduler (cron job)!")
            send_telegram_alert(msg)
            print(f"ALERTA: {msg}")
            return False
        
        # Caso 3: La última ejecución falló
        if status == 'FAILURE':
            msg = (f"La última ejecución de `{script_name}` falló.\n"
                   f"Revisa los logs para el error: `{error_message or 'No hay mensaje de error.'}`")
            send_telegram_alert(msg)
            print(f"ALERTA: {msg}")
            return False

        # Si todo está bien
        print(f"OK: Última ejecución exitosa fue hace {time_since_run.seconds // 3600} horas y {(time_since_run.seconds % 3600) // 60} minutos.")
        return True


def main():
    """Función principal que orquesta el monitoreo de todos los scripts definidos."""
    print("=============================================")
    print(" Ejecutando Chequeo de Monitoreo del Sistema ")
    print(f" Hora actual: {pd.Timestamp.now(tz='America/Santiago').strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print("=============================================")
    
    conn = None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        
        problemas_encontrados = False
        for script, threshold in SCRIPTS_A_VIGILAR.items():
            if not check_script_health(conn, script, threshold):
                problemas_encontrados = True
        
        print("---------------------------------------------")
        if problemas_encontrados:
            print("Resultado: Se encontraron problemas. Revise las alertas enviadas.")
        else:
            print("Resultado: Todos los sistemas monitoreados operan normalmente.")
        print("---------------------------------------------")

    except (Exception, psycopg2.DatabaseError) as error:
        error_msg = f"El propio script de monitoreo (`monitor.py`) ha fallado: `{error}`"
        print(f"ERROR CRÍTICO: {error_msg}")
        send_telegram_alert(error_msg)
    finally:
        if conn:
            conn.close()
            print("Conexión a la base de datos cerrada.")

if __name__ == "__main__":
    main()