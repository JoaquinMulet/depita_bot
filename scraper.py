# scraper.py
# -*- coding: utf-8 -*-
# /// script
# python-version = ">=3.11"
# dependencies = [
#    "psycopg2",
#    "pandas",
#    "requests",
#    "selenium",
#    "beautifulsoup4",
#    "python-dotenv",
# ]
# ///

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
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

# --- Configuración ---
DATABASE_URL = os.getenv('DATABASE_URL')
CMF_API_KEY = os.getenv('CMF_API_KEY')
SCRAPE_URLS_STRING = os.getenv('SCRAPE_URLS')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# --- Funciones de Utilidad y DB ---

def send_telegram_alert(message):
    """Envía una notificación de alerta a Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("ALERTA: Variables de Telegram no configuradas.")
        return
    if 'TU_BOT_TOKEN' in TELEGRAM_BOT_TOKEN:
        print("ALERTA: El token de Telegram parece ser un placeholder.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': f"🚨 ALERTA - SCRAPER 🚨\n\n{message}", 'parse_mode': 'Markdown'}
    try:
        requests.post(url, json=payload, timeout=10).raise_for_status()
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
    # Intenta obtener el valor de hoy (endpoint sin fecha)
    try:
        url = f"https://api.cmfchile.cl/api-sbifv3/recursos_api/uf?apikey={CMF_API_KEY}&formato=json"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        uf_string = data['UFs'][0]['Valor'].replace('.', '').replace(',', '.')
        return float(uf_string)
    except Exception:
        # Fallback: Intenta obtener el valor de ayer
        try:
            yesterday = (pd.Timestamp.now() - pd.Timedelta(days=1)).strftime('%Y/%m/dias/%d')
            url = f"https://api.cmfchile.cl/api-sbifv3/recursos_api/uf/{yesterday}?apikey={CMF_API_KEY}&formato=json"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            uf_string = data['UFs'][0]['Valor'].replace('.', '').replace(',', '.')
            return float(uf_string)
        except Exception:
            return None

def guardar_en_db(conn, propiedades, uf_valor):
    """Guarda las propiedades scrapeadas en la base de datos."""
    nuevas_observaciones = 0
    with conn.cursor() as cur:
        for prop in propiedades:
            # 1. Buscar o insertar la propiedad para obtener su ID
            cur.execute("SELECT id FROM propiedades WHERE link = %s", (prop.get('link'),))
            result = cur.fetchone()
            if result:
                propiedad_id = result[0]
            else:
                cur.execute(
                    "INSERT INTO propiedades (link, ubicacion, titulo) VALUES (%s, %s, %s) RETURNING id",
                    (prop.get('link'), prop.get('ubicacion'), prop.get('titulo'))
                )
                propiedad_id = cur.fetchone()[0]

            # 2. Convertir precio a UF si es necesario
            precio_uf = None
            if prop.get('moneda') == '$' and uf_valor:
                precio_uf = prop.get('valor_numerico', 0) / uf_valor
            elif prop.get('moneda') == 'UF':
                precio_uf = prop.get('valor_numerico')
            
            # 3. Insertar la nueva observación
            cur.execute(
                """
                INSERT INTO observaciones_venta (propiedad_id, precio_clp, precio_uf, superficie_util_m2, dormitorios, atributos_raw, imagen_url) 
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (propiedad_id, 
                 prop.get('valor_numerico') if prop.get('moneda') == '$' else None, 
                 precio_uf,
                 prop.get('superficie_util_m2'), 
                 prop.get('dormitorios'), 
                 prop.get('atributos_raw'), 
                 prop.get('imagen_url'))
            )
            nuevas_observaciones += 1
    conn.commit()
    print(f"Se guardaron {nuevas_observaciones} observaciones en la base de datos.")

# --- LÓGICA DE SCRAPING PRINCIPAL ---

def parsear_vista_mapa(html_content):
    """
    Función de parseo refinada para los resultados de la VISTA DE MAPA.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    listings = soup.select('div.ui-search-map-list__item')
    propiedades_pagina = []
    for listing in listings:
        property_data = {}
        try:
            property_data['titulo'] = html.unescape(listing.find('h2', class_='ui-search-item__title').text.strip())
            property_data['link'] = listing.find('a', class_='ui-search-result__content-link')['href']
            
            price_container = listing.find('div', class_='ui-search-price__second-line')
            property_data['moneda'] = price_container.find(class_='andes-money-amount__currency-symbol').text.strip()
            amount = price_container.find(class_='andes-money-amount__fraction').text.strip()
            property_data['valor_numerico'] = float(amount.replace('.', '').replace(',', ''))
            
            raw_attributes = listing.find('div', class_='ui-search-result__content-attributes').text.strip()
            area_search = re.search(r'(\d+[\.,]?\d*)\s*m²\s*útiles', raw_attributes) or re.search(r'(\d+[\.,]?\d*)\s*m²', raw_attributes)
            dorms_search = re.search(r'(\d+)\s*dorm', raw_attributes)
            
            property_data['superficie_util_m2'] = float(area_search.group(1).replace(',', '.')) if area_search else None
            property_data['dormitorios'] = int(dorms_search.group(1)) if dorms_search else None
            property_data['atributos_raw'] = raw_attributes
            
            property_data['ubicacion'] = listing.find('div', class_='ui-search-result__content-location').text.strip()
            
            img_tag = listing.find('img', class_='ui-search-result__main-image-internal')
            property_data['imagen_url'] = img_tag.get('data-src', img_tag.get('src'))

            propiedades_pagina.append(property_data)
        except (AttributeError, TypeError):
            # Si falta algún campo esencial, omitimos esta propiedad
            continue
            
    return propiedades_pagina

def scrape_url(url, driver, wait):
    """
    Scraper robusto que navega una URL, paginando y extrayendo todas las propiedades.
    """
    print(f"\n>>>> Iniciando scraping para la URL: {url[:80]}...")
    driver.get(url)
    
    # Manejo del banner de cookies, solo si aparece
    try:
        cookie_button = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Entendido')]")))
        cookie_button.click()
        print("Banner de cookies cerrado.")
    except TimeoutException:
        print("No se encontró el banner de cookies, continuando...")

    todas_las_propiedades_de_url = []
    pagina_actual = 1

    while True:
        print(f"--- Procesando Página {pagina_actual} de la URL actual ---")
        
        try:
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "ui-search-map-list__item")))
            time.sleep(3) # Espera extra para que cargue todo el contenido dinámico
        except TimeoutException:
            print("No se encontraron más resultados en esta página. Finalizando esta URL.")
            break
            
        propiedades_de_esta_pagina = parsear_vista_mapa(driver.page_source)
        
        if not propiedades_de_esta_pagina and pagina_actual > 1:
            print("La función de parseo no extrajo propiedades. Puede ser el final.")
            break

        # Lógica anti-duplicados para evitar bucles infinitos
        links_ya_guardados = {p['link'] for p in todas_las_propiedades_de_url}
        nuevas_propiedades = [p for p in propiedades_de_esta_pagina if p.get('link') not in links_ya_guardados]
        
        if not nuevas_propiedades and pagina_actual > 1:
             print("No se encontraron propiedades nuevas en esta página. Finalizando esta URL.")
             break
        
        print(f"Se extrajeron {len(nuevas_propiedades)} propiedades nuevas.")
        todas_las_propiedades_de_url.extend(nuevas_propiedades)
        
        # Navegar a la siguiente página
        try:
            boton_siguiente = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "li.andes-pagination__button--next a")))
            driver.execute_script("arguments[0].scrollIntoView(true);", boton_siguiente)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", boton_siguiente)
            pagina_actual += 1
        except TimeoutException:
            print("No se encontró el botón 'Siguiente' activo. Se ha llegado a la última página de esta URL.")
            break
            
    return todas_las_propiedades_de_url

def main():
    """Función principal que orquesta todo el proceso."""
    log_conn = None
    try:
        log_conn = psycopg2.connect(DATABASE_URL)
        log_execution(log_conn, 'scraper.py', 'STARTED')
    except (Exception, psycopg2.DatabaseError) as e:
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
        options.add_argument("window-size=1920,1080")
        
        driver = webdriver.Chrome(options=options)
        wait = WebDriverWait(driver, 20)
        
        for url in urls_to_scrape:
            try:
                propiedades_de_url = scrape_url(url, driver, wait)
                todas_las_propiedades_global.extend(propiedades_de_url)
            except Exception as e:
                print(f"Error procesando URL {url[:80]}: {e}")
                send_telegram_alert(f"Falló el scraping para una URL:\n`{url}`\nError: `{e}`")
        
        driver.quit()

        if todas_las_propiedades_global:
            guardar_en_db(log_conn, todas_las_propiedades_global, uf_actual)
            print(f"\n✅ ¡PROCESO DE SCRAPING GLOBAL COMPLETADO!")
            log_execution(log_conn, 'scraper.py', 'SUCCESS')
        else:
            print("\n⚠️ No se extrajo ninguna propiedad en ninguna de las URLs.")
            log_execution(log_conn, 'scraper.py', 'SUCCESS_EMPTY')
        
    except Exception as e:
        error_msg = f"El script `scraper.py` falló de forma crítica: {e}"
        print(error_msg)
        if log_conn:
            log_execution(log_conn, 'scraper.py', 'FAILURE', error_message=str(e))
        send_telegram_alert(error_msg)
        sys.exit(1)
    finally:
        if log_conn:
            log_conn.close()

if __name__ == "__main__":
    main()