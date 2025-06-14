# Dockerfile para despliegue con Python y cron

FROM python:3.10-slim-bullseye

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
WORKDIR /app

# Instala dependencias del sistema, incluyendo cron
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    cron \
    libglib2.0-0 \
    libnss3 \
    libgconf-2-4 \
    libfontconfig1 \
    --no-install-recommends

# Instala Google Chrome y chromedriver (sin cambios)
RUN wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
    dpkg -i google-chrome-stable_current_amd64.deb; \
    apt-get -fy install; \
    rm google-chrome-stable_current_amd64.deb

RUN CHROMEDRIVER_VERSION="124.0.6367.207" && \
    wget -q https://storage.googleapis.com/chrome-for-testing-public/${CHROMEDRIVER_VERSION}/linux64/chromedriver-linux64.zip && \
    unzip chromedriver-linux64.zip -d /usr/local/bin/ && \
    rm chromedriver-linux64.zip

# Copia e instala las dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo el código de la aplicación
COPY . .

# Dale permisos de ejecución al script de entrada
RUN chmod +x /app/entrypoint.sh

# Establece el punto de entrada del contenedor. Este comando es el que se ejecutará al iniciar.
ENTRYPOINT ["/app/entrypoint.sh"]