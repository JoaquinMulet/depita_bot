# Sistema de Monitoreo de Propiedades Inmobiliarias

Este proyecto es una aplicación de recolección y análisis de datos diseñada para monitorear el mercado inmobiliario. Construida con principios de fiabilidad y mantenibilidad, utiliza un flujo de datos desacoplado para garantizar la integridad y facilitar la evolución del sistema.

### Arquitectura

-   **Ingesta (Scraper):** `scraper.py` utiliza Selenium para extraer datos de múltiples URLs configuradas.
-   **Almacenamiento (PostgreSQL):** La base de datos actúa como un log de eventos inmutables, nuestra fuente de la verdad.
-   **Procesamiento (Analyzer):** `analyzer.py` consume los nuevos datos, calcula métricas (UF/m²) y envía notificaciones a Telegram sobre nuevas propiedades.
-   **Orquestación (PM2):** Se utiliza PM2, un gestor de procesos de producción para Node.js (pero que funciona excelentemente con Python), para programar y ejecutar los scripts como tareas cron dentro del contenedor Docker.
-   **Monitoreo (Monitor):** `monitor.py` verifica periódicamente la salud de las ejecuciones pasadas y alerta sobre fallos.

---

## Despliegue en Railway

El despliegue está optimizado para Railway y utiliza un `Dockerfile` para crear un entorno autocontenido.

### Prerrequisitos

*   Una cuenta de GitHub.
*   Una cuenta de Railway.
*   Un bot de Telegram y el ID de chat/canal.
*   Una API Key de la CMF Chile para el valor de la UF.

### Pasos de Despliegue

1.  **Forkear y Crear Proyecto:**
    *   Haz un "fork" de este repositorio.
    *   En Railway, crea un `New Project` y selecciona `Deploy from GitHub repo`, eligiendo tu fork. Railway usará el `Dockerfile` para construir el servicio.

2.  **Añadir Base de Datos PostgreSQL:**
    *   En tu proyecto de Railway, haz clic en `+ New` -> `Database` -> `PostgreSQL`.
    *   Railway creará la base de datos y **automáticamente inyectará la variable `DATABASE_URL` en tu servicio de aplicación.**

3.  **Configurar Variables de Entorno:**
    *   Ve a tu servicio de aplicación y abre la pestaña `Variables`.
    *   Añade las siguientes variables. **No necesitas añadir `DATABASE_URL` manualmente.**

        | Variable             | Descripción                                                                                                 |
        | -------------------- | ----------------------------------------------------------------------------------------------------------- |
        | `TELEGRAM_BOT_TOKEN` | El token de tu bot de Telegram.                                                                             |
        | `TELEGRAM_CHAT_ID`   | El ID numérico de tu chat, canal o grupo de Telegram.                                                       |
        | `CMF_API_KEY`        | Tu clave de API del portal de CMF Chile.                                                                    |
        | `SCRAPE_URLS`        | Lista de URLs de Mercado Libre a scrapear, **separadas por comas, sin espacios**.                             |

4.  **Inicializar Esquema de la Base de Datos:**
    *   Ve a tu servicio PostgreSQL en Railway, abre la pestaña `Data`.
    *   Copia el contenido del archivo `schema.sql` del repositorio.
    *   Pega el SQL en la ventana de consulta y ejecútalo para crear todas las tablas necesarias.

¡Listo! El `Dockerfile` se encarga de iniciar PM2, que a su vez leerá `ecosystem.config.js` y programará tus scripts para que se ejecuten en los horarios definidos. Puedes monitorear la salida de los scripts en los logs de despliegue de tu servicio en Railway.

### Aclaración sobre la Conexión a la Base de Datos

La variable `DATABASE_URL` es una cadena de conexión estándar con el formato:
`postgresql://<usuario>:<contraseña>@<host>:<puerto>/<nombre_db>`

Nuestra aplicación utiliza la librería `psycopg2`, que entiende este formato directamente. Extrae todas las credenciales necesarias (usuario, contraseña, host, etc.) de esta única variable. Por lo tanto, **es la única variable que necesitas para la conexión a la base de datos**, lo cual es una práctica segura y estándar.