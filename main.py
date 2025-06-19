# main.py (versión actualizada para incluir el monitor)
import sys
import os
from dotenv import load_dotenv

# Importa las funciones principales de tus otros scripts
# ASUMO que tus scripts tienen una función main() como el analyzer
from scraper import main as run_scraper
from analyzer import main as run_analyzer
# --- NUEVA LÍNEA: Importamos la función principal del monitor ---
from monitor import main as run_monitor

# Cargar variables de entorno desde .env para desarrollo local
load_dotenv()

def run_full_process():
    """
    Ejecuta el proceso completo: scraping, análisis y monitoreo.
    """
    print("==============================================")
    print("🚀 INICIANDO PROCESO COMPLETO DE PROPIEDADES")
    print("==============================================")

    # --- PASO 1: SCRAPER (Sin cambios) ---
    try:
        print("\n--- PASO 1: EJECUTANDO SCRAPER ---")
        run_scraper()
        print("--- ✅ SCRAPER FINALIZADO CON ÉXITO ---\n")
    except Exception as e:
        print(f"--- ❌ ERROR CRÍTICO EN SCRAPER ---")
        print(f"Error: {e}")
        print("El proceso se detendrá. El analizador y monitor no se ejecutarán.")
        sys.exit(1)

    # --- PASO 2: ANALIZADOR (Sin cambios) ---
    try:
        print("\n--- PASO 2: EJECUTANDO ANALIZADOR ---")
        run_analyzer()
        print("--- ✅ ANALIZADOR FINALIZADO CON ÉXITO ---\n")
    except Exception as e:
        print(f"--- ❌ ERROR CRÍTICO EN ANALIZADOR ---")
        print(f"Error: {e}")
        print("El proceso se detendrá. El monitor no se ejecutará.")
        sys.exit(1)

    # --- NUEVO PASO 3: MONITOR ---
    try:
        print("\n--- PASO 3: EJECUTANDO MONITOR ---")
        run_monitor()
        print("--- ✅ MONITOR FINALIZADO CON ÉXITO ---\n")
    except Exception as e:
        # Un error en el monitor no debería detener el proceso como crítico,
        # pero sí debería registrarse.
        print(f"--- ⚠️ ADVERTENCIA EN MONITOR ---")
        print(f"Error: {e}")
        # No usamos sys.exit(1) para que el log de Railway no marque el run como fallido
        # si solo falla el monitoreo opcional.

    print("==============================================")
    print("🎉 PROCESO COMPLETO FINALIZADO EXITOSAMENTE")
    print("==============================================")


if __name__ == "__main__":
    run_full_process()