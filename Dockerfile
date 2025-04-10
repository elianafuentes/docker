FROM python:3.9-slim

WORKDIR /app

# Instalar las dependencias del sistema necesarias para geopandas
RUN apt-get update && apt-get install -y \
    build-essential \
    libgeos-dev \
    libproj-dev \
    libgdal-dev \
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
CMD ["python", "app.py"]
