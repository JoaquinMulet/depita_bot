# Dockerfile para despliegue con Python y PM2

# ---- Stage 1: Build - Imagen base de Python ----
    FROM python:3.10-slim-bullseye AS base

    ENV PYTHONDONTWRITEBYTECODE 1
    ENV PYTHONUNBUFFERED 1
    WORKDIR /app
    
    # Instala dependencias del sistema para Chrome
    RUN apt-get update && apt-get install -y \
        wget \
        unzip \
        libglib2.0-0 \
        libnss3 \
        libgconf-2-4 \
        libfontconfig1 \
        --no-install-recommends
    
    # Instala Google Chrome
    RUN wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
        dpkg -i google-chrome-stable_current_amd64.deb; \
        apt-get -fy install; \
        rm google-chrome-stable_current_amd64.deb
    
    # Instala el chromedriver correspondiente
    RUN CHROMEDRIVER_VERSION="124.0.6367.207" && \
        wget -q https://storage.googleapis.com/chrome-for-testing-public/${CHROMEDRIVER_VERSION}/linux64/chromedriver-linux64.zip && \
        unzip chromedriver-linux64.zip -d /usr/local/bin/ && \
        rm chromedriver-linux64.zip
    
    # Copia e instala las dependencias de Python
    COPY requirements.txt .
    RUN pip install --no-cache-dir -r requirements.txt
    
    # ---- Stage 2: Final - Añadir Node.js y PM2 ----
    FROM base
    
    # Instala Node.js y npm
    RUN apt-get update && apt-get install -y nodejs npm --no-install-recommends
    
    # Instala PM2 globalmente
    RUN npm install pm2 -g
    
    # Copia todo el código de la aplicación
    COPY . .
    
    # Expone el puerto por si PM2 lo necesita internamente
    EXPOSE 8080
    
    # El comando de inicio que lanza PM2 con nuestro archivo de configuración
    CMD ["pm2-runtime", "start", "ecosystem.config.js"]