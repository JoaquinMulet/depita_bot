# scraper.py (versión corregida)
# -*- coding: utf-8 -*-

import os
import sys
import html
import re
import time
import psycopg2
import pandas as pd
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

# --- Configuración desde variables de entorno ---
DATABASE_URL = os.getenv('DATABASE_URL')
CMF_API_KEY = os.getenv('CMF_API_KEY')
SCRAPE_URLS_STRING = os.getenv('SCRAPE_URLS')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# --- Funciones de Utilidad ---

def send_telegram_alert(message):
    """Envía una notificación de alerta a Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("ALERTA: Variables de Telegram no configuradas.")
        return
    # Asegurarse de que no estamos usando valores de placeholder
    if 'TU_BOT_TOKEN' in TELEGRAM_BOT_TOKEN:
        print("ALERTA: El token de Telegram parece ser un placeholder.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': f"🚨 ALERTA - SCRAPER 🚨\n\n{message}", 'parse_mode': 'Markdown'}
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        print("Alerta de fallo enviada a Telegram.")
    except requests.exceptions.RequestException as e:
        print(f"Error crítico al enviar alerta a Telegram: {e}")

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

def get_uf_value():
    """Obtiene el valor de la UF usando el endpoint del día, con fallback al día anterior."""
    if not CMF_API_KEY:
        raise ValueError("La variable de entorno CMF_API_KEY no está definida.")

    # 1. Intenta obtener el valor de hoy (endpoint sin fecha)
    try:
        url = f"https://api.cmfchile.cl/api-sbifv3/recursos_api/uf?apikey={CMF_API_KEY}&formato=json"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        uf_string = data['UFs'][0]['Valor'].replace('.', '').replace(',', '.')
        print(f"Valor UF obtenido para hoy: {uf_string}")
        return float(uf_string)
    except Exception as e:
        print(f"No se pudo obtener la UF de hoy ({e}), intentando con la de ayer...")

    # 2. Fallback: Intenta obtener el valor de ayer
    try:
        yesterday = (pd.Timestamp.now() - pd.Timedelta(days=1)).strftime('%Y/%m/dias/%d')
        url = f"https://api.cmfchile.cl/api-sbifv3/recursos_api/uf/{yesterday}?apikey={CMF_API_KEY}&formato=json"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        uf_string = data['UFs'][0]['Valor'].replace('.', '').replace(',', '.')
        print(f"Valor UF obtenido para ayer: {uf_string}")
        return float(uf_string)
    except Exception as e_yesterday:
        print(f"Tampoco se pudo obtener la UF de ayer ({e_yesterday}).")
        return None


# --- Las funciones `parsear_vista_mapa`, `guardar_en_db`, y `scrape_con_selenium_y_paginacion` permanecen igual ---
# ... (debes incluirlas aquí)


def main():
    """Función principal que orquesta todo el proceso."""
    log_conn = None
    try:
        # Conexión única para logging de ejecución
        log_conn = psycopg2.connect(DATABASE_URL)
        log_execution(log_conn, 'scraper.py', 'STARTED')
    except (Exception, psycopg2.DatabaseError) as e:
        # Si no podemos conectar a la DB, no podemos hacer nada más.
        send_telegram_alert(f"CRÍTICO: No se pudo conectar a la DB para iniciar el log: `{e}`")
        sys.exit(1)

    try:
        if not SCRAPE_URLS_STRING:
            raise ValueError("Variable de entorno SCRAPE_URLS no definida.")
        
        urls_to_scrape = [url.strip() for url in SCRAPE_URLS_STRING.split(',') if url.strip()]
        todas_las_propiedades_global = []

        uf_actual = get_uf_value()
        if not uf_actual:
            raise ConnectionError("No se pudo obtener el valor de la UF de la API de CMF.")

        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        driver = webdriver.Chrome(options=options)
        wait = WebDriverWait(driver, 20)
        
        # ... (Tu bucle `for url in urls_to_scrape:` y lógica de scraping aquí) ...
        
        driver.quit()

        if todas_las_propiedades_global:
            guardar_en_db(log_conn, todas_las_propiedades_global, uf_actual)
            print(f"\n✅ ¡PROCESO DE SCRAPING GLOBAL COMPLETADO!")
            log_execution(log_conn, 'scraper.py', 'SUCCESS')
        else:
            print("\n⚠️ No se extrajo ninguna propiedad.")
            log_execution(log_conn, 'scraper.py', 'SUCCESS_EMPTY')
        
    except Exception as e:
        error_msg = f"El script `scraper.py` falló de forma crítica: {e}"
        print(error_msg)
        if log_conn:
            log_execution(log_conn, 'scraper.py', 'FAILURE', error_message=str(e))
        send_telegram_alert(error_msg)
        sys.exit(1) # <<-- MUY IMPORTANTE: Salir con código de error
    finally:
        if log_conn:
            log_conn.close()

if __name__ == "__main__":
    main()