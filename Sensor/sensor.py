import socket
import time
import random
import sys

# ──────────────────────────────────────────────
#  CONFIGURACIÓN DE VALORES SIMULADOS
#  Cada tipo de sensor tiene un rango "normal"
#  y ocasionalmente genera valores anómalos
# ──────────────────────────────────────────────
RANGOS = {
    "temperature": {"min": 15.0, "max": 35.0, "anomalia": 45.0, "unidad": "°C"},
    "vibration":   {"min": 0.1,  "max": 0.8,  "anomalia": 1.5,  "unidad": "g"},
    "energy":      {"min": 100,  "max": 400,  "anomalia": 550,  "unidad": "W"},
    "humidity":    {"min": 30.0, "max": 75.0, "anomalia": 95.0, "unidad": "%"},
}

INTERVALO_SEGUNDOS = 5   # cada cuánto envía una medición
PROB_ANOMALIA      = 0.1  # 10% de probabilidad de generar valor anómalo


def generar_valor(tipo: str) -> float:
    """Genera un valor simulado para el tipo de sensor dado."""
    rango = RANGOS[tipo]
    # 10% de las veces genera un valor anómalo para probar las alertas
    if random.random() < PROB_ANOMALIA:
        return round(rango["anomalia"] + random.uniform(0, 5), 2)
    return round(random.uniform(rango["min"], rango["max"]), 2)


def conectar(host: str, puerto: int) -> socket.socket:
    """
    Resuelve el nombre de dominio y establece conexión TCP.
    Usa getaddrinfo() — nunca IPs hardcodeadas.
    """
    print(f"[DNS] Resolviendo {host}...")

    # getaddrinfo hace la resolución DNS automáticamente
    # si host es un nombre de dominio, lo resuelve a IP
    # si es una IP directa, la usa tal cual
    infos = socket.getaddrinfo(host, puerto, socket.AF_INET, socket.SOCK_STREAM)

    if not infos:
        raise ConnectionError(f"No se pudo resolver el host: {host}")

    # Tomar la primera dirección resuelta
    familia, tipo_sock, proto, _, direccion = infos[0]
    ip_resuelta = direccion[0]
    print(f"[DNS] Resuelto → {ip_resuelta}")

    # Crear socket TCP
    sock = socket.socket(familia, tipo_sock)
    sock.settimeout(10)  # timeout de 10 segundos para operaciones de red
    sock.connect(direccion)
    print(f"[TCP] Conectado a {host}:{puerto}")
    return sock


def enviar_mensaje(sock: socket.socket, mensaje: str) -> str:
    """Envía un mensaje y espera la respuesta del servidor."""
    # El protocolo define que cada mensaje termina en \n
    sock.sendall((mensaje + "\n").encode("utf-8"))

    # Esperar respuesta
    respuesta = sock.recv(1024).decode("utf-8").strip()
    return respuesta


def main():
    if len(sys.argv) != 5:
        print("Uso: python3 sensor.py <host> <puerto> <sensor_id> <tipo>")
        print("Ej:  python3 sensor.py localhost 8080 temp-001 temperature")
        sys.exit(1)

    host      = sys.argv[1]
    puerto    = int(sys.argv[2])
    sensor_id = sys.argv[3]
    tipo      = sys.argv[4]

    if tipo not in RANGOS:
        print(f"Error: tipo debe ser uno de {list(RANGOS.keys())}")
        sys.exit(1)

    unidad = RANGOS[tipo]["unidad"]
    sock   = None

    try:
        # ── 1. Conectar al servidor ──────────────────────────
        sock = conectar(host, puerto)

        # ── 2. Registrar el sensor ───────────────────────────
        respuesta = enviar_mensaje(sock, f"REGISTER SENSOR {sensor_id} {tipo}")
        print(f"[REGISTRO] {respuesta}")

        if "ERROR" in respuesta:
            print("No se pudo registrar. Saliendo.")
            return

        # ── 3. Loop de envío de mediciones ───────────────────
        print(f"\n[INFO] Enviando mediciones cada {INTERVALO_SEGUNDOS}s. Ctrl+C para detener.\n")

        while True:
            valor = generar_valor(tipo)
            mensaje = f"DATA {sensor_id} {tipo} {valor}"
            respuesta = enviar_mensaje(sock, mensaje)

            estado = "ANOMALIA" if valor > RANGOS[tipo]["max"] else "normal"
            print(f"[DATA] {sensor_id} → {valor} {unidad:5s} [{estado}] | Servidor: {respuesta}")

            time.sleep(INTERVALO_SEGUNDOS)

    except KeyboardInterrupt:
        # El usuario presionó Ctrl+C — desconexión limpia
        print("\n[INFO] Desconectando...")
        if sock:
            try:
                enviar_mensaje(sock, f"DISCONNECT {sensor_id}")
            except Exception:
                pass

    except socket.gaierror as e:
        # Error de resolución DNS
        print(f"[ERROR DNS] No se pudo resolver '{host}': {e}")

    except ConnectionRefusedError:
        print(f"[ERROR] Conexión rechazada. ¿Está el servidor corriendo en {host}:{puerto}?")

    except socket.timeout:
        print("[ERROR] Timeout — el servidor no respondió.")

    except OSError as e:
        # Error de red genérico (conexión perdida, etc.)
        print(f"[ERROR RED] {e}")

    finally:
        if sock:
            sock.close()
            print("[TCP] Socket cerrado.")


if __name__ == "__main__":
    main()