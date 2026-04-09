# ============================================================
# HORUS GCS v3.0 — BACKEND DE TELEMETRÍA
# ============================================================

import time, math, json, random
from dataclasses import dataclass
from PyQt6 import QtCore

try:
    import serial
    import serial.tools.list_ports
    SERIAL_DISPONIBLE = True
except ImportError:
    SERIAL_DISPONIBLE = False


# ── Modelo de datos ──────────────────────────────────────────

@dataclass
class DatosTelemetria:
    tiempo:         float = 0.0
    altitud:        float = 0.0
    velocidad:      float = 0.0
    aceleracion_y:  float = 0.0
    aceleracion_x:  float = 0.0
    aceleracion_z:  float = 0.0
    pitch:          float = 0.0
    roll:           float = 0.0
    yaw:            float = 0.0
    latitud:        float = 27.9174
    longitud:       float = -110.8975
    presion:        float = 1013.25
    temperatura:    float = 25.0
    satelites:      int   = 0
    etapa:          str   = "PREVIA"
    mensaje:        str   = "SISTEMAS EN LINEA"
    paracaidas:     bool  = False
    motor_activo:   bool  = False
    en_falla:       bool  = False
    bateria:        float = 100.0
    rssi:           int   = -60


# ── Simulador de física ──────────────────────────────────────

