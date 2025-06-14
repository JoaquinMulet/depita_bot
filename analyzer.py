# analyzer.py (versión adaptada para llave compuesta y análisis avanzado)
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

# --- Funciones de Utilidad (sin cambios) ---

def escape_markdown_v2(text: str) -> str:
    if not isinstance(text, str):
        return ""
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

def send_telegram_message(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("ALERTA: Variables de Telegram no configuradas.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message, # El mensaje ya debe venir escapado desde la lógica principal
        'parse_mode': 'MarkdownV2',
        'disable_web_page_preview': True
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        print("-> Notificación de análisis enviada a Telegram.")
    except requests.exceptions.RequestException as e:
        print(f"Error al enviar notificación a Telegram: {e}")
        if e.response is not None:
            print(f"Respuesta de la API de Telegram: {e.response.text}")

def log_execution(conn, script_name, status, error_message=None):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO log_ejecucion (script_name, start_time, end_time, status, error_message)
            VALUES (%s, NOW() AT TIME ZONE 'utc', NOW() AT TIME ZONE 'utc', %s, %s);
            """,
            (script_name, status, error_message)
        )
        conn.commit()

# --- Función Principal de Análisis (Adaptada) ---

def main():
    conn = None
    script_name = 'analyzer.py'
    try:
        conn = psycopg2.connect(DATABASE_URL)
        print("Conexión a la base de datos exitosa.")
        # No registramos 'STARTED' aquí, lo haremos al final junto con el estado final.
    except (Exception, psycopg2.DatabaseError) as e:
        print(f"CRÍTICO: No se pudo conectar a la DB: {e}")
        # No podemos registrar el error en la DB si no nos podemos conectar.
        sys.exit(1)

    try:
        with conn.cursor() as cur:
            # 1. OBTENER NUEVAS OBSERVACIONES
            # Traemos más datos para un análisis completo.
            cur.execute("""
                SELECT
                    o.id as obs_id,
                    o.propiedad_id,
                    o.precio_uf,
                    o.superficie_util_m2,
                    p.titulo
                FROM observaciones_venta o
                JOIN propiedades p ON o.propiedad_id = p.id
                WHERE o.es_nueva = TRUE;
            """)
            observaciones_nuevas = cur.fetchall()

            if not observaciones_nuevas:
                print("No hay nuevas observaciones para procesar.")
                log_execution(conn, script_name, 'SUCCESS_EMPTY')
                return

            print(f"Se procesarán {len(observaciones_nuevas)} nuevas observaciones.")
            df_new = pd.DataFrame(observaciones_nuevas, columns=['obs_id', 'propiedad_id', 'precio_uf', 'superficie', 'titulo'])

            # 2. CALCULAR MÉTRICAS BÁSICAS (UF/m²)
            df_valid = df_new.dropna(subset=['precio_uf', 'superficie'])
            df_valid = df_valid[df_valid['superficie'] > 0].copy()
            if not df_valid.empty:
                df_valid['uf_por_m2'] = df_valid['precio_uf'] / df_valid['superficie']
                # Insertar las nuevas métricas calculadas
                for _, row in df_valid.iterrows():
                    cur.execute(
                        "INSERT INTO metricas_historicas (observacion_id, uf_por_m2) VALUES (%s, %s)",
                        (row['obs_id'], row['uf_por_m2'])
                    )
                print(f"Se insertaron {len(df_valid)} nuevas métricas.")

            # 3. IDENTIFICAR PROPIEDADES REALMENTE NUEVAS VS. ACTUALIZACIONES
            # Para cada propiedad, contamos cuántas observaciones totales tiene en la DB.
            # Si solo tiene 1, es genuinamente nueva.
            prop_ids_a_chequear = tuple(df_new['propiedad_id'].unique())
            cur.execute(
                "SELECT propiedad_id, COUNT(id) as total_obs FROM observaciones_venta WHERE propiedad_id IN %s GROUP BY propiedad_id",
                (prop_ids_a_chequear,)
            )
            counts = cur.fetchall()
            df_counts = pd.DataFrame(counts, columns=['propiedad_id', 'total_obs'])
            
            # Unimos los conteos con nuestras observaciones nuevas
            df_merged = pd.merge(df_new, df_counts, on='propiedad_id')

            df_genuinamente_nuevas = df_merged[df_merged['total_obs'] == 1]
            df_actualizaciones = df_merged[df_merged['total_obs'] > 1]

            num_nuevas_total = len(df_genuinamente_nuevas)
            num_actualizaciones = len(df_actualizaciones)

            # 4. DETECTAR CAMBIOS DE PRECIO EN LAS ACTUALIZACIONES
            num_cambios_precio = 0
            if num_actualizaciones > 0:
                # Traemos el historial de las propiedades actualizadas para comparar precios
                prop_ids_actualizadas = tuple(df_actualizaciones['propiedad_id'].unique())
                cur.execute(
                    """
                    SELECT propiedad_id, precio_uf FROM (
                        SELECT
                            propiedad_id,
                            precio_uf,
                            LAG(precio_uf, 1) OVER (PARTITION BY propiedad_id ORDER BY fecha_observacion) as precio_anterior,
                            ROW_NUMBER() OVER (PARTITION BY propiedad_id ORDER BY fecha_observacion DESC) as rn
                        FROM observaciones_venta
                        WHERE propiedad_id IN %s
                    ) as sub
                    WHERE rn = 1 AND precio_uf <> precio_anterior;
                    """, (prop_ids_actualizadas,)
                )
                cambios_precio_detectados = cur.fetchall()
                num_cambios_precio = len(cambios_precio_detectados)

            # 5. CONSTRUIR Y ENVIAR EL REPORTE
            # Usamos los números calculados para un reporte mucho más rico.
            precio_promedio_uf = df_valid['precio_uf'].mean() if not df_valid.empty else 0
            uf_m2_promedio = df_valid['uf_por_m2'].mean() if 'uf_por_m2' in df_valid.columns else 0
            
            # Pre-escapamos todos los valores antes de construir el mensaje
            fecha_reporte = pd.Timestamp.now(tz='America/Santiago').strftime("%d de %B de %Y")
            s_nuevas = escape_markdown_v2(str(num_nuevas_total))
            s_actualizaciones = escape_markdown_v2(str(num_actualizaciones))
            s_cambios_precio = escape_markdown_v2(str(num_cambios_precio))
            s_total_validas = escape_markdown_v2(str(len(df_valid)))
            s_precio_prom_uf = escape_markdown_v2(f"{precio_promedio_uf:,.2f} UF".replace(",", "X").replace(".", ",").replace("X", "."))
            s_uf_m2_prom = escape_markdown_v2(f"{uf_m2_promedio:,.2f} UF/m²".replace(",", "X").replace(".", ",").replace("X", "."))

            message = (
                f"📊 *Reporte del Mercado Inmobiliario*\n"
                f"_{escape_markdown_v2(fecha_reporte)}_\n\n"
                f"Resumen de las últimas 24 horas:\n\n"
                f"🏠 *Nuevas Propiedades/Precios:* Se detectaron *{s_nuevas}* combinaciones de título/precio por primera vez\.\n"
                f"🔄 *Nuevas Observaciones:* Se registraron *{s_actualizaciones}* observaciones de propiedades ya existentes\.\n"
                f"💸 *Cambios de Precio:* Dentro de las observaciones, se identificaron *{s_cambios_precio}* cambios de precio\.\n\n"
                f"📈 *Análisis del Lote (basado en {s_total_validas} propiedades válidas):*\n"
                f"  • *Precio Promedio:* {s_precio_prom_uf}\n"
                f"  • *Valor Promedio:* {s_uf_m2_prom}\n"
            )

            send_telegram_message(message)

            # 6. MARCAR OBSERVACIONES COMO PROCESADAS
            cur.execute("UPDATE observaciones_venta SET es_nueva = FALSE WHERE es_nueva = TRUE;")
            conn.commit()
            print("Análisis y limpieza completados.")
            log_execution(conn, script_name, 'SUCCESS')

    except (Exception, psycopg2.DatabaseError) as error:
        error_msg = f"Error durante el análisis: {error}"
        print(error_msg)
        if conn:
            conn.rollback()
            log_execution(conn, script_name, 'FAILURE', error_message=str(error))
        # No enviar alerta de Telegram si el error fue al conectar
        if 'conn' in locals() and conn:
             send_telegram_message(escape_markdown_v2(f"🚨 ERROR CRÍTICO EN ANALYZER\n\n{error_msg}"))
        sys.exit(1)
    finally:
        if conn:
            conn.close()
            print("Conexión a la base de datos cerrada.")

if __name__ == "__main__":
    main()