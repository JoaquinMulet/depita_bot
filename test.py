# -*- coding: utf-8 -*-

import os
import sys
import psycopg2
from dotenv import load_dotenv

# Cargar las variables de entorno (necesario para obtener DATABASE_URL)
load_dotenv()

# --- ¡IMPORTANTE! ---
# Reemplaza esta URL con el link EXACTO de una de las propiedades
# que quieres verificar. Cópialo de tu notificación de Telegram.
link_a_verificar = "https://departamento.mercadolibre.cl/MLC-2898842808-moderno-departamento-en-el-arrayan-con-increible-v-_JM#position=1&search_layout=map&type=item&tracking_id=d9e8ad7a-6fc2-4269-92c9-38c4aefcccbf"


def verificar_propiedad(db_url, link):
    """
    Se conecta a la base de datos y verifica si un link existe en la tabla 'propiedades'.
    """
    if not db_url:
        print("❌ ERROR: La variable de entorno DATABASE_URL no está definida en tu archivo .env")
        sys.exit(1)

    if "ejemplo-pegalo-aqui" in link:
        print("⚠️ ADVERTENCIA: Por favor, edita el script y reemplaza el link de ejemplo por uno real.")
        sys.exit(1)

    conn = None
    try:
        # Conectarse a la base de datos PostgreSQL
        print("🔌 Conectando a la base de datos...")
        conn = psycopg2.connect(db_url)
        print("✅ Conexión exitosa.")

        # Crear un cursor para ejecutar comandos
        cur = conn.cursor()

        print(f"\n🔎 Buscando el siguiente link en la tabla 'propiedades':\n   {link}\n")

        # Ejecutar la consulta SQL para buscar el link
        cur.execute("SELECT id, titulo FROM propiedades WHERE link = %s", (link,))

        # Obtener el resultado
        resultado = cur.fetchone()

        # Cerrar la comunicación con la base de datos
        cur.close()

        # Analizar y reportar el resultado
        if resultado:
            propiedad_id, titulo = resultado
            print("--- RESULTADO ---")
            print(f"✔️ ¡ENCONTRADO! El link ya existe en la base de datos.")
            print(f"    ID: {propiedad_id}")
            print(f"    Título: {titulo}")
        else:
            print("--- RESULTADO ---")
            print("❌ NO ENCONTRADO. El link no existe en la tabla 'propiedades'.")
            print("   Esto explica por qué el scraper lo trató como una 'NUEVA PROPIEDAD'.")

    except psycopg2.DatabaseError as e:
        print(f"\n🔥 Error de base de datos: {e}")
    except Exception as e:
        print(f"\n🔥 Ocurrió un error inesperado: {e}")
    finally:
        # Asegurarse de que la conexión se cierre siempre
        if conn is not None:
            conn.close()
            print("\n🔌 Conexión a la base de datos cerrada.")

if __name__ == "__main__":
    database_url = os.getenv('DATABASE_URL')
    verificar_propiedad(database_url, link_a_verificar)