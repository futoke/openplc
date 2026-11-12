"""OpenPLC tank HMI: Modbus TCP + a lumped hydraulic tank model."""
import math
import os
import threading
import time

from flask import Flask, jsonify, render_template
from pymodbus.client import ModbusTcpClient

app = Flask(__name__)
lock = threading.RLock()  # One shared Modbus client, used by the simulation and HTTP requests
client = ModbusTcpClient(
    os.getenv("PLC_HOST", "openplc"),
    port=int(os.getenv("PLC_PORT", "502")),
    timeout=1,
)

# Modbus addresses, zero-based. OpenPLC coil mapping: %QX (16) followed by %MX (8).
COIL_PUMP, COIL_ALARM, COIL_AUTO = 8, 9, 10
COIL_START, COIL_STOP, COIL_RESET = 16, 17, 18
COIL_LOW, COIL_HIGH = 19, 20
SLAVE = 1

# Physical tank / pump parameters (SI units)
TANK_HEIGHT_M = 1.0
TANK_AREA_M2 = 0.10                # 100 litres when full
OUTLET_DIAMETER_M = 0.025
DISCHARGE_COEFFICIENT = 0.62
GRAVITY = 9.81
OUTLET_AREA_M2 = math.pi * OUTLET_DIAMETER_M**2 / 4
PUMP_MAX_FLOW_M3_S = 0.006         # 6 l/s at zero hydraulic head
PUMP_SHUTOFF_HEAD_M = 3.0         # Simplified pump curve: Q = Qmax*sqrt(1-h/Hmax)
LOW_SENSOR_M = TANK_HEIGHT_M * 0.25
HIGH_SENSOR_M = TANK_HEIGHT_M * 0.90
MAX_STEP_S = 0.05

height_m = 0.10 * TANK_HEIGHT_M
state = {
    "level": 10.0, "pump": False, "alarm": False, "auto": False,
    "connected": False, "error": "", "low": False, "high": False,
    "height_m": height_m, "inflow_l_s": 0.0, "outflow_l_s": 0.0,
}


def ensure_connection():
    if not client.connected and not client.connect():
        raise ConnectionError("OpenPLC Modbus TCP is unavailable")


def check_result(result):
    if result.isError():
        raise ConnectionError(str(result))
    return result


def read_outputs():
    with lock:
        ensure_connection()
        result = check_result(client.read_coils(COIL_PUMP, count=3, slave=SLAVE))
        return tuple(bool(v) for v in result.bits[:3])


def write_sensors(low, high):
    with lock:
        ensure_connection()
        check_result(client.write_coils(COIL_LOW, [low, high], slave=SLAVE))


def flows_at_height(h, pump_on):
    """Flows in m^3/s; outlet follows Torricelli, pump depends on head."""
    q_in = (PUMP_MAX_FLOW_M3_S * math.sqrt(max(0., 1. - h / PUMP_SHUTOFF_HEAD_M))) if pump_on else 0.
    q_out = DISCHARGE_COEFFICIENT * OUTLET_AREA_M2 * math.sqrt(2 * GRAVITY * max(0., h))
    return q_in, q_out


def integrate_tank(h, pump_on, dt):
    """Euler integration with small steps and physical 0..height bounds."""
    remaining = dt
    while remaining > 1e-9:
        step = min(MAX_STEP_S, remaining)
        q_in, q_out = flows_at_height(h, pump_on)
        h = max(0., min(TANK_HEIGHT_M, h + ((q_in - q_out) / TANK_AREA_M2) * step))
        remaining -= step
    q_in, q_out = flows_at_height(h, pump_on)
    return h, q_in, q_out


def simulation():
    global height_m
    last = time.monotonic()
    while True:
        time.sleep(0.25)
        now = time.monotonic()
        dt = min(now - last, 1.0)
        last = now
        try:
            pump, alarm, auto = read_outputs()
            # Do not advance the physics while disconnected from the PLC.
            height_m, q_in, q_out = integrate_tank(height_m, pump, dt)
            low = height_m >= LOW_SENSOR_M
            high = height_m >= HIGH_SENSOR_M
            write_sensors(low, high)
            with lock:
                state.update(
                    level=round(100 * height_m / TANK_HEIGHT_M, 2),
                    height_m=round(height_m, 4),
                    inflow_l_s=round(q_in * 1000, 3),
                    outflow_l_s=round(q_out * 1000, 3),
                    pump=pump, alarm=alarm, auto=auto,
                    low=low, high=high, connected=True, error="",
                )
        except Exception as exc:
            with lock:
                state.update(connected=False, error=str(exc), pump=False)
            client.close()


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/state")
def api_state():
    with lock:
        return jsonify(state.copy())


@app.post("/api/<command>")
def api_command(command):
    address = {"start": COIL_START, "stop": COIL_STOP, "reset": COIL_RESET}.get(command)
    if address is None:
        return jsonify(error="Unknown command"), 404
    try:
        # Keep the write active for several PLC cycles, always try to release it.
        with lock:
            ensure_connection()
            check_result(client.write_coil(address, True, slave=SLAVE))
        try:
            time.sleep(1.0)
        finally:
            with lock:
                ensure_connection()
                check_result(client.write_coil(address, False, slave=SLAVE))
        return jsonify(ok=True)
    except Exception as exc:
        client.close()
        return jsonify(error=str(exc)), 503


if __name__ == "__main__":
    threading.Thread(target=simulation, daemon=True).start()
    app.run(host="0.0.0.0", port=8080, threaded=True, use_reloader=False)
