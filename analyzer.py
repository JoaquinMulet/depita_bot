# analyzer.py
# -*- coding: utf-8 -*-

import os
import psycopg2
import requests
from dotenv import load_dotenv

load_dotenv()

# --- Configuración ---
DATABASE_URL = os.getenv('DATABASE_URL')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

def send_telegram_notification(message):
    # ... (misma función que en scraper.py, pero sin el prefijo de alerta)
    pass

def main():
    conn = None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        with conn.cursor() as cur:
            # 1. Procesar nuevas observaciones para calcular métricas
            cur.execute("""
                SELECT o.id, o.precio_uf, o.superficie_util_m2 
                FROM observaciones_venta o
                WHERE o.es_nueva = TRUE;
            """)
            
            observaciones_para_procesar = cur.fetchall()
            for obs_id, precio_uf, superficie in observaciones_para_procesar:
                if precio_uf and superficie and superficie > 0:
                    uf_por_m2 = round(precio_uf / superficie, 2)
                    cur.execute(
                        "INSERT INTO metricas_historicas (observacion_id, uf_por_m2) VALUES (%s, %s)",
                        (obs_id, uf_por_m2)
                    )
            
            # 2. Identificar propiedades que son genuinamente nuevas
            cur.execute("""
                SELECT p.titulo, p.link, o.precio_uf
                FROM propiedades p
                JOIN observaciones_venta o ON p.id = o.propiedad_id
                WHERE o.id IN (SELECT id FROM observaciones_venta WHERE es_nueva = TRUE)
                AND (SELECT COUNT(*) FROM observaciones_venta WHERE propiedad_id = p.id) = 1;
            """)
            propiedades_nuevas = cur.fetchall()

            if propiedades_nuevas:
                message = f"🔔 *{len(propiedades_nuevas)} Propiedades Nuevas Detectadas* 🔔\n\n"
                for titulo, link, precio in propiedades_nuevas:
                    message += f"🏠 [{titulo}]({link})\n   *Precio:* {precio:,.2f} UF\n\n".replace(',', 'X').replace('.', ',').replace('X', '.')
                send_telegram_notification(message)

            # 3. Marcar observaciones como procesadas
            cur.execute("UPDATE observaciones_venta SET es_nueva = FALSE WHERE es_nueva = TRUE;")
            conn.commit()

        print(f"Análisis completado. {len(observaciones_para_procesar)} observaciones procesadas.")

    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error en el analizador: {error}")
        if conn: conn.rollback()
        # Aquí podrías enviar una alerta de fallo específica del analizador
    finally:
        if conn: conn.close()

if __name__ == "__main__":
    main()