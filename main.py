# main.py
import sys
import os
from dotenv import load_dotenv

# Importa las funciones principales de tus otros scripts
# ASUMO que tu scraper tiene una función main() como el analyzer
# Si no, adapta el nombre de la función (ej. run_scraper)
from scraper import main as run_scraper
from analyzer import main as run_analyzer

# Cargar variables de entorno desde .env para desarrollo local
load_dotenv()

def run_full_process():
    """
    Ejecuta el proceso completo: scraping y luego análisis.
    """
    print("==============================================")
    print("🚀 INICIANDO PROCESO COMPLETO DE PROPIEDADES")
    print("==============================================")

    try:
        print("\n--- PASO 1: EJECUTANDO SCRAPER ---")
        run_scraper()
        print("--- ✅ SCRAPER FINALIZADO CON ÉXITO ---\n")
    except Exception as e:
        print(f"--- ❌ ERROR CRÍTICO EN SCRAPER ---")
        print(f"Error: {e}")
        print("El proceso se detendrá. El analizador no se ejecutará.")
        # Salimos con un código de error para que Railway sepa que falló.
        sys.exit(1)

    try:
        print("\n--- PASO 2: EJECUTANDO ANALIZADOR ---")
        run_analyzer()
        print("--- ✅ ANALIZADOR FINALIZADO CON ÉXITO ---\n")
    except Exception as e:
        print(f"--- ❌ ERROR CRÍTICO EN ANALIZADOR ---")
        print(f"Error: {e}")
        sys.exit(1)

    print("==============================================")
    print("🎉 PROCESO COMPLETO FINALIZADO EXITOSAMENTE")
    print("==============================================")

if __name__ == "__main__":
    run_full_process()