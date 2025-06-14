# Sistema de Monitoreo de Propiedades Inmobiliarias

Este proyecto es una aplicación de recolección y análisis de datos diseñada para monitorear el mercado inmobiliario en portales web como Mercado Libre. La aplicación está construida siguiendo los principios de diseño de sistemas de datos intensivos, priorizando la fiabilidad, escalabilidad y mantenibilidad.

La arquitectura se basa en un modelo de flujo de datos (dataflow) que separa claramente las responsabilidades:

1.  **Ingesta (Scraper):** Un script robusto basado en Selenium extrae periódicamente los datos de las propiedades en venta desde una o más URLs configuradas.
2.  **Almacenamiento (Base de Datos):** Utiliza una base de datos PostgreSQL como **Sistema de Registro (Source of Truth)**. Todas las observaciones se guardan como eventos inmutables, creando un historial completo y auditable.
3.  **Análisis (Analyzer):** Un consumidor procesa las nuevas observaciones, calcula métricas derivadas (como el valor en UF por metro cuadrado) y las almacena para análisis histórico.
4.  **Notificaciones (Notifier):** El analizador detecta propiedades genuinamente nuevas y envía notificaciones en tiempo real a un canal de Telegram.
5.  **Monitoreo (Monitor):** Un script de vigilancia se ejecuta periódicamente para asegurar que el sistema está funcionando correctamente y alerta sobre posibles fallos en las ejecuciones.

Este diseño "desempaquetado" permite que cada componente evolucione de forma independiente y garantiza la integridad de los datos a lo largo de todo el pipeline.

## Despliegue en Railway

Esta aplicación está diseñada para ser desplegada fácilmente en [Railway.app](https://railway.app/).

### Prerrequisitos

*   Una cuenta de GitHub.
*   Una cuenta de Railway.
*   Un bot de Telegram y el ID del chat donde se enviarán las notificaciones.
*   Una API Key del servicio de Indicadores Financieros de CMF Chile para obtener el valor de la UF. Puedes registrarte en [api.cmfchile.cl](https://api.cmfchile.cl/).

### Pasos de Despliegue

1.  **Forkear el Repositorio:** Haz un "fork" de este repositorio en tu propia cuenta de GitHub.

2.  **Crear Proyecto en Railway:**
    *   Inicia sesión en tu cuenta de Railway y haz clic en `New Project`.
    *   Selecciona `Deploy from GitHub repo` y elige el repositorio que acabas de forkear.
    *   Railway detectará el `Dockerfile` y comenzará a construir la imagen de tu aplicación.

3.  **Añadir Base de Datos PostgreSQL:**
    *   Dentro de tu nuevo proyecto en Railway, haz clic en el botón `+ New`.
    *   Selecciona `Database` y luego `PostgreSQL`.
    *   Railway creará una base de datos y automáticamente añadirá la variable de entorno `DATABASE_URL` a tu servicio de aplicación. ¡No necesitas configurarla manualmente!

4.  **Configurar Variables de Entorno:**
    *   Ve a tu servicio de aplicación (no a la base de datos) y haz clic en la pestaña `Variables`.
    *   Añade las siguientes variables de entorno con tus propios valores (los secretos se guardarán de forma segura):

        | Variable             | Descripción                                                                                              | Ejemplo                                                                                                                                                                                                                                                                                                           |
        | -------------------- | -------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
        | `TELEGRAM_BOT_TOKEN` | El token de tu bot de Telegram, obtenido de @BotFather.                                                  | `1234567890:AAbbCCddEEffGGhhIIjjKKllMMnnOOpp`                                                                                                                                                                                                                                                                      |
        | `TELEGRAM_CHAT_ID`   | El ID numérico del chat, canal o grupo de Telegram donde se recibirán las alertas.                        | `-1001234567890` (para canales/supergrupos) o `987654321` (para chats privados).                                                                                                                                                                                                                                    |
        | `CMF_API_KEY`        | Tu clave de API personal del portal de CMF Chile.                                                        | `a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4`                                                                                                                                                                                                                                                                                 |
        | `SCRAPE_URLS`        | Una lista de URLs de Mercado Libre a scrapear, **separadas por comas y sin espacios entre ellas**.         | `https://listado.mercadolibre.cl/inmuebles/departamentos/venta/_DisplayType_M,https://listado.mercadolibre.cl/inmuebles/casas/arriendo/_DisplayType_M`                                                                                                                                                                     |

5.  **Inicializar la Base de Datos:**
    *   Ve a tu servicio de PostgreSQL en Railway y haz clic en la pestaña `Data`.
    *   Copia y pega el contenido del archivo `schema.sql` (que se encuentra en el repositorio) en la ventana de consulta y ejecútalo. Esto creará las tablas necesarias (`propiedades`, `observaciones_venta`, `metricas_historicas`, `log_ejecucion`).

6.  **Configurar Tareas Programadas (Cron Jobs):**
    *   Vuelve a tu servicio de aplicación y ve a la pestaña `Settings`.
    *   En la sección `Deploy`, busca el `Start Command`. Déjalo en blanco o pon `sleep infinity`. Esto es importante para que el contenedor se mantenga vivo para ejecutar los cron jobs.
    *   Railway debería detectar el archivo `railway.json` y configurar los cron jobs automáticamente. Si no, puedes definirlos manualmente en la UI de Railway. El `railway.json` define:
        *   **Trabajo Principal (diario a las 12:00 UTC):** `python scraper.py && python analyzer.py`
        *   **Trabajo de Monitoreo (diario a las 14:00 UTC):** `python monitor.py`

¡Eso es todo! Tu sistema ahora está desplegado y se ejecutará automáticamente según el horario definido. Puedes ver los logs de cada ejecución en la pestaña `Deployments` de tu servicio de aplicación en Railway.

## Desarrollo Local

Para ejecutar y probar la aplicación en tu máquina local:

1.  Asegúrate de tener Python 3.10+ y Google Chrome instalado.
2.  Clona el repositorio: `git clone <url-de-tu-repo>`
3.  Crea un entorno virtual: `python -m venv venv` y actívalo (`source venv/bin/activate` en Linux/macOS o `venv\Scripts\activate` en Windows).
4.  Instala las dependencias: `pip install -r requirements.txt`.
5.  Crea un archivo `.env` a partir de `.env.example` y rellénalo con tus credenciales y URLs de prueba.
6.  Ejecuta los scripts manualmente: `python scraper.py`, luego `python analyzer.py`.