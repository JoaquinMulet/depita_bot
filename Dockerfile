# Dockerfile RECOMENDADO Y COMPLETO
# Usa webdriver-manager en Python para gestionar el chromedriver

# 1. Imagen base de Python, delgada y estable.
FROM python:3.10-slim-bullseye

# 2. Variables de entorno para optimizar Python en Docker.
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# 3. Instalar dependencias del sistema, INCLUYENDO Google Chrome.
#    No se instala chromedriver aquí; eso lo hará Python al ejecutarse.
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    --no-install-recommends && \
    wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome-keyring.gpg && \
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && \
    apt-get install -y google-chrome-stable --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# 4. Preparar el directorio de la aplicación y las dependencias de Python.
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copiar todo el código de la aplicación al contenedor.
COPY . .

# 6. Comando final: Ejecutar el script orquestador principal.
#    Cuando main.py termine, el contenedor se detendrá.
CMD ["python", "main.py"]