FROM python:3.9-slim

WORKDIR /app

# Instalar Flask. (En un caso real se usaría requirements.txt)
RUN pip install flask flask-cors

# Copiar el servicio y la base de datos JSON
COPY auth_service.py .
COPY users.json .

# Puerto del servicio de autenticación
EXPOSE 5001

# Ejecutar el servicio
CMD ["python", "auth_service.py"]
