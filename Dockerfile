# Dockerfile final para Cron Job en Railway

# 1. Usar una imagen base de Python delgada y estable
FROM python:3.10-slim-bullseye

# 2. Variables de entorno para optimizar Python en Docker
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# 3. Instalar dependencias del sistema para headless Chrome
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# 4. Instalar Google Chrome Stable
RUN wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
    apt-get update && \
    apt-get install -y ./google-chrome-stable_current_amd64.deb --no-install-recommends && \
    rm google-chrome-stable_current_amd64.deb

# 5. Instalar el Chromedriver correcto para la versión de Chrome instalada
# Este método es robusto y busca la versión correcta automáticamente
RUN CHROME_VERSION=$(google-chrome --version | cut -f 3 -d ' ' | cut -d '.' -f 1-3) && \
    CHROMEDRIVER_VERSION=$(wget -qO- "https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json" | jq -r ".versions[] | select(.version | startswith(\"$CHROME_VERSION\")) | .downloads.chromedriver[0].url" | grep 'linux64') && \
    wget -q "$CHROMEDRIVER_VERSION" -O chromedriver.zip && \
    unzip chromedriver.zip -d /usr/local/bin/ && \
    rm chromedriver.zip

# 6. Preparar el directorio de la aplicación y las dependencias de Python
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 7. Copiar todo el código de la aplicación al contenedor
COPY . .

# 8. Comando final: Ejecutar el script orquestador
# Railway ejecutará este comando. Cuando 'main.py' termine, el contenedor se detendrá.
CMD ["python", "main.py"]