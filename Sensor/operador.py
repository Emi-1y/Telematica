import socket
import threading
import time
import sys
import tkinter as tk
from tkinter import ttk, scrolledtext
from datetime import datetime


# ──────────────────────────────────────────────
#  CLIENTE DE RED (corre en hilo separado)
#  Maneja toda la comunicación con el servidor
#  sin bloquear la interfaz gráfica
# ──────────────────────────────────────────────

class ClienteRed:
    def __init__(self, host: str, puerto: int, nombre: str, gui_callback):
        self.host        = host
        self.puerto      = puerto
        self.nombre      = nombre
        self.gui_callback = gui_callback  # función para enviar eventos a la GUI
        self.sock        = None
        self.conectado   = False

    def conectar(self):
        """Resuelve DNS y establece conexión TCP."""
        try:
            self.gui_callback("log", f"Resolviendo {self.host}...")
            infos = socket.getaddrinfo(
                self.host, self.puerto, socket.AF_INET, socket.SOCK_STREAM
            )
            familia, tipo_sock, _, _, direccion = infos[0]
            self.gui_callback("log", f"DNS resuelto → {direccion[0]}")

            self.sock = socket.socket(familia, tipo_sock)
            self.sock.settimeout(10)
            self.sock.connect(direccion)
            self.conectado = True
            self.gui_callback("log", f"Conectado a {self.host}:{self.puerto}")
            self.gui_callback("estado", "Conectado")
            return True

        except socket.gaierror as e:
            self.gui_callback("error", f"Error DNS: no se pudo resolver '{self.host}'")
            return False
        except ConnectionRefusedError:
            self.gui_callback("error", f"Conexión rechazada en {self.host}:{self.puerto}")
            return False
        except Exception as e:
            self.gui_callback("error", f"Error de conexión: {e}")
            return False

    def enviar(self, mensaje: str) -> str:
        """Envía un mensaje y retorna la respuesta."""
        if not self.conectado or not self.sock:
            return "ERROR NOT_CONNECTED"
        try:
            self.sock.sendall((mensaje + "\n").encode("utf-8"))
            respuesta = self.sock.recv(4096).decode("utf-8").strip()
            return respuesta
        except Exception as e:
            self.conectado = False
            self.gui_callback("estado", "Desconectado")
            return f"ERROR {e}"

    def escuchar_alertas(self):
        """
        Corre en un hilo separado.
        Espera mensajes del servidor (alertas en tiempo real).
        El servidor puede mandar ALERT en cualquier momento.
        """
        self.sock.settimeout(None)  # sin timeout para escuchar indefinidamente
        while self.conectado:
            try:
                datos = self.sock.recv(1024).decode("utf-8").strip()
                if not datos:
                    break  # servidor cerró la conexión
                # Puede llegar más de un mensaje junto
                for linea in datos.split("\n"):
                    linea = linea.strip()
                    if linea.startswith("ALERT"):
                        self.gui_callback("alerta", linea)
                    elif linea:
                        self.gui_callback("log", f"Servidor: {linea}")
            except Exception:
                break

        self.conectado = False
        self.gui_callback("estado", "Desconectado")

    def desconectar(self):
        self.conectado = False
        if self.sock:
            try:
                self.sock.sendall(f"DISCONNECT {self.nombre}\n".encode())
            except Exception:
                pass
            self.sock.close()


# ──────────────────────────────────────────────
#  INTERFAZ GRÁFICA (tkinter)
# ──────────────────────────────────────────────

