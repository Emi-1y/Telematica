import socket
import requests
import os
from flask import Flask, render_template, request, redirect, url_for, session, flash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'default_secret_key_12345')

# Configuración de servicios desde variables de entorno para Docker
IOT_SERVER_HOST = os.environ.get('IOT_SERVER_HOST', 'localhost')
IOT_SERVER_PORT = int(os.environ.get('IOT_SERVER_PORT', 8080))
AUTH_SERVICE_URL = os.environ.get('AUTH_SERVICE_URL', 'http://localhost:5001')

def query_iot_server(command: str) -> str:
    """Envía un comando al servidor C por socket y retorna la respuesta."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5)
            s.connect((IOT_SERVER_HOST, IOT_SERVER_PORT))
            s.sendall(f"{command}\n".encode('utf-8'))
            data = s.recv(4096)
            return data.decode('utf-8').strip()
    except Exception as e:
        return f"ERROR_CONEXION: {e}"

def parse_status(raw):
    """Parsea 'STATUS OK uptime:86 sensors:1 operators:1'"""
    # System Status: ACTIVE, Uptime: X seconds, Connected Sensors: Y
    if "ERROR" in raw: return {"status": "INACTIVE", "uptime": "0", "sensors": "0", "alerts": "0"}
    parts = raw.split()
    res = {"status": "ACTIVE" if "OK" in raw else "INACTIVE", "uptime": "0", "sensors": "0", "alerts": "0"}
    for p in parts:
        if "uptime:" in p: res["uptime"] = p.split(":")[1]
        if "sensors:" in p: res["sensors"] = p.split(":")[1]
    return res

def parse_sensors(raw):
    """Parsea 'SENSOR_LIST [{id:s1,tipo:temp,valor:25.5,...}]' -> 'ID → Valor ⚠️'"""
    import re
    if "SENSOR_LIST" not in raw: return []
    items = re.findall(r'\{id:([^,]+),tipo:([^,]+),valor:([^,]+)', raw)
    formatted = []
    for sid, stype, sval in items:
        val_f = float(sval)
        marker = ""
        # Lógica de anomalía simple para el frontend (espejo del servidor C)
        if (stype == "temperature" and (val_f > 40 or val_f < -10)) or \
           (stype == "vibration" and val_f > 8.0) or \
           (stype == "energy" and val_f > 500):
            marker = " ⚠️ HIGH VALUE"
        formatted.append(f"{sid} → {val_f}{'°C' if 'temp' in stype else ''} {marker}")
    return formatted

def parse_alerts(raw):
    """Parsea 'ALERTS [{id:s1,t:temp,v:45.0,r:RAZON,ts:1234567},...]'"""
    import re
    from datetime import datetime
    if "ALERTS" not in raw: return []
    items = re.findall(r'\{id:([^,]+),t:([^,]+),v:([^,]+),r:([^,]+),ts:([^}]+)\}', raw)
    formatted = []
    for sid, stype, sval, sreason, sts in items:
        dt = datetime.fromtimestamp(int(sts))
        time_str = dt.strftime("%H:%M")
        formatted.append(f"[{time_str}] {sid} → {sreason} ({sval})")
    return formatted

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        try:
            # Llamar al servicio de autenticación externo
            response = requests.post(f"{AUTH_SERVICE_URL}/auth/login", 
                                  json={"username": username, "password": password},
                                  timeout=5)
            if response.status_code == 200:
                user_data = response.json().get('user', {})
                session['username'] = user_data.get('username')
                session['role'] = user_data.get('role')
                session['view_only'] = (user_data.get('role') == 'operator')
                flash(f"Welcome {username}", "success")
                return redirect(url_for('dashboard'))
            else:
                flash("Invalid credentials", "error")
        except Exception as e:
            flash(f"Error de conexión con servicio Auth: {e}", "error")
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/status')
def status():
    """Requirement 4: structured information"""
    if 'username' not in session:
        return redirect(url_for('login'))
    
    raw = query_iot_server("GET_STATUS")
    stats = parse_status(raw)
    
    alerts_raw = query_iot_server("GET_ALERTS")
    import re
    stats["alerts"] = len(re.findall(r'\{', alerts_raw))
    
    return render_template('status.html',
                            username=session['username'], 
                            role=session['role'],
                            view_only=session.get('view_only', False),
                            stats=stats)

@app.route('/dashboard')
def dashboard():
    """Main Operator View for Demo"""
    if 'username' not in session:
        return redirect(url_for('login'))
    
    # 1. Fetch Summary
    raw = query_iot_server("GET_STATUS")
    stats = parse_status(raw)
    
    # 2. Fetch Active Sensors and Real-time Measurements
    sensors_raw = query_iot_server("LIST_SENSORS")
    sensors_list = parse_sensors(sensors_raw)
    
    # 3. Fetch Alerts
    alerts_raw = query_iot_server("GET_ALERTS")
    alerts_list = parse_alerts(alerts_raw)
    
    return render_template('dashboard.html', 
                            username=session['username'], 
                            role=session['role'],
                            view_only=session.get('view_only', False),
                            stats=stats,
                            sensors_list=sensors_list,
                            alerts_list=alerts_list)

@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/sensors')
def sensors():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    # Consultar lista de sensores y parsear al formato ID → Valor
    sensors_raw = query_iot_server("LIST_SENSORS")
    sensors_list = parse_sensors(sensors_raw)
    return render_template('sensors.html', 
                            username=session['username'], 
                            role=session['role'],
                            view_only=session.get('view_only', False),
                            sensors_raw=sensors_raw,
                            sensors_list=sensors_list)

@app.route('/alerts')
def alerts():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    # Consultar alertas recientes y parsear al formato [Time] ID → Alert
    alerts_raw = query_iot_server("GET_ALERTS")
    alerts_list = parse_alerts(alerts_raw)
    return render_template('alerts.html', 
                            username=session['username'], 
                            role=session['role'],
                            view_only=session.get('view_only', False),
                            alerts_raw=alerts_raw,
                            alerts_list=alerts_list)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
