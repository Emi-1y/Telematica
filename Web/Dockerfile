FROM python:3.9-slim

WORKDIR /app

# Instalar dependencias
RUN pip install flask requests

# Copiar la aplicación y las plantillas
COPY web_app.py .
COPY templates/ ./templates/

# Variables de entorno por defecto (Docker las sobrescribirá)
ENV IOT_SERVER_HOST=localhost
ENV IOT_SERVER_PORT=8080
ENV AUTH_SERVICE_URL=http://localhost:5001
ENV SECRET_KEY=super_secret_iot_key

EXPOSE 5000

# Ejecutar el dashboard
CMD ["python", "web_app.py"]