class FisicaVuelo:
    """
    Etapas: PREVIA → IGNICION → MOTOR_ACTIVO → APOGEO
            → DESCENSO (normal) ó FALLA (balística)
            → ATERRIZAJE
    """
    G            = 9.80665
    MASA         = 1.2
    EMPUJE       = 150.0
    T_MOTOR      = 3.2
    AREA_CUERPO  = 0.03
    AREA_CHUTE   = 0.8
    CD_CUERPO    = 0.45
    CD_CHUTE     = 1.5
    RHO0         = 1.225
    PROB_FALLA   = 0.20   # 20 % de probabilidad de falla en apogeo

    def __init__(self):
        self.reiniciar()

    def reiniciar(self):
        self.t          = 0.0
        self.altitud    = 0.0
        self.velocidad  = 0.0
        self.etapa      = "PREVIA"
        self.paracaidas = False
        self.en_falla   = False
        self._vel_prev  = 0.0
        self._t_inicio_etapa = 0.0

    # ── paso principal ────────────────────────────────────────

    def paso(self, dt: float = 0.05) -> DatosTelemetria:
        self.t += dt
        self._fisica(dt)
        return self._construir()

    def _fisica(self, dt):
        e = self.etapa

        if e == "PREVIA":
            if self.t >= 2.0:
                self._cambiar_etapa("IGNICION")
            return

        if e == "IGNICION":
            # Empuje parcial durante encendido
            self.velocidad += (self.EMPUJE * 0.4 / self.MASA - self.G) * dt
            self.altitud    = max(0.0, self.altitud + self.velocidad * dt)
            if self.t - self._t_inicio_etapa >= 0.5:
                self._cambiar_etapa("MOTOR_ACTIVO")
            return

        if e == "MOTOR_ACTIVO":
            te     = self.t - self._t_inicio_etapa
            factor = max(0.0, 1.0 - te / self.T_MOTOR)
            empuje = self.EMPUJE * factor
            rho    = self.RHO0 * math.exp(-self.altitud / 8500)
            drag   = 0.5 * rho * self.CD_CUERPO * self.AREA_CUERPO * self.velocidad ** 2
            drag  *= (-1 if self.velocidad > 0 else 1)
            self.velocidad += (empuje / self.MASA + drag / self.MASA - self.G) * dt
            self.altitud    = max(0.0, self.altitud + self.velocidad * dt)
            if te >= self.T_MOTOR and self.velocidad < 0:
                self._cambiar_etapa("APOGEO")
            return

        if e == "APOGEO":
            # Decide si hay falla
            if random.random() < self.PROB_FALLA:
                self.en_falla = True
                self._cambiar_etapa("FALLA")
            else:
                self.paracaidas = True
                self._cambiar_etapa("DESCENSO")
            return

        if e == "DESCENSO":
            rho   = self.RHO0 * math.exp(-self.altitud / 8500)
            drag  = 0.5 * rho * self.CD_CHUTE * self.AREA_CHUTE * self.velocidad ** 2
            drag *= (-1 if self.velocidad > 0 else 1)
            self.velocidad  = max(self.velocidad + (drag / self.MASA - self.G) * dt, -7.0)
            self.altitud    = max(0.0, self.altitud + self.velocidad * dt)
            if self.altitud <= 0:
                self._cambiar_etapa("ATERRIZAJE")
            return

        if e == "FALLA":
            # Caída balística libre
            rho   = self.RHO0 * math.exp(-self.altitud / 8500)
            drag  = 0.5 * rho * self.CD_CUERPO * self.AREA_CUERPO * self.velocidad ** 2
            drag *= (-1 if self.velocidad > 0 else 1)
            self.velocidad += (drag / self.MASA - self.G) * dt
            self.altitud    = max(0.0, self.altitud + self.velocidad * dt)
            if self.altitud <= 0:
                self._cambiar_etapa("ATERRIZAJE")
            return

        if e == "ATERRIZAJE":
            self.velocidad = 0.0
            self.altitud   = 0.0
            if self.t - self._t_inicio_etapa > 6.0:
                self.reiniciar()
            return

    def _cambiar_etapa(self, nueva):
        self.etapa              = nueva
        self._t_inicio_etapa    = self.t

    # ── construcción del dato ─────────────────────────────────

    def _construir(self) -> DatosTelemetria:
        acc_y          = (self.velocidad - self._vel_prev) / 0.05
        self._vel_prev = self.velocidad
        e              = self.etapa

        # Orientación simulada
        if e in ("IGNICION", "MOTOR_ACTIVO"):
            pitch = 90.0 - min(15.0, (self.t - self._t_inicio_etapa) * 2)
            roll  = (self.t * 30) % 360
            yaw   = (self.t * 5)  % 360
        elif e == "FALLA":
            pitch = random.uniform(-180, 180)
            roll  = random.uniform(-180, 180)
            yaw   = (self.t * 40) % 360
        elif e == "DESCENSO":
            pitch = -20.0
            roll  = (self.t * 8) % 360
            yaw   = (self.t * 3) % 360
        else:
            pitch = 0.0; roll = 0.0; yaw = 0.0

        lat = 27.9174  + self.altitud * 5e-6 * math.sin(self.t * 0.1)
        lon = -110.8975 + self.altitud * 5e-6 * math.cos(self.t * 0.1)

        return DatosTelemetria(
            tiempo        = round(self.t, 2),
            altitud       = max(0.0, self.altitud),
            velocidad     = round(self.velocidad, 2),
            aceleracion_y = round(acc_y / self.G, 3),
            aceleracion_x = round(random.gauss(0, 0.03), 3),
            aceleracion_z = round(random.gauss(0, 0.03), 3),
            pitch         = round(pitch, 1),
            roll          = round(roll,  1),
            yaw           = round(yaw,   1),
            latitud       = round(lat, 6),
            longitud      = round(lon, 6),
            presion       = round(1013.25 * math.exp(-self.altitud / 8434), 2),
            temperatura   = round(25.0 - self.altitud / 1000 * 6.5, 1),
            satelites     = random.choice([8, 9, 10, 10, 11]),
            etapa         = e,
            mensaje       = self._msg(e),
            paracaidas    = self.paracaidas,
            motor_activo  = e in ("IGNICION", "MOTOR_ACTIVO"),
            en_falla      = self.en_falla,
            bateria       = round(max(20.0, 100.0 - self.t * 0.04), 1),
            rssi          = int(-60 - self.altitud * 0.008 + random.gauss(0, 1.5)),
        )

    @staticmethod
    def _msg(e):
        return {
            "PREVIA":       "COHETE EN RAMPA — ESPERANDO IGNICION",
            "IGNICION":     "IGNICION DETECTADA — ENCENDIENDO MOTOR",
            "MOTOR_ACTIVO": "MOTOR ACTIVO — ASCENSO NOMINAL",
            "APOGEO":       "APOGEO — EVALUANDO SISTEMA DE RECUPERACION",
            "DESCENSO":     "DESCENSO CON PARACAIDAS — NOMINAL",
            "FALLA":        "¡FALLA! DESCENSO BALISTICO — SIN PARACAIDAS",
            "ATERRIZAJE":   "ATERRIZAJE — MISION COMPLETADA",
        }.get(e, "ESTADO DESCONOCIDO")


# ── Worker (hilo productor a 20 Hz) ─────────────────────────

