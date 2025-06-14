# scraper.py (versión con llave compuesta título/precio)
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
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

# --- Configuración desde variables de entorno ---
DATABASE_URL = os.getenv('DATABASE_URL')
CMF_API_KEY = os.getenv('CMF_API_KEY')
SCRAPE_URLS_STRING = os.getenv('SCRAPE_URLS')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')


def escape_markdown_v2(text: str) -> str:
    """Escapa los caracteres especiales para el formato MarkdownV2 de Telegram."""
    if not isinstance(text, str):
        return ""
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    # La siguiente línea está modificada para evitar un error común de 're'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

def send_telegram_notification(message: str):
    """Envía una notificación de propiedad encontrada. El mensaje ya debe venir escapado."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message, # Se asume que el mensaje ya está formateado y escapado
        'parse_mode': 'MarkdownV2',
        'disable_web_page_preview': False
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        print("-> Notificación de propiedad enviada a Telegram.")
    except requests.exceptions.RequestException as e:
        print(f"-> Error enviando notificación a Telegram: {e}")
        if e.response is not None:
            print(f"-> Respuesta de API: {e.response.text}")


def send_telegram_alert(message):
    """Envía una alerta de error."""
    error_message_text = f"🚨 *ALERTA - SCRAPER* 🚨\n\n{message}"
    # Escapamos el mensaje de error completo antes de enviarlo
    send_telegram_notification(escape_markdown_v2(error_message_text))


def log_execution(conn, script_name, status, error_message=None):
    # (Sin cambios en esta función)
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
    # (Sin cambios en esta función)
    if not CMF_API_KEY: raise ValueError("CMF_API_KEY no definida.")
    try:
        today = pd.Timestamp.now().strftime('%Y/%m/dias/%d')
        url = f"https://api.cmfchile.cl/api-sbifv3/recursos_api/uf/{today}?apikey={CMF_API_KEY}&formato=json"
        data = requests.get(url, timeout=10).json()
        return float(data['UFs'][0]['Valor'].replace('.', '').replace(',', '.'))
    except Exception:
        try:
            yesterday = (pd.Timestamp.now() - pd.Timedelta(days=1)).strftime('%Y/%m/dias/%d')
            url = f"https://api.cmfchile.cl/api-sbifv3/recursos_api/uf/{yesterday}?apikey={CMF_API_KEY}&formato=json"
            data = requests.get(url, timeout=10).json()
            return float(data['UFs'][0]['Valor'].replace('.', '').replace(',', '.'))
        except Exception: return None

# ==============================================================================
# FUNCIÓN MODIFICADA
# ==============================================================================
def guardar_en_db(conn, propiedades, uf_valor):
    """
    Guarda las propiedades en la base de datos siguiendo la lógica de la llave
    compuesta (título, precio_uf).
    """
    nuevas_observaciones = 0
    with conn.cursor() as cur:
        for prop in propiedades:
            # Normalizamos el título para consistencia (quita espacios al inicio/final)
            titulo_prop = prop.get('titulo', 'Sin título').strip()

            # Calculamos el precio en UF para esta observación
            precio_uf_actual = None
            if prop.get('moneda') == '$' and uf_valor:
                # Usamos round para evitar problemas con decimales largos
                precio_uf_actual = round(prop.get('valor_numerico', 0) / uf_valor, 2)
            elif prop.get('moneda') == 'UF':
                precio_uf_actual = prop.get('valor_numerico')

            # Si no se pudo determinar un precio en UF, no podemos procesar esta propiedad
            # porque el precio es parte de nuestra llave única.
            if precio_uf_actual is None:
                print(f"-> Propiedad omitida (no se pudo calcular precio en UF): {titulo_prop}")
                continue

            # Paso 1: Buscamos si la combinación exacta de (título, precio) ya existe.
            cur.execute(
                "SELECT id FROM propiedades WHERE titulo = %s AND precio_uf = %s",
                (titulo_prop, precio_uf_actual)
            )
            propiedad_existente = cur.fetchone()

            propiedad_id = None

            if propiedad_existente:
                # --- LÓGICA SI LA COMBINACIÓN (TÍTULO, PRECIO) YA EXISTE ---
                propiedad_id = propiedad_existente[0]
                print(f"-> Combinación Título/Precio ya existente, no se notifica: {titulo_prop}")

            else:
                # --- LÓGICA SI ES UNA COMBINACIÓN (TÍTULO, PRECIO) NUEVA ---
                print(f"NUEVA COMBINACIÓN TÍTULO/PRECIO ENCONTRADA: {titulo_prop}")
                
                # 1. La insertamos en nuestra tabla 'propiedades' para registrarla como única.
                cur.execute(
                    "INSERT INTO propiedades (titulo, ubicacion, precio_uf) VALUES (%s, %s, %s) RETURNING id",
                    (titulo_prop, prop.get('ubicacion'), precio_uf_actual)
                )
                propiedad_id = cur.fetchone()[0]

                # 2. Enviamos la notificación de "Nueva Propiedad/Precio"
                superficie_str = f"{prop.get('superficie_util_m2')} m²" if prop.get('superficie_util_m2') else "No especificada"
                precio_str = f"{precio_uf_actual:,.2f} UF".replace(",", "X").replace(".", ",").replace("X", ".")

                mensaje_telegram = (
                    f"🏠 *Nueva Propiedad/Precio Detectado*\n\n"
                    f"*{escape_markdown_v2(titulo_prop)}*\n\n"
                    f"💵 *Precio:* {escape_markdown_v2(precio_str)}\n"
                    f"📏 *Superficie:* {escape_markdown_v2(superficie_str)}\n\n"
                    f"[Ver en el portal]({prop.get('link', '')})"
                )
                send_telegram_notification(mensaje_telegram)


            # Finalmente, SIEMPRE insertamos la observación detallada
            if propiedad_id:
                cur.execute(
                    """
                    INSERT INTO observaciones_venta (propiedad_id, precio_clp, precio_uf, superficie_util_m2, dormitorios, link, atributos_raw, imagen_url, es_nueva) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE)
                    """,
                    (
                        propiedad_id,
                        prop.get('valor_numerico') if prop.get('moneda') == '$' else None,
                        precio_uf_actual,
                        prop.get('superficie_util_m2'),
                        prop.get('dormitorios'),
                        prop.get('link'),
                        prop.get('atributos_raw'),
                        prop.get('imagen_url')
                    )
                )
                nuevas_observaciones += 1
            
    conn.commit()
    print(f"\nSe guardaron {nuevas_observaciones} observaciones en la base de datos.")
# ==============================================================================


def parsear_vista_mapa(html_content):
    # (Sin cambios en esta función)
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
            continue
    return propiedades_pagina


def scrape_url(url, driver, wait, max_retries=2):
    # (Sin cambios en esta función)
    print(f"\n>>>> Iniciando scraping para la URL: {url[:80]}...")
    
    for attempt in range(max_retries):
        try:
            driver.get(url)
            
            try:
                cookie_button = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Entendido')]")))
                cookie_button.click()
                print("Banner de cookies cerrado.")
            except TimeoutException:
                print("No se encontró el banner de cookies, continuando...")

            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.ui-search-map-list")))
            
            todas_las_propiedades_de_url = []
            pagina_actual = 1
            
            while True:
                print(f"--- Procesando Página {pagina_actual} ---")
                
                try:
                    wait.until(EC.visibility_of_element_located((By.CLASS_NAME, "ui-search-map-list__item")))
                except TimeoutException:
                    print("Timeout esperando los items de la lista. Puede que la página no tenga resultados.")
                    break 
                
                time.sleep(1) 

                propiedades_de_esta_pagina = parsear_vista_mapa(driver.page_source)
                
                links_ya_vistos_en_esta_sesion = {p['link'] for p in todas_las_propiedades_de_url}
                nuevas_propiedades = [p for p in propiedades_de_esta_pagina if p.get('link') and p.get('link') not in links_ya_vistos_en_esta_sesion]
                
                if not nuevas_propiedades and pagina_actual > 1:
                    print("No se encontraron propiedades nuevas en esta página. Asumiendo fin de la paginación.")
                    break
                
                todas_las_propiedades_de_url.extend(nuevas_propiedades)
                print(f"Extraídas {len(nuevas_propiedades)} propiedades nuevas.")
                
                try:
                    boton_siguiente = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "li.andes-pagination__button--next a")))
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", boton_siguiente)
                    time.sleep(0.5)
                    boton_siguiente.click()
                    pagina_actual += 1
                except TimeoutException:
                    print("Última página alcanzada (botón 'Siguiente' no encontrado o no clickeable).")
                    break
            
            return todas_las_propiedades_de_url

        except Exception as e:
            print(f"Intento {attempt + 1}/{max_retries} falló para la URL. Error: {e}")
            if attempt + 1 == max_retries:
                print(f"Se agotaron los reintentos para la URL: {url}")
                return [] 
            time.sleep(5) 
    return []


def main():
    # (Sin cambios en la lógica principal de esta función)
    log_conn = None
    try:
        log_conn = psycopg2.connect(DATABASE_URL)
        log_execution(log_conn, 'scraper.py', 'STARTED')
    except (Exception, psycopg2.DatabaseError) as e:
        send_telegram_alert(f"CRÍTICO: No se pudo conectar a la DB: `{e}`")
        sys.exit(1)

    try:
        if not SCRAPE_URLS_STRING:
            raise ValueError("Variable de entorno SCRAPE_URLS no definida o está vacía.")
        
        urls_to_scrape = [url.strip().strip('"') for url in SCRAPE_URLS_STRING.split(';') if url.strip()]
        
        if not urls_to_scrape:
            raise ValueError("No se encontraron URLs válidas en SCRAPE_URLS después de procesar.")
        
        print(f"Se procesarán {len(urls_to_scrape)} URL(s).")
        
        todas_las_propiedades_global = []

        uf_actual = get_uf_value()
        if not uf_actual:
            raise ConnectionError("No se pudo obtener el valor de la UF de la API de CMF.")
        print(f"Valor UF obtenido: {uf_actual}")

        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument("window-size=1920,1080")
        
        driver = webdriver.Chrome(options=options)
        wait = WebDriverWait(driver, 20)
        
        try:
            for i, url in enumerate(urls_to_scrape):
                print(f"\n--- URL {i+1}/{len(urls_to_scrape)} ---")
                try:
                    propiedades_de_url = scrape_url(url, driver, wait)
                    if propiedades_de_url:
                        todas_las_propiedades_global.extend(propiedades_de_url)
                except Exception as e:
                    print(f"Error procesando URL {url[:80]}: {e}")
                    send_telegram_alert(f"Falló el scraping para una URL:\n`{url}`\nError: `{e}`")
        finally:
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