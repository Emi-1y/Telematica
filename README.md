# IoT Services Monitoring - README

## 1. Descripción General
Sistema distribuido de monitoreo IoT para procesos industriales. Consta de un servidor central en C de alto rendimiento, clientes sensores en múltiples lenguajes (C y Python) y una interfaz web de gestión distribuida mediante microservicios.

## 2. Requisitos Académicos Cumplidos (Compliance Matrix)

| Requisito | Implementación | Evidencia |
| :--- | :--- | :--- |
| **Sockets Berkeley (TCP)** | Servidor en C y Clientes (C/Python) usan sockets puros. | `server/server.c`, `Sensor/sensor_cli.c` |
| **Concurrencia** | Servidor usa `pthreads` para manejar múltiples clientes simultáneos. | Logs con registros intercalados de múltiples IPs/Puertos. |
| **Protocolo de Texto Propio** | Definido con comandos `REGISTER`, `DATA`, `GET_STATUS`, etc. | Sección 3 de este README. |
| **Multilenguaje (Clientes)** | Sensores implementados en **Python** y **C**. | `Sensor/sensor.py` y `Sensor/sensor_cli.c`. |
| **Resolución de Nombres (DNS)** | Clientes usan `getaddrinfo` para conectar a `iot-server`. | Código fuente de sensores (C/Python). |
| **Microservicio de Auth** | Servicio independiente en el puerto `5001` con `users.json`. | Directorio `Auth/`. |
| **Interfaz HTTP / WEB** | Panel en puerto `5000` con rutas protegidas y sesiones. | Directorio `Web/`. |
| **Dockerización Completa** | Orquestación de 3 servicios y 5 sensores vía `docker-compose`. | `docker-compose.yml`. |

## 3. Especificación del Protocolo IoT (v1.2)

### Comandos de Sensores
| Comando | Sintaxis | Ejemplo de Respuesta |
| :--- | :--- | :--- |
| **REGISTER** | `REGISTER SENSOR <ID> <TIPO>` | `OK SENSOR_REGISTERED <ID>` |
| **DATA** | `DATA <ID> <TIPO> <VALOR>` | `OK DATA_RECEIVED` o `ALERT ...` |
| **DISCONNECT** | `DISCONNECT` | (Cierre de socket) |

### Comandos de Gestión (Usados por la Web)
| Comando | Propósito | Ejemplo de Respuesta |
| :--- | :--- | :--- |
| **GET_STATUS** | Estado general del servidor y uptime. | `STATUS OK uptime:120 sensors:5 ...` |
| **LIST_SENSORS** | Lista de sensores y últimos valores. | `SENSOR_LIST [{id:s1, tipo:temp, v:25}, ...]` |
| **GET_ALERTS** | Historial de las últimas 50 anomalías. | `ALERTS [{id:s1, ts:123, r:ALTA}, ...]` |

## 4. Ejecución del Proyecto con Docker

1. **Levantar el sistema completo (incluye 5 sensores):**
   ```bash
   docker-compose up -d --build
   ```

2. **Acceso Web:**
   - **URL**: `http://localhost:5000/status`
   - **Login**: `admin` / `password123`

## 5. Pruebas de Validación HTTP (Curl)

- **Login (200)**: `curl -I http://localhost:5000/login`
- **Acceso Protegido (302 Redirect)**: `curl -I http://localhost:5000/status`
- **Página inexistente (404)**: `curl -I http://localhost:5000/not-found`

## 6. Logs del Servidor
Ubicación: `/app/logs/server.log` (dentro del contenedor).
Formato: `[Timestamp] IP=... PUERTO=... | RX: ... | TX: ...`
