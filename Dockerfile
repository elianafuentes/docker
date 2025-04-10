FROM python:3.9

WORKDIR /app

# Instalar las dependencias del sistema necesarias para geopandas y otras bibliotecas
RUN apt-get update && apt-get install -y \
    build-essential \
    libgeos-dev \
    libproj-dev \
    libgdal-dev \
    libmariadb-dev \
    libpq-dev \
    libjpeg-dev \
    zlib1g-dev \
    libpng-dev \
    libssl-dev \
    libxml2-dev \
    libxslt-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements.txt primero para aprovechar la caché de Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todo el código de la aplicación
COPY . .

# Exponer el puerto en el que se ejecutará la aplicación Dash
EXPOSE 8050

# Comando para ejecutar la aplicación
CMD ["gunicorn", "--bind", "0.0.0.0:8050", "app:server"]
