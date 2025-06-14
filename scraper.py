# scraper.py
# -*- coding: utf-8 -*-

import os
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

# --- Configuración ---
DATABASE_URL = os.getenv('DATABASE_URL')
CMF_API_KEY = os.getenv('CMF_API_KEY')
SCRAPE_URLS_STRING = os.getenv('SCRAPE_URLS')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# --- Funciones de Utilidad y Parseo ---

def send_telegram_alert(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Variables de Telegram no configuradas para alerta.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': f"🚨 ALERTA - SCRAPER 🚨\n\n{message}", 'parse_mode': 'Markdown'}
    try:
        requests.post(url, json=payload, timeout=10).raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error crítico al enviar alerta a Telegram: {e}")

def log_ejecucion_db(conn, script_name, status, error_message=None):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO log_ejecucion (script_name, start_time, status, error_message)
            VALUES (%s, %s, %s, %s) RETURNING id
            """,
            (script_name, pd.Timestamp.now(tz='utc'), status, error_message)
        )
        log_id = cur.fetchone()[0]
        conn.commit()
        return log_id

def update_log_ejecucion_db(conn, log_id, status, error_message=None):
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE log_ejecucion SET end_time = %s, status = %s, error_message = %s
            WHERE id = %s
            """,
            (pd.Timestamp.now(tz='utc'), status, error_message, log_id)
        )
        conn.commit()

# ... (Tu función parsear_vista_mapa, aquí. Asegúrate que extraiga 'moneda' y 'valor_numerico') ...

def get_uf_value():
    if not CMF_API_KEY:
        raise ValueError("La variable de entorno CMF_API_KEY no está definida.")
    try:
        today = pd.Timestamp.now().strftime('%Y/%m/dias/%d')
        url = f"https://api.cmfchile.cl/api-sbifv3/recursos_api/uf/{today}?apikey={CMF_API_KEY}&formato=json"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        uf_string = data['UFs'][0]['Valor'].replace('.', '').replace(',', '.')
        return float(uf_string)
    except Exception as e:
        print(f"Error al obtener valor de la UF: {e}")
        return None

def guardar_en_db(conn, propiedades, uf_valor):
    nuevas_observaciones = 0
    with conn.cursor() as cur:
        for prop in propiedades:
            cur.execute("SELECT id FROM propiedades WHERE link = %s", (prop.get('link'),))
            result = cur.fetchone()
            propiedad_id = result[0] if result else cur.execute(
                "INSERT INTO propiedades (link, ubicacion, titulo) VALUES (%s, %s, %s) RETURNING id",
                (prop.get('link'), prop.get('ubicacion'), prop.get('titulo'))
            ) or cur.fetchone()[0]

            precio_uf = (prop.get('valor_numerico') / uf_valor) if prop.get('moneda') == '$' and uf_valor else \
                        prop.get('valor_numerico') if prop.get('moneda') == 'UF' else None
            
            cur.execute(
                """
                INSERT INTO observaciones_venta (propiedad_id, precio_clp, precio_uf, superficie_util_m2, dormitorios, atributos_raw, imagen_url) 
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (propiedad_id, prop.get('valor_numerico') if prop.get('moneda') == '$' else None, precio_uf,
                 prop.get('superficie_util_m2'), prop.get('dormitorios'), prop.get('atributos_raw'), prop.get('imagen_url'))
            )
            nuevas_observaciones += 1
        conn.commit()
    print(f"Se guardaron/actualizaron {nuevas_observaciones} observaciones.")

def scrape_url(url, driver, wait):
    # ... (Tu lógica de scraping para una sola URL, paginando con el botón 'Siguiente')
    pass

def main():
    if not SCRAPE_URLS_STRING:
        raise ValueError("La variable de entorno SCRAPE_URLS no está definida.")
    
    urls_to_scrape = [url.strip() for url in SCRAPE_URLS_STRING.split(',')]
    todas_las_propiedades_global = []

    conn = psycopg2.connect(DATABASE_URL)
    log_id = log_ejecucion_db(conn, 'scraper.py', 'STARTED')

    try:
        uf_actual = get_uf_value()
        if not uf_actual:
            raise ConnectionError("No se pudo obtener el valor de la UF.")

        options = webdriver.ChromeOptions()
        # ... (Tus opciones headless, no-sandbox, etc.)
        driver = webdriver.Chrome(options=options)
        wait = WebDriverWait(driver, 20)
        
        try:
            for url in urls_to_scrape:
                todas_las_propiedades_global.extend(scrape_url(url, driver, wait))
        finally:
            driver.quit()

        if todas_las_propiedades_global:
            guardar_en_db(conn, todas_las_propiedades_global, uf_actual)
        else:
            print("No se encontraron propiedades nuevas.")
        
        update_log_ejecucion_db(conn, log_id, 'SUCCESS')
    except Exception as e:
        print(f"ERROR CRÍTICO: {e}")
        update_log_ejecucion_db(conn, log_id, 'FAILURE', error_message=str(e))
        send_telegram_alert(f"El script `scraper.py` falló:\n`{e}`")
    finally:
        conn.close()

if __name__ == "__main__":
    main()