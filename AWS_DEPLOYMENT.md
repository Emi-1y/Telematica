# IoT Services Monitoring - Guía de Despliegue AWS EC2

Sigue estos pasos para desplegar el sistema completo en una instancia EC2 de AWS.

## 1. Lanzamiento de la Instancia
- **OS**: Ubuntu Server 22.04 LTS (recomendado)
- **Tipo**: t2.micro (Tapa gratuita)
- **Par de llaves**: Descarga tu archivo `.pem`

---

## 2. Configuración del Grupo de Seguridad (Security Group)
Debes abrir los siguientes puertos en "Inbound Rules" (Reglas de Entrada):

| Tipo  | Puerto | Protocolo | Descripción           |
| :---: | :---:  | :---:     | :---                  |
| HTTP  | 80     | TCP       | Acceso web (si usas proxy) |
| Personalizado | 5000   | TCP       | Dashboard Web Flask   |
| Personalizado | 8080   | TCP       | Servidor Central IoT  |
| Personalizado | 5001   | TCP       | API de Autenticación  |
| SSH   | 22     | TCP       | Acceso remoto         |

---

## 3. Preparación del Entorno
Conéctate por SSH e instala Docker y Git:

```bash
sudo apt update
sudo apt install -y git docker.io docker-compose
sudo usermod -aG docker $USER
# Cierra sesión y vuelve a entrar para aplicar cambios de grupo
```

---

## 4. Clonación y Despliegue
```bash
git clone <tu-repositorio>
cd Telematica

# Construir y lanzar los servicios en segundo plano
docker-compose up --build -d
```

---

## 5. Acceso al Sistema
Una vez desplegado:
- **Dashboard Web**: `http://<IP-Publica-EC2>:5000`
- **Servidor IoT (TCP)**: `http://<IP-Publica-EC2>:8080` (Para conectar sensores y operadores externos)

---

## 6. Variables de Entorno (Opcional)
Si deseas personalizar la clave de sesión o las URLs internas, puedes editar el archivo `docker-compose.yml` en la sección `web-service/environment`.

### Variables Disponibles:
- `IOT_SERVER_HOST`: El nombre DNS del contenedor del servidor (por defecto `iot-server`).
- `AUTH_SERVICE_URL`: La URL base del microservicio de autenticación.
- `SECRET_KEY`: Una cadena aleatoria para cifrar las cookies de sesión de Flask.
