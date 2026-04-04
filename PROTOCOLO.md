---

## 1. Características generales

| Propiedad         | Valor                        |
|-------------------|------------------------------|
| Capa              | Aplicación (Capa 7)          |
| Transporte        | TCP (SOCK_STREAM)            |
| Formato           | Texto plano UTF-8            |
| Terminador        | `\n` (newline) por mensaje   |
| Puerto por defecto| 8080                         |
| Codificación      | ASCII / UTF-8                |

### Justificación del transporte: TCP vs UDP

Se eligió **TCP (SOCK_STREAM)** por las siguientes razones:

- **Confiabilidad**: Si un sensor reporta una temperatura de 95°C y el mensaje se
  pierde (UDP no garantiza entrega), el servidor no detecta la anomalía. En un
  sistema de monitoreo industrial esto puede tener consecuencias graves.
- **Orden de mensajes**: El mensaje `REGISTER` debe llegar antes que `DATA`. TCP
  garantiza el orden; UDP no.
- **Detección de desconexión**: TCP notifica automáticamente cuando un cliente se
  desconecta (recv retorna 0), lo que permite al servidor marcar el sensor como
  inactivo. Con UDP no existe este mecanismo.

UDP sería justificable únicamente si la latencia fuera crítica y se tolerara pérdida
de datos (por ejemplo, streaming de video). Para monitoreo de sensores la
confiabilidad es prioritaria.

---

## 2. Formato general de mensajes

```
COMANDO arg1 arg2 arg3\n
```

- Cada mensaje ocupa exactamente **una línea** terminada en `\n`
- Los argumentos se separan por **espacios**
- El protocolo es **case-sensitive** (los comandos van en MAYÚSCULAS)
- Máximo 1024 bytes por mensaje

---

## 3. Mensajes: Sensor → Servidor

### 3.1 `REGISTER SENSOR`

Registra un nuevo sensor en el sistema. Debe ser el primer mensaje enviado.

```
REGISTER SENSOR <sensor_id> <tipo>
```

| Campo       | Descripción                                          |
|-------------|------------------------------------------------------|
| `sensor_id` | Identificador único del sensor (ej: `temp-001`)      |
| `tipo`      | Tipo de sensor: `temperature`, `vibration`, `energy` |

**Ejemplo:**
```
REGISTER SENSOR temp-001 temperature
```

**Respuesta exitosa:**
```
OK SENSOR_REGISTERED temp-001
```

**Respuestas de error:**
```
ERROR SENSOR_ALREADY_EXISTS temp-001
ERROR SERVER_FULL
```

---

### 3.2 `DATA`

Envía una medición periódica al servidor.

```
DATA <sensor_id> <tipo> <valor>
```

| Campo       | Descripción                          |
|-------------|--------------------------------------|
| `sensor_id` | ID del sensor previamente registrado |
| `tipo`      | Tipo de la medición                  |
| `valor`     | Valor numérico (punto decimal)       |

**Ejemplo:**
```
DATA temp-001 temperature 23.5
```

**Respuesta:**
```
OK DATA_RECEIVED
```

---

### 3.3 `DISCONNECT`

Notifica al servidor que el sensor se desconectará.

```
DISCONNECT <sensor_id>
```

**Ejemplo:**
```
DISCONNECT temp-001
```

**Respuesta:**
```
OK GOODBYE
```

---

## 4. Mensajes: Operador → Servidor

### 4.1 `REGISTER OPERATOR`

Registra un operador en el sistema. A partir de este momento recibirá alertas.

```
REGISTER OPERATOR <nombre>
```

**Ejemplo:**
```
REGISTER OPERATOR ana
```

**Respuesta:**
```
OK OPERATOR_REGISTERED ana
```

---

### 4.2 `LIST SENSORS`

Solicita la lista de todos los sensores activos y su último valor.

```
LIST SENSORS
```

**Respuesta:**
```
SENSOR_LIST [{id:temp-001,tipo:temperature,valor:23.50,ip:192.168.1.10}]
```

---

### 4.3 `GET HISTORY`

Solicita el historial de las últimas 20 mediciones de un sensor.

```
GET HISTORY <sensor_id>
```

**Ejemplo:**
```
GET HISTORY temp-001
```

**Respuesta:**
```
HISTORY temp-001 [{t:1718000000,v:23.50},{t:1718000060,v:24.10}]
```

| Campo | Descripción               |
|-------|---------------------------|
| `t`   | Timestamp Unix            |
| `v`   | Valor de la medición      |

---

## 5. Mensajes: Servidor → Operadores (alertas automáticas)

Cuando el servidor detecta una anomalía, **notifica a todos los operadores conectados**
de forma automática sin que lo soliciten.

```
ALERT <sensor_id> <tipo> <valor> <razon>
```

**Ejemplos:**
```
ALERT temp-001 temperature 45.20 TEMPERATURA_ALTA_(45.2_>_40.0)
ALERT vib-003 vibration 9.10 VIBRACION_ALTA_(9.1_>_8.0)
ALERT eng-002 energy 520.00 CONSUMO_ALTO_(520.0_>_500.0)
```

---

## 6. Umbrales de detección de anomalías

| Tipo de sensor | Variable   | Condición de alerta     |
|----------------|------------|-------------------------|
| `temperature`  | Temperatura| valor > 40.0 °C         |
| `temperature`  | Temperatura| valor < -10.0 °C        |
| `vibration`    | Vibración  | valor > 8.0 m/s²        |
| `energy`       | Energía    | valor > 500.0 W         |

---

## 7. Manejo de errores

| Código de error            | Causa                                      |
|----------------------------|--------------------------------------------|
| `ERROR UNKNOWN_COMMAND`    | Comando no reconocido                      |
| `ERROR SENSOR_ALREADY_EXISTS` | El sensor_id ya está registrado         |
| `ERROR SERVER_FULL`        | Se alcanzó el límite de clientes           |
| `ERROR SENSOR_NOT_FOUND`   | El sensor_id no existe en el sistema       |

Si la conexión se pierde inesperadamente (sin `DISCONNECT`), el servidor detecta
el cierre de socket y marca al cliente como inactivo automáticamente.

---

## 8. Flujo de comunicación típico

### Sensor

```
Sensor                          Servidor
  |                                |
  |-- REGISTER SENSOR temp-001 --> |
  |<-- OK SENSOR_REGISTERED ------|
  |                                |
  |-- DATA temp-001 temp 23.5 ---> |  (cada 5 segundos)
  |<-- OK DATA_RECEIVED ----------|
  |                                |
  |-- DATA temp-001 temp 45.5 ---> |  (valor anómalo)
  |<-- OK DATA_RECEIVED ----------|  (el servidor notifica operadores)
  |                                |
  |-- DISCONNECT temp-001 -------> |
  |<-- OK GOODBYE ----------------|
```

### Operador

```
Operador                        Servidor
  |                                |
  |-- REGISTER OPERATOR ana -----> |
  |<-- OK OPERATOR_REGISTERED ----|
  |                                |
  |-- LIST SENSORS ---------------> |
  |<-- SENSOR_LIST [...] ----------|
  |                                |
  |       (alerta automática)      |
  |<-- ALERT temp-001 ... ---------|
```

---

## 9. Resolución de nombres

El código no contiene direcciones IP hardcodeadas. Todos los servicios se localizan
mediante resolución DNS usando `getaddrinfo()` de la API POSIX.

El servidor es accesible mediante el nombre de dominio configurado en AWS Route 53:

