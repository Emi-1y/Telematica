Aquí tienes el **README completo en Markdown puro**, limpio y listo para copiar y pegar directamente en GitHub 👇🔥

---

````markdown
# IoT Services Monitoring Dashboard 🌐🚀

Este proyecto es una plataforma de monitoreo IoT industrial distribuida, diseñada para la gestión en tiempo real de sensores, detección de anomalías y visualización de datos mediante una arquitectura de microservicios robusta.

---

## 📋 Descripción del Sistema

El sistema consta de cuatro componentes principales trabajando en conjunto:

1. **Servidor Central (C)**  
   Motor de alto rendimiento que utiliza Berkeley Sockets y pthreads para gestionar conexiones simultáneas de sensores. Implementa buffers circulares para el registro de alertas y actividad.

2. **Microservicio de Autenticación (Python)**  
   Servicio desacoplado que gestiona credenciales y Roles de Acceso (RBAC: Administrador y Operador).

3. **Interfaz Web (Flask)**  
   Dashboard responsivo que consume datos directamente del servidor C mediante sockets para mostrar el estado del sistema, sensores activos y alertas históricas.

4. **Red de Sensores (Simulados)**  
   Ecosistema de 5 sensores (Temperatura, Vibración, Humedad y Energía) que envían mediciones periódicas y generan alertas basadas en umbrales críticos.

---

## 🛠️ Instalación y Configuración Local

### Requisitos Previos

- Docker  
- Docker Compose  
- Git  

---

### Pasos para ejecutar

1. Clonar el repositorio:

```bash
git clone <URL_DEL_REPOSITORIO>
cd Telematica
````

2. Levantar el sistema:

```bash
docker-compose up --build -d
```

3. Acceder al sistema:

[http://localhost:5000](http://localhost:5000)

---

## 🔐 Credenciales de prueba

* Operador → usuario: operator1 | clave: op123
* Admin → usuario: admin | clave: password123

---

## ☁️ Despliegue en AWS (EC2)

### 1. Crear instancia

* Ubuntu Server 22.04
* Acceso mediante archivo .pem

---

### 2. Configurar Security Group (puertos)

* 22 → SSH
* 5000 → Web
* 8080 → Servidor IoT
* 5001 → Auth

---

### 3. Instalar dependencias

Conéctate por SSH y ejecuta:

```bash
sudo apt update
sudo apt install -y git docker.io docker-compose
sudo usermod -aG docker $USER
```

Luego cierra sesión y vuelve a entrar.

---

### 4. Clonar y ejecutar

```bash
git clone <URL_DEL_REPOSITORIO>
cd Telematica
docker-compose up --build -d
```

---

### 5. Acceso

http://IP_PUBLICA:5000

---

## 🏗️ Estructura del proyecto

```
/server   → Servidor en C  
/Auth     → Servicio de autenticación  
/Web      → Dashboard Flask  
/Sensor   → Simulación de sensores  
docker-compose.yml  
```

---

## 🧠 Tecnologías utilizadas

* C (Sockets + pthreads)
* Python (Flask)
* Docker / Docker Compose
* AWS EC2
* HTTP / TCP

---

## 🎯 Características clave

* Sistema distribuido real
* Comunicación mediante sockets
* Manejo de múltiples clientes simultáneos
* Detección de anomalías
* Visualización en tiempo real
* Despliegue en la nube

---

## 📚 Proyecto académico

Materia: Internet, Arquitectura y Protocolos

---

## 👨‍💻 Autores

* Emily Cardona
* Samuel Arango Echeverri




