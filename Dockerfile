# Usa una imagen base de Python que incluya herramientas de compilación
FROM python:3.10-slim-bullseye

# Variables de entorno para que Python no guarde bytecode
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Directorio de trabajo
WORKDIR /app

# Instala dependencias del sistema: wget, unzip, y librerías para Chrome
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    libglib2.0-0 \
    libnss3 \
    libgconf-2-4 \
    libfontconfig1 \
    --no-install-recommends

# Instala Google Chrome
RUN wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
RUN dpkg -i google-chrome-stable_current_amd64.deb || apt-get -fy install
RUN rm google-chrome-stable_current_amd64.deb

# Instala el chromedriver correspondiente.
# Es crucial que esta versión coincida con la de Chrome instalada.
# Revisa las versiones disponibles en: https://googlechromelabs.github.io/chrome-for-testing/
# A la fecha, una versión reciente y estable de Chrome es 124.
RUN CHROMEDRIVER_VERSION="124.0.6367.207" && \
    wget -q https://storage.googleapis.com/chrome-for-testing-public/${CHROMEDRIVER_VERSION}/linux64/chromedriver-linux64.zip && \
    unzip chromedriver-linux64.zip -d /usr/local/bin/ && \
    rm chromedriver-linux64.zip

# Copia e instala las dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo el código de la aplicación
COPY . .

# El comando por defecto se establece en Railway, manteniendo el contenedor en espera.
CMD ["sleep", "infinity"]