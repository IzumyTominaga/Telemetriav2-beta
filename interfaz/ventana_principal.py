# ============================================================
# HORUS GCS v3.0 — VENTANA PRINCIPAL
#
# Decisiones de estabilidad:
#   · Visor3D se crea UNA sola vez y vive en un QStackedWidget.
#     Cambiar de pestaña no lo destruye ni re-inicializa.
#   · El QTabWidget central alterna entre: Visor3D, Mapa,
#     Horizonte, Arduino — sin usar el visor3d dentro del tab
#     directamente (lo mantiene el stack externo).
#   · Actualizaciones de UI a 20 Hz mediante señal del worker.
#   · Gráficas con decimación: solo se redibujan cada 3 datos.
# ============================================================

from PyQt6 import QtWidgets, QtCore, QtWebEngineWidgets
import pyqtgraph as pg

from Telemetry.configuracion import TEMA_HORUS, COLORES_ETAPA
from backend.telemetria      import DatosTelemetria, WorkerTelemetria, SERIAL_DISPONIBLE
from interfaz.componentes    import (
    MetricaVuelo, LogMision, PanelEtapa, IndicadorEstado, HorizonteArtificial
)
from interfaz.visor3d import Visor3D

try:
    import serial.tools.list_ports
except ImportError:
    pass


# ── Panel Arduino ────────────────────────────────────────────

class PanelArduino(QtWidgets.QWidget):
    sig_conectar    = QtCore.pyqtSignal(str, int)
    sig_desconectar = QtCore.pyqtSignal()

    def __init__(self):
        super().__init__()
        lay = QtWidgets.QVBoxLayout(self)

        gb = QtWidgets.QGroupBox("CONEXIÓN ARDUINO / SERIAL")
        g  = QtWidgets.QGridLayout(gb)

        g.addWidget(QtWidgets.QLabel("Puerto:"), 0, 0)
        self._puerto = QtWidgets.QComboBox()
        g.addWidget(self._puerto, 0, 1)
        br = QtWidgets.QPushButton("↻")
        br.setFixedWidth(32)
        br.clicked.connect(self._refrescar)
        g.addWidget(br, 0, 2)

        g.addWidget(QtWidgets.QLabel("Baudrate:"), 1, 0)
        self._baud = QtWidgets.QComboBox()
        for b in (9600, 19200, 38400, 57600, 115200, 230400):
            self._baud.addItem(str(b))
        self._baud.setCurrentText("115200")
        g.addWidget(self._baud, 1, 1, 1, 2)

        self._btn = QtWidgets.QPushButton("CONECTAR")
        self._btn.setCheckable(True)
        self._btn.clicked.connect(self._toggle)
        g.addWidget(self._btn, 2, 0, 1, 3)
        lay.addWidget(gb)

        # Pantalla de espera
        self._espera = QtWidgets.QLabel(
            "⏳  MODO REAL ACTIVO\n\n"
            "Conecta tu Arduino al puerto\nseleccionado y presiona CONECTAR.\n\n"
            "Formato CSV esperado:\n"
            "ALT,VEL,AX,AY,AZ,PITCH,ROLL,YAW,\nLAT,LON,PRES,TEMP,SATS\n\n"
            "Formato JSON también soportado.\n"
            "Ver backend/telemetria.py para detalles."
        )
        self._espera.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._espera.setStyleSheet(
            "color:#00FFCC; font-size:13px; font-family:Consolas;"
            "border:1px solid #2A2A35; border-radius:8px; padding:20px;"
        )
        lay.addWidget(self._espera, 1)
        self._refrescar()

    def _refrescar(self):
        self._puerto.clear()
        if SERIAL_DISPONIBLE:
            import serial.tools.list_ports
            ps = [p.device for p in serial.tools.list_ports.comports()]
            self._puerto.addItems(ps or ["Sin puertos"])
        else:
            self._puerto.addItem("pip install pyserial")

    def _toggle(self):
        if self._btn.isChecked():
            self.sig_conectar.emit(self._puerto.currentText(), int(self._baud.currentText()))
            self._btn.setText("DESCONECTAR")
        else:
            self.sig_desconectar.emit()
            self._btn.setText("CONECTAR")


# ── Ventana principal ────────────────────────────────────────

