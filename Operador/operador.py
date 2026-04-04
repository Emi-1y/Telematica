import socket
import threading
import sys
import re
import tkinter as tk
from tkinter import ttk, scrolledtext
from datetime import datetime


def crear_socket(host: str, puerto: int) -> socket.socket:
    """Resuelve DNS y devuelve un socket TCP conectado."""
    infos = socket.getaddrinfo(host, puerto, socket.AF_INET, socket.SOCK_STREAM)
    familia, tipo_sock, _, _, direccion = infos[0]
    sock = socket.socket(familia, tipo_sock)
    sock.connect(direccion)
    return sock


def enviar_recibir(sock: socket.socket, mensaje: str) -> str:
    sock.sendall((mensaje + "\n").encode("utf-8"))
    return sock.recv(4096).decode("utf-8").strip()


class AppOperador:
    def __init__(self, root: tk.Tk, host: str, puerto: int, nombre: str):
        self.root    = root
        self.host    = host
        self.puerto  = puerto
        self.nombre  = nombre
        self.sock_cmd   = None
        self.sock_alert = None
        self.conectado  = False
        self.cola   = []
        self.lock   = threading.Lock()
        self._construir_ui()
        self._conectar()
        self.root.after(100, self._procesar_cola)

    def _construir_ui(self):
        self.root.title(f"IoT Monitor — Operador: {self.nombre}")
        self.root.geometry("860x620")
        self.root.configure(bg="#f5f5f5")

        barra = tk.Frame(self.root, bg="#1e293b", pady=8)
        barra.pack(fill=tk.X)
        tk.Label(barra, text="IoT Monitor", font=("Helvetica", 14, "bold"),
                 fg="white", bg="#1e293b").pack(side=tk.LEFT, padx=12)
        tk.Label(barra, text=f"Operador: {self.nombre}",
                 font=("Helvetica", 10), fg="#94a3b8",
                 bg="#1e293b").pack(side=tk.LEFT, padx=4)
        self.lbl_estado = tk.Label(barra, text="Conectando...",
                                   font=("Helvetica", 10, "bold"),
                                   fg="#fbbf24", bg="#1e293b")
        self.lbl_estado.pack(side=tk.RIGHT, padx=12)

        panel = tk.Frame(self.root, bg="#f5f5f5")
        panel.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)
        izq = tk.Frame(panel, bg="#f5f5f5")
        izq.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        der = tk.Frame(panel, bg="#f5f5f5")
        der.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(6, 0))

        tk.Label(izq, text="Sensores activos", font=("Helvetica", 11, "bold"),
                 bg="#f5f5f5", anchor="w").pack(fill=tk.X, pady=(0, 4))
        cols = ("ID", "Tipo", "Último valor", "IP")
        self.tabla = ttk.Treeview(izq, columns=cols, show="headings", height=10)
        anchos = {"ID": 130, "Tipo": 110, "Último valor": 110, "IP": 120}
        for col in cols:
            self.tabla.heading(col, text=col)
            self.tabla.column(col, width=anchos[col], anchor="center")
        self.tabla.pack(fill=tk.BOTH, expand=True)

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

        tk.Label(izq, text="Log de actividad", font=("Helvetica", 11, "bold"),
                 bg="#f5f5f5", anchor="w").pack(fill=tk.X, pady=(8, 4))
        self.txt_log = scrolledtext.ScrolledText(
            izq, height=8, font=("Courier", 9),
            bg="#1e293b", fg="#e2e8f0",
            state=tk.DISABLED, relief=tk.FLAT)
        self.txt_log.pack(fill=tk.BOTH, expand=True)

        tk.Label(der, text="Alertas en tiempo real",
                 font=("Helvetica", 11, "bold"),
                 bg="#f5f5f5", fg="#dc2626", anchor="w").pack(fill=tk.X, pady=(0, 4))
        self.txt_alertas = scrolledtext.ScrolledText(
            der, height=30, font=("Courier", 9),
            bg="#fff1f2", fg="#991b1b",
            state=tk.DISABLED, relief=tk.FLAT)
        self.txt_alertas.pack(fill=tk.BOTH, expand=True)

    def _conectar(self):
        def tarea():
            try:
                self._evento("log", f"Resolviendo {self.host}...")
                # Socket 1: solo para enviar comandos y recibir respuestas
                self.sock_cmd = crear_socket(self.host, self.puerto)
                self.sock_cmd.settimeout(8)
                resp = enviar_recibir(self.sock_cmd, f"REGISTER OPERATOR {self.nombre}_cmd")
                self._evento("log", f"Comandos OK: {resp}")

                # Socket 2: solo para recibir alertas en tiempo real
                self.sock_alert = crear_socket(self.host, self.puerto)
                self.sock_alert.settimeout(None)
                resp2 = enviar_recibir(self.sock_alert, f"REGISTER OPERATOR {self.nombre}")
                self._evento("log", f"Alertas OK: {resp2}")

                self.conectado = True
                self._evento("estado", "Conectado")
                self._pedir_sensores()

                hilo = threading.Thread(target=self._escuchar_alertas, daemon=True)
                hilo.start()

            except Exception as e:
                self._evento("error", f"No se pudo conectar: {e}")

        threading.Thread(target=tarea, daemon=True).start()

    def _escuchar_alertas(self):
        while self.conectado:
            try:
                datos = self.sock_alert.recv(2048).decode("utf-8")
                if not datos:
                    break
                for linea in datos.split("\n"):
                    linea = linea.strip()
                    if linea.startswith("ALERT"):
                        self._evento("alerta", linea)
            except OSError:
                break
        self.conectado = False
        self._evento("estado", "Desconectado")

    def _pedir_sensores(self):
        def tarea():
            if not self.conectado or not self.sock_cmd:
                return
            try:
                resp = enviar_recibir(self.sock_cmd, "LIST SENSORS")
                self._evento("sensores", resp)
                self._evento("log", "Tabla actualizada")
            except Exception as e:
                self._evento("log", f"Error sensores: {e}")
        threading.Thread(target=tarea, daemon=True).start()

    def _pedir_historial(self):
        seleccion = self.tabla.selection()
        if not seleccion:
            self._evento("log", "Selecciona un sensor en la tabla primero")
            return
        sensor_id = self.tabla.item(seleccion[0])["values"][0]
        def tarea():
            try:
                resp = enviar_recibir(self.sock_cmd, f"GET HISTORY {sensor_id}")
                self._evento("log", f"Historial {sensor_id}: {resp}")
            except Exception as e:
                self._evento("log", f"Error historial: {e}")
        threading.Thread(target=tarea, daemon=True).start()

    def _evento(self, tipo: str, dato: str):
        with self.lock:
            self.cola.append((tipo, dato))

    def _procesar_cola(self):
        with self.lock:
            eventos = self.cola[:]
            self.cola.clear()
        for tipo, dato in eventos:
            if tipo == "log":
                self._log(dato)
            elif tipo == "alerta":
                self._mostrar_alerta(dato)
            elif tipo == "estado":
                color = "#22c55e" if dato == "Conectado" else "#ef4444"
                self.lbl_estado.config(text=dato, fg=color)
            elif tipo == "error":
                self._log(f"ERROR: {dato}")
                self.lbl_estado.config(text="Error", fg="#ef4444")
            elif tipo == "sensores":
                self._actualizar_tabla(dato)
        self.root.after(100, self._procesar_cola)

    def _log(self, texto: str):
        ahora = datetime.now().strftime("%H:%M:%S")
        self.txt_log.config(state=tk.NORMAL)
        self.txt_log.insert(tk.END, f"[{ahora}] {texto}\n")
        self.txt_log.see(tk.END)
        self.txt_log.config(state=tk.DISABLED)

    def _mostrar_alerta(self, alerta: str):
        partes = alerta.split()
        ahora  = datetime.now().strftime("%H:%M:%S")
        if len(partes) >= 5:
            linea = f"[{ahora}] {partes[1]} | {partes[2]} = {partes[3]} | {' '.join(partes[4:])}\n"
        else:
            linea = f"[{ahora}] {alerta}\n"
        self.txt_alertas.config(state=tk.NORMAL)
        self.txt_alertas.insert(tk.END, linea)
        self.txt_alertas.see(tk.END)
        self.txt_alertas.config(state=tk.DISABLED)
        self._log(f"ALERTA: {alerta}")

    def _actualizar_tabla(self, respuesta: str):
        for item in self.tabla.get_children():
            self.tabla.delete(item)

        entradas = re.findall(r'\{([^}]+)\}', respuesta)
        for entrada in entradas:
            campos = {}
            for par in entrada.split(","):
                if ":" in par:
                    k, v = par.split(":", 1)
                    campos[k.strip()] = v.strip()
            if not campos:
                continue
            tipo   = campos.get("tipo", "")
            val    = campos.get("valor", "—")
            unidad = {"temperature": "°C", "vibration": "m/s²", "energy": "W"}.get(tipo, "")
            self.tabla.insert("", tk.END, values=(
                campos.get("id", "—"),
                tipo,
                f"{val} {unidad}".strip(),
                campos.get("ip", "—"),
            ))

    def cerrar(self):
        self.conectado = False
        for sock in [self.sock_cmd, self.sock_alert]:
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass
        self.root.destroy()


def main():
    if len(sys.argv) != 4:
        print("Uso: python operador.py <host> <puerto> <nombre>")
        sys.exit(1)
    host, puerto, nombre = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    root = tk.Tk()
    app  = AppOperador(root, host, puerto, nombre)
    root.protocol("WM_DELETE_WINDOW", app.cerrar)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        app.cerrar()

if __name__ == "__main__":
    main()