class AppOperador:
    def __init__(self, root: tk.Tk, host: str, puerto: int, nombre: str):
        self.root   = root
        self.nombre = nombre
        self.cliente = ClienteRed(host, puerto, nombre, self.recibir_evento)

        # Cola de eventos del hilo de red → hilo de GUI
        self.cola_eventos = []
        self.lock_cola    = threading.Lock()

        self._construir_ui()
        self._conectar()

        # Revisar la cola de eventos cada 100ms (evita problemas de hilos con tkinter)
        self.root.after(100, self._procesar_cola)

    # ── Construcción de la UI ─────────────────────────────────

    def _construir_ui(self):
        self.root.title(f"IoT Monitor — Operador: {self.nombre}")
        self.root.geometry("800x600")
        self.root.configure(bg="#f5f5f5")

        # ── Barra superior: estado y botones ──────────────────
        barra = tk.Frame(self.root, bg="#1e293b", pady=8)
        barra.pack(fill=tk.X)

        tk.Label(barra, text="IoT Monitor", font=("Helvetica", 14, "bold"),
                 fg="white", bg="#1e293b").pack(side=tk.LEFT, padx=12)

        tk.Label(barra, text=f"Operador: {self.nombre}", font=("Helvetica", 10),
                 fg="#94a3b8", bg="#1e293b").pack(side=tk.LEFT, padx=4)

        self.lbl_estado = tk.Label(barra, text="Conectando...",
                                   font=("Helvetica", 10, "bold"),
                                   fg="#fbbf24", bg="#1e293b")
        self.lbl_estado.pack(side=tk.RIGHT, padx=12)

        # ── Panel principal: 2 columnas ───────────────────────
        panel = tk.Frame(self.root, bg="#f5f5f5")
        panel.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)

        # Columna izquierda: sensores y controles
        izq = tk.Frame(panel, bg="#f5f5f5")
        izq.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))

        # Columna derecha: alertas
        der = tk.Frame(panel, bg="#f5f5f5")
        der.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(6, 0))

        # ── Tabla de sensores activos ─────────────────────────
        tk.Label(izq, text="Sensores activos", font=("Helvetica", 11, "bold"),
                 bg="#f5f5f5", anchor="w").pack(fill=tk.X, pady=(0, 4))

        cols = ("ID", "Tipo", "Último valor", "IP")
        self.tabla = ttk.Treeview(izq, columns=cols, show="headings", height=10)
        for col in cols:
            self.tabla.heading(col, text=col)
            self.tabla.column(col, width=90 if col != "ID" else 120)
        self.tabla.pack(fill=tk.BOTH, expand=True)

        # ── Botones de control ────────────────────────────────
        controles = tk.Frame(izq, bg="#f5f5f5", pady=6)
        controles.pack(fill=tk.X)

        tk.Button(controles, text="Actualizar sensores",
                  command=self._pedir_sensores,
                  bg="#3b82f6", fg="white", relief=tk.FLAT,
                  padx=10, pady=4).pack(side=tk.LEFT, padx=(0, 6))

        tk.Button(controles, text="Ver historial",
                  command=self._pedir_historial,
                  bg="#6366f1", fg="white", relief=tk.FLAT,
                  padx=10, pady=4).pack(side=tk.LEFT)

        # ── Log de actividad ──────────────────────────────────
        tk.Label(izq, text="Log de actividad", font=("Helvetica", 11, "bold"),
                 bg="#f5f5f5", anchor="w").pack(fill=tk.X, pady=(8, 4))

        self.txt_log = scrolledtext.ScrolledText(
            izq, height=8, font=("Courier", 9),
            bg="#1e293b", fg="#e2e8f0", insertbackground="white",
            state=tk.DISABLED, relief=tk.FLAT
        )
        self.txt_log.pack(fill=tk.BOTH, expand=True)

        # ── Panel de alertas ──────────────────────────────────
        tk.Label(der, text="Alertas en tiempo real", font=("Helvetica", 11, "bold"),
                 bg="#f5f5f5", fg="#dc2626", anchor="w").pack(fill=tk.X, pady=(0, 4))

        self.txt_alertas = scrolledtext.ScrolledText(
            der, height=30, font=("Courier", 9),
            bg="#fff1f2", fg="#991b1b", insertbackground="black",
            state=tk.DISABLED, relief=tk.FLAT
        )
        self.txt_alertas.pack(fill=tk.BOTH, expand=True)

    # ── Lógica de conexión ────────────────────────────────────

    def _conectar(self):
        """Conecta en un hilo para no bloquear la GUI."""
        def tarea():
            ok = self.cliente.conectar()
            if ok:
                # Registrar operador
                resp = self.cliente.enviar(f"REGISTER OPERATOR {self.nombre}")
                self.recibir_evento("log", f"Registro: {resp}")
                # Pedir lista inicial de sensores
                self._pedir_sensores()
                # Escuchar alertas en segundo plano
                hilo = threading.Thread(target=self.cliente.escuchar_alertas, daemon=True)
                hilo.start()

        threading.Thread(target=tarea, daemon=True).start()

    # ── Acciones del operador ─────────────────────────────────

    def _pedir_sensores(self):
        def tarea():
            resp = self.cliente.enviar("LIST SENSORS")
            self.recibir_evento("sensores", resp)
            self.recibir_evento("log", "Lista de sensores actualizada")
        threading.Thread(target=tarea, daemon=True).start()

    def _pedir_historial(self):
        """Pide el historial del sensor seleccionado en la tabla."""
        seleccion = self.tabla.selection()
        if not seleccion:
            self.recibir_evento("log", "Selecciona un sensor en la tabla primero")
            return
        sensor_id = self.tabla.item(seleccion[0])["values"][0]

        def tarea():
            resp = self.cliente.enviar(f"GET HISTORY {sensor_id}")
            self.recibir_evento("log", f"Historial {sensor_id}: {resp}")
        threading.Thread(target=tarea, daemon=True).start()

    # ── Sistema de eventos entre hilos ───────────────────────
    # tkinter NO es thread-safe: nunca toques widgets desde otro hilo.
    # Usamos una cola: el hilo de red deposita eventos,
    # el hilo principal los procesa cada 100ms.

    def recibir_evento(self, tipo: str, dato: str):
        """Llamado desde cualquier hilo — deposita en la cola."""
        with self.lock_cola:
            self.cola_eventos.append((tipo, dato))

    def _procesar_cola(self):
        """Llamado desde el hilo principal cada 100ms."""
        with self.lock_cola:
            eventos = self.cola_eventos[:]
            self.cola_eventos.clear()

        for tipo, dato in eventos:
            if tipo == "log":
                self._escribir_log(dato)
            elif tipo == "alerta":
                self._mostrar_alerta(dato)
            elif tipo == "estado":
                color = "#22c55e" if dato == "Conectado" else "#ef4444"
                self.lbl_estado.config(text=dato, fg=color)
            elif tipo == "error":
                self._escribir_log(f"ERROR: {dato}")
            elif tipo == "sensores":
                self._actualizar_tabla(dato)

        # Reprogramar para el siguiente ciclo
        self.root.after(100, self._procesar_cola)

    # ── Actualizar widgets ────────────────────────────────────

    def _escribir_log(self, texto: str):
        ahora = datetime.now().strftime("%H:%M:%S")
        self.txt_log.config(state=tk.NORMAL)
        self.txt_log.insert(tk.END, f"[{ahora}] {texto}\n")
        self.txt_log.see(tk.END)
        self.txt_log.config(state=tk.DISABLED)

    def _mostrar_alerta(self, alerta: str):
        # Parsear: ALERT sensor_id tipo valor razon
        partes = alerta.split()
        ahora  = datetime.now().strftime("%H:%M:%S")
        if len(partes) >= 5:
            sensor_id = partes[1]
            tipo      = partes[2]
            valor     = partes[3]
            razon     = " ".join(partes[4:])
            linea = f"[{ahora}] {sensor_id} | {tipo} = {valor} | {razon}\n"
        else:
            linea = f"[{ahora}] {alerta}\n"

        self.txt_alertas.config(state=tk.NORMAL)
        self.txt_alertas.insert(tk.END, linea)
        self.txt_alertas.see(tk.END)
        self.txt_alertas.config(state=tk.DISABLED)
        self._escribir_log(f"ALERTA recibida: {alerta}")

    def _actualizar_tabla(self, respuesta: str):
        """Parsea SENSOR_LIST y rellena la tabla."""
        # Limpiar tabla
        for item in self.tabla.get_children():
            self.tabla.delete(item)

        # Parsear formato: SENSOR_LIST [{id:x,tipo:y,valor:z,ip:w}...]
        # Extracción simple sin json (el formato no es JSON estándar)
        import re
        entradas = re.findall(r'\{([^}]+)\}', respuesta)
        for entrada in entradas:
            campos = {}
            for par in entrada.split(","):
                if ":" in par:
                    k, v = par.split(":", 1)
                    campos[k.strip()] = v.strip()
            if campos:
                self.tabla.insert("", tk.END, values=(
                    campos.get("id",    "—"),
                    campos.get("tipo",  "—"),
                    campos.get("valor", "—"),
                    campos.get("ip",    "—"),
                ))

    def cerrar(self):
        self.cliente.desconectar()
        self.root.destroy()


# ──────────────────────────────────────────────
#  PUNTO DE ENTRADA
# ──────────────────────────────────────────────

def main():
    if len(sys.argv) != 4:
        print("Uso: python3 operador.py <host> <puerto> <nombre>")
        print("Ej:  python3 operador.py localhost 8080 ana")
        sys.exit(1)

    host   = sys.argv[1]
    puerto = int(sys.argv[2])
    nombre = sys.argv[3]

    root = tk.Tk()
    app  = AppOperador(root, host, puerto, nombre)
    root.protocol("WM_DELETE_WINDOW", app.cerrar)
    root.mainloop()


if __name__ == "__main__":
    main()