class WorkerTelemetria(QtCore.QObject):
    dato_recibido = QtCore.pyqtSignal(DatosTelemetria)
    error_serial  = QtCore.pyqtSignal(str)

    INTERVALO = 0.05   # 20 Hz

    def __init__(self):
        super().__init__()
        self._corriendo = True
        self.modo       = "Simulacion"
        self.fisica     = FisicaVuelo()
        self._serial    = None

    # ── control ───────────────────────────────────────────────

    def reiniciar_simulacion(self):
        self.fisica.reiniciar()

    def conectar_arduino(self, puerto: str, baudrate: int = 115200) -> bool:
        if not SERIAL_DISPONIBLE:
            self.error_serial.emit("pyserial no instalado — pip install pyserial")
            return False
        try:
            self._serial = serial.Serial(puerto, baudrate, timeout=1)
            self.modo    = "Arduino"
            return True
        except Exception as exc:
            self.error_serial.emit(f"Error al conectar {puerto}: {exc}")
            return False

    def desconectar_arduino(self):
        try:
            if self._serial and self._serial.is_open:
                self._serial.close()
        except Exception:
            pass
        self._serial = None
        self.modo    = "Simulacion"

    # ── bucle ─────────────────────────────────────────────────

    @QtCore.pyqtSlot()
    def procesar(self):
        while self._corriendo:
            t0 = time.monotonic()
            dato = self._leer()
            if dato is not None:
                self.dato_recibido.emit(dato)
            elapsed = time.monotonic() - t0
            rest = self.INTERVALO - elapsed
            if rest > 0:
                time.sleep(rest)

    def _leer(self):
        if self.modo == "Simulacion":
            return self.fisica.paso(self.INTERVALO)

        if self.modo == "Arduino":
            if self._serial and self._serial.is_open:
                try:
                    linea = self._serial.readline().decode("utf-8", errors="ignore")
                    return self._parsear(linea)
                except Exception as exc:
                    self.error_serial.emit(str(exc)[:80])
            # Arduino esperando — dato de espera
            return DatosTelemetria(etapa="OFFLINE", mensaje="ESPERANDO ARDUINO...")

        return None

    # ── parser CSV / JSON ─────────────────────────────────────

    def _parsear(self, linea: str):
        linea = linea.strip()
        if not linea:
            return None
        try:
            if linea.startswith("{"):
                d = json.loads(linea)
                return DatosTelemetria(
                    altitud       = float(d.get("alt",   0)),
                    velocidad     = float(d.get("vel",   0)),
                    aceleracion_x = float(d.get("ax",    0)),
                    aceleracion_y = float(d.get("ay",    0)),
                    aceleracion_z = float(d.get("az",    0)),
                    pitch         = float(d.get("pitch", 0)),
                    roll          = float(d.get("roll",  0)),
                    yaw           = float(d.get("yaw",   0)),
                    latitud       = float(d.get("lat",   27.9174)),
                    longitud      = float(d.get("lon",  -110.8975)),
                    presion       = float(d.get("pres",  1013.25)),
                    temperatura   = float(d.get("temp",  25.0)),
                    satelites     = int(d.get("sats",    0)),
                    etapa         = d.get("etapa", "MOTOR_ACTIVO"),
                    mensaje       = d.get("msg",   "DATOS ARDUINO"),
                    paracaidas    = bool(d.get("chute", False)),
                    motor_activo  = bool(d.get("motor", False)),
                    bateria       = float(d.get("bat",   100.0)),
                    rssi          = int(d.get("rssi",   -70)),
                )
            else:
                p = linea.split(",")
                if len(p) < 8:
                    return None
                return DatosTelemetria(
                    altitud       = float(p[0]),
                    velocidad     = float(p[1]),
                    aceleracion_x = float(p[2]),
                    aceleracion_y = float(p[3]),
                    aceleracion_z = float(p[4]),
                    pitch         = float(p[5]),
                    roll          = float(p[6]),
                    yaw           = float(p[7]),
                    latitud       = float(p[8])  if len(p) > 8  else 27.9174,
                    longitud      = float(p[9])  if len(p) > 9  else -110.8975,
                    presion       = float(p[10]) if len(p) > 10 else 1013.25,
                    temperatura   = float(p[11]) if len(p) > 11 else 25.0,
                    satelites     = int(p[12])   if len(p) > 12 else 0,
                    etapa         = "MOTOR_ACTIVO",
                    mensaje       = "DATOS ARDUINO (CSV)",
                )
        except Exception:
            return None