class HorusGCS(QtWidgets.QMainWindow):

    MAX_HIST    = 250    # puntos en gráficas
    DECIM_GRAF  = 3      # actualizar gráficas cada N datos

    def __init__(self):
        super().__init__()
        self.setWindowTitle("HORUS SPACE LABS — ESTACIÓN DE CONTROL v3.0")
        self.resize(1700, 960)

        self._ultima_etapa  = ""
        self._modo          = "Simulacion"   # "Simulacion" | "Arduino"
        self._hist          = {"alt": [], "vel": [], "acc": []}
        self._decim         = 0
        self._alerta_acc    = False

        self._construir_ui()
        self._construir_backend()

    # ═══════════════════════════════════════════════════════
    # CONSTRUCCIÓN DE UI
    # ═══════════════════════════════════════════════════════

    def _construir_ui(self):
        raiz = QtWidgets.QWidget()
        self.setCentralWidget(raiz)
        lay = QtWidgets.QHBoxLayout(raiz)
        lay.setSpacing(8)
        lay.setContentsMargins(8, 8, 8, 8)

        lay.addLayout(self._col_izquierda(), 2)
        lay.addLayout(self._col_central(),   3)
        lay.addLayout(self._col_graficas(),  2)

    # ── Columna izquierda ─────────────────────────────────

    def _col_izquierda(self):
        col = QtWidgets.QVBoxLayout()
        col.setSpacing(5)

        # Botones de modo
        fila_modo = QtWidgets.QHBoxLayout()
        self._btn_sim  = QtWidgets.QPushButton("● SIMULACIÓN")
        self._btn_real = QtWidgets.QPushButton("○ MODO REAL")
        self._btn_sim.setCheckable(True);  self._btn_sim.setChecked(True)
        self._btn_real.setCheckable(True); self._btn_real.setChecked(False)
        self._btn_sim.clicked.connect(lambda: self._cambiar_modo("Simulacion"))
        self._btn_real.clicked.connect(lambda: self._cambiar_modo("Arduino"))
        for b in (self._btn_sim, self._btn_real):
            b.setFixedHeight(32)
            fila_modo.addWidget(b)
        col.addLayout(fila_modo)

        # Panel de etapa
        self.panel_etapa = PanelEtapa()
        col.addWidget(self.panel_etapa)

        # Métricas
        g = QtWidgets.QGridLayout(); g.setSpacing(4)
        self.m_alt   = MetricaVuelo("ALTITUD",       "m AGL",  "#00FFCC")
        self.m_vel   = MetricaVuelo("VELOCIDAD",     "m/s",    "#00FF88")
        self.m_acc   = MetricaVuelo("ACEL. Y",       "G",      "#FFCC00")
        self.m_pitch = MetricaVuelo("PITCH",         "°",      "#FF8800")
        self.m_roll  = MetricaVuelo("ROLL",          "°",      "#FF8800")
        self.m_yaw   = MetricaVuelo("YAW",           "°",      "#FF8800")
        self.m_temp  = MetricaVuelo("TEMPERATURA",   "°C",     "#FF6666")
        self.m_pres  = MetricaVuelo("PRESIÓN",       "hPa",    "#8888FF")
        pares = [(self.m_alt, self.m_vel), (self.m_acc, self.m_pitch),
                 (self.m_roll, self.m_yaw), (self.m_temp, self.m_pres)]
        for i, (a, b) in enumerate(pares):
            g.addWidget(a, i, 0); g.addWidget(b, i, 1)
        col.addLayout(g)

        self.ind = IndicadorEstado()
        col.addWidget(self.ind)

        self.log = LogMision()
        col.addWidget(self.log, 1)

        return col

    # ── Columna central (tabs) ────────────────────────────

    def _col_central(self):
        col = QtWidgets.QVBoxLayout()

        self._tabs = QtWidgets.QTabWidget()
        self._tabs.setTabPosition(QtWidgets.QTabWidget.TabPosition.North)

        # Visor 3D — SIEMPRE vivo, nunca destruido
        self.visor3d = Visor3D()
        self._tabs.addTab(self.visor3d, "🚀 VISOR 3D")

        # Mapa GPS
        self.mapa = QtWebEngineWidgets.QWebEngineView()
        self._cargar_mapa()
        self._tabs.addTab(self.mapa, "🗺 MAPA GPS")

        # Horizonte artificial
        self.horizonte = HorizonteArtificial()
        self._tabs.addTab(self.horizonte, "✈ HORIZONTE")

        # Arduino
        self.panel_ard = PanelArduino()
        self.panel_ard.sig_conectar.connect(self._conectar_arduino)
        self.panel_ard.sig_desconectar.connect(self._desconectar_arduino)
        self._tabs.addTab(self.panel_ard, "⚡ ARDUINO")

        col.addWidget(self._tabs)
        return col

    # ── Columna derecha (gráficas) ─────────────────────────

    def _col_graficas(self):
        col = QtWidgets.QVBoxLayout()
        col.setSpacing(5)

        def _g(titulo, color, unidad):
            pw = pg.PlotWidget(title=titulo)
            pw.setBackground("#050508")
            pw.getAxis("left").setPen(pg.mkPen("#444"))
            pw.getAxis("bottom").setPen(pg.mkPen("#444"))
            pw.showGrid(x=True, y=True, alpha=0.12)
            pw.setLabel("left", unidad, color=color)
            pw.setMinimumHeight(170)
            c = pw.plot(pen=pg.mkPen(color, width=2))
            col.addWidget(pw)
            return c

        self.c_alt = _g("ALTITUD",       "#00FFCC", "m")
        self.c_vel = _g("VELOCIDAD",     "#00FF88", "m/s")
        self.c_acc = _g("ACELERACIÓN Y", "#FFCC00", "G")

        return col

    # ── Mapa Leaflet ──────────────────────────────────────

    def _cargar_mapa(self):
        lat0, lon0 = 27.9174, -110.8975
        self.mapa.setHtml(f"""<!DOCTYPE html><html><head>
<meta charset='utf-8'>
<link rel='stylesheet' href='https://unpkg.com/leaflet@1.9.4/dist/leaflet.css'/>
<script src='https://unpkg.com/leaflet@1.9.4/dist/leaflet.js'></script>
<style>html,body,#map{{margin:0;padding:0;width:100%;height:100%;background:#0A0A0C;}}</style>
</head><body><div id='map'></div><script>
var map=L.map('map').setView([{lat0},{lon0}],14);
L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png',
  {{maxZoom:18,attribution:'© OSM'}}).addTo(map);
var mk=L.circleMarker([{lat0},{lon0}],
  {{color:'#00FFCC',fillColor:'#00FFCC',fillOpacity:1,radius:6}}).addTo(map);
var tr=L.polyline([],{{color:'#FF4400',weight:2}}).addTo(map);
function upd(lat,lon,alt){{
  mk.setLatLng([lat,lon]);
  mk.bindPopup('Alt: '+alt.toFixed(1)+' m').update();
  tr.addLatLng([lat,lon]);
}}
</script></body></html>""")

    # ═══════════════════════════════════════════════════════
    # BACKEND
    # ═══════════════════════════════════════════════════════

    def _construir_backend(self):
        self.hilo   = QtCore.QThread()
        self.worker = WorkerTelemetria()
        self.worker.moveToThread(self.hilo)
        self.worker.dato_recibido.connect(self._actualizar, QtCore.Qt.ConnectionType.QueuedConnection)
        self.worker.error_serial.connect(lambda m: self.log.agregar(m, "CRITICO"))
        self.hilo.started.connect(self.worker.procesar)
        self.hilo.start()
        self.log.agregar("HORUS GCS v3.0 iniciado", "SISTEMA")
        self.log.agregar("Modo: simulación activa — 20 Hz", "INFO")

    def _cambiar_modo(self, modo: str):
        self._modo = modo
        if modo == "Simulacion":
            self._btn_sim.setChecked(True)
            self._btn_real.setChecked(False)
            self.worker.desconectar_arduino()
            self.worker.modo = "Simulacion"
            self.worker.reiniciar_simulacion()
            self.log.agregar("Modo SIMULACIÓN activado", "SISTEMA")
            # Ir al tab 3D automáticamente
            self._tabs.setCurrentIndex(0)
        else:
            self._btn_sim.setChecked(False)
            self._btn_real.setChecked(True)
            self.worker.modo = "Arduino"
            self.log.agregar("Modo REAL activado — esperando Arduino", "SISTEMA")
            # Ir al tab Arduino
            self._tabs.setCurrentIndex(3)

    def _conectar_arduino(self, puerto: str, baud: int):
        ok = self.worker.conectar_arduino(puerto, baud)
        if ok:
            self.log.agregar(f"Arduino conectado: {puerto} @ {baud}", "ARDUINO")
        else:
            self.panel_ard._btn.setChecked(False)
            self.panel_ard._btn.setText("CONECTAR")

    def _desconectar_arduino(self):
        self.worker.desconectar_arduino()
        self.log.agregar("Arduino desconectado", "SISTEMA")

    # ═══════════════════════════════════════════════════════
    # ACTUALIZACIÓN POR DATO RECIBIDO
    # ═══════════════════════════════════════════════════════

    def _actualizar(self, d: DatosTelemetria):
        # ── Métricas ─────────────────────────────────────
        self.m_alt.actualizar(d.altitud)
        self.m_vel.actualizar(d.velocidad)
        self.m_acc.actualizar(d.aceleracion_y, "{:.3f}")
        self.m_pitch.actualizar(d.pitch)
        self.m_roll.actualizar(d.roll)
        self.m_yaw.actualizar(d.yaw)
        self.m_temp.actualizar(d.temperatura)
        self.m_pres.actualizar(d.presion)
        self.ind.actualizar(d)
        self.panel_etapa.actualizar(d.etapa)

        # ── Horizonte (solo si pestaña visible) ──────────
        if self._tabs.currentIndex() == 2:
            self.horizonte.actualizar(d.pitch, d.roll)

        # ── 3D ───────────────────────────────────────────
        self.visor3d.set_datos(d)

        # ── Mapa (throttle: cada 5 datos) ────────────────
        self._decim += 1
        if self._decim % 5 == 0:
            self.mapa.page().runJavaScript(
                f"upd({d.latitud},{d.longitud},{d.altitud});"
            )

        # ── Gráficas (cada DECIM_GRAF datos) ─────────────
        if self._decim % self.DECIM_GRAF == 0:
            for clave, val in (("alt", d.altitud), ("vel", d.velocidad), ("acc", d.aceleracion_y)):
                h = self._hist[clave]
                h.append(val)
                if len(h) > self.MAX_HIST:
                    del h[0]
            self.c_alt.setData(self._hist["alt"])
            self.c_vel.setData(self._hist["vel"])
            self.c_acc.setData(self._hist["acc"])

        # ── Alertas por cambio de etapa ───────────────────
        if d.etapa != self._ultima_etapa:
            nivel = ("CRITICO" if d.etapa == "FALLA"
                     else "RECUP"   if d.etapa in ("DESCENSO", "ATERRIZAJE")
                     else "ADVERT"  if d.etapa == "APOGEO"
                     else "INFO")
            self.log.agregar(d.mensaje, nivel)
            self._aplicar_borde(d.etapa)
            self._ultima_etapa = d.etapa

        # ── Alertas continuas (sin spam) ─────────────────
        if d.altitud > 50 and abs(d.aceleracion_y) > 6 and not self._alerta_acc:
            self.log.agregar(f"Aceleración alta: {d.aceleracion_y:.2f} G", "ADVERT")
            self._alerta_acc = True
        elif abs(d.aceleracion_y) < 3:
            self._alerta_acc = False

        if d.bateria < 25 and int(d.tiempo) % 30 == 1:
            self.log.agregar(f"Batería baja: {d.bateria:.0f}%", "ADVERT")

        if d.rssi < -95 and int(d.tiempo) % 20 == 1:
            self.log.agregar(f"Señal débil: {d.rssi} dBm", "ADVERT")

    def _aplicar_borde(self, etapa: str):
        extra = {
            "FALLA":    "QMainWindow{border:5px solid #FF0000;}",
            "DESCENSO": "QMainWindow{border:3px solid #00FFFF;}",
        }.get(etapa, "")
        self.setStyleSheet(TEMA_HORUS + extra)

    # ═══════════════════════════════════════════════════════
    # CIERRE LIMPIO
    # ═══════════════════════════════════════════════════════

    def closeEvent(self, event):
        self.visor3d._timer.stop()
        self.worker._corriendo = False
        self.worker.desconectar_arduino()
        self.hilo.quit()
        self.hilo.wait(3000)
        event.accept()
