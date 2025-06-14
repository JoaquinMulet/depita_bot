# analyzer.py
# -*- coding: utf-8 -*-

import os
import sys
import psycopg2
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# --- Configuración ---
DATABASE_URL = os.getenv('DATABASE_URL')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# --- Funciones de Utilidad ---

def send_telegram_notification(message):
    """Envía un mensaje de notificación de nuevas propiedades a Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Variables de Telegram no configuradas. Omitiendo notificación.")
        return
    if 'TU_BOT_TOKEN' in TELEGRAM_BOT_TOKEN:
        print("ALERTA: El token de Telegram parece ser un placeholder.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'Markdown',
        'disable_web_page_preview': True
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        print("Notificación de nuevas propiedades enviada a Telegram.")
    except requests.exceptions.RequestException as e:
        print(f"Error al enviar notificación de Telegram: {e}")

def send_telegram_alert(message):
    """Envía una notificación de alerta de fallo a Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("ALERTA: Variables de Telegram no configuradas.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': f"🚨 ALERTA - ANALYZER 🚨\n\n{message}", 'parse_mode': 'Markdown'}
    try:
        requests.post(url, json=payload, timeout=10).raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error crítico al enviar alerta de fallo a Telegram: {e}")

def log_execution(conn, script_name, status, error_message=None):
    """Registra el estado de una ejecución en la base de datos."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO log_ejecucion (script_name, start_time, end_time, status, error_message)
            VALUES (%s, %s, %s, %s, %s);
            """,
            (script_name, pd.Timestamp.now(tz='utc'), pd.Timestamp.now(tz='utc'), status, error_message)
        )
        conn.commit()

# --- Función Principal ---

def main():
    """
    Procesa nuevas observaciones, calcula métricas, y notifica sobre nuevas propiedades.
    """
    conn = None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        log_execution(conn, 'analyzer.py', 'STARTED')
    except (Exception, psycopg2.DatabaseError) as e:
        send_telegram_alert(f"CRÍTICO: No se pudo conectar a la DB para el análisis: `{e}`")
        sys.exit(1)

    try:
        with conn.cursor() as cur:
            # 1. Procesar nuevas observaciones para calcular métricas
            cur.execute("""
                SELECT o.id, o.precio_uf, o.superficie_util_m2 
                FROM observaciones_venta o
                WHERE o.es_nueva = TRUE;
            """)
            
            observaciones_para_procesar = cur.fetchall()
            if not observaciones_para_procesar:
                print("No hay nuevas observaciones para procesar.")
                log_execution(conn, 'analyzer.py', 'SUCCESS_EMPTY')
                return # Salir limpiamente si no hay nada que hacer

            for obs_id, precio_uf, superficie in observaciones_para_procesar:
                if precio_uf and superficie and superficie > 0:
                    uf_por_m2 = round(precio_uf / superficie, 2)
                    cur.execute(
                        "INSERT INTO metricas_historicas (observacion_id, uf_por_m2) VALUES (%s, %s)",
                        (obs_id, uf_por_m2)
                    )
            
            # 2. Identificar propiedades que son genuinamente nuevas para la notificación
            # (aquellas que solo tienen una observación, y esa observación es nueva)
            cur.execute("""
                SELECT p.titulo, p.link, o.precio_uf
                FROM propiedades p
                JOIN observaciones_venta o ON p.id = o.propiedad_id
                WHERE o.es_nueva = TRUE
                AND (SELECT COUNT(*) FROM observaciones_venta WHERE propiedad_id = p.id) = 1;
            """)
            propiedades_nuevas = cur.fetchall()

            if propiedades_nuevas:
                message = f"🔔 *{len(propiedades_nuevas)} Propiedad(es) Nueva(s) Detectada(s)* 🔔\n\n"
                for titulo, link, precio in propiedades_nuevas:
                    # Formatea el precio y escapa caracteres de Markdown
                    precio_formateado = f"{precio:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                    titulo_escapado = titulo.replace('[', '\\[').replace(']', '\\]')
                    message += f"🏠 [{titulo_escapado}]({link})\n   *Precio:* {precio_formateado} UF\n\n"
                
                send_telegram_notification(message)

            # 3. Marcar todas las observaciones procesadas como no nuevas
            cur.execute("UPDATE observaciones_venta SET es_nueva = FALSE WHERE es_nueva = TRUE;")
            conn.commit()

        print(f"Análisis completado. {len(observaciones_para_procesar)} observaciones procesadas.")
        log_execution(conn, 'analyzer.py', 'SUCCESS')

    except (Exception, psycopg2.DatabaseError) as error:
        error_msg = f"Error durante el análisis: {error}"
        print(error_msg)
        if conn: conn.rollback()
        log_execution(conn, 'analyzer.py', 'FAILURE', error_message=str(error))
        send_telegram_alert(error_msg)
        sys.exit(1)
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    main()