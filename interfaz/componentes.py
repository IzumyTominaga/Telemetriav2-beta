# ============================================================
# HORUS GCS v3.0 — COMPONENTES DE INTERFAZ
# Widgets puros, sin lógica de negocio.
# ============================================================

import time, math
from PyQt6 import QtWidgets, QtCore, QtGui
from Telemetry.configuracion import COLORES_ETAPA
from backend.telemetria import DatosTelemetria


# ── MetricaVuelo ─────────────────────────────────────────────

class MetricaVuelo(QtWidgets.QGroupBox):
    def __init__(self, titulo: str, unidad: str, color: str = "#00FFCC"):
        super().__init__(titulo)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(4, 12, 4, 4)
        self._val = QtWidgets.QLabel("---")
        self._val.setStyleSheet(
            f"font-size:24px; color:{color}; font-weight:bold; font-family:Consolas;"
        )
        self._val.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        uni = QtWidgets.QLabel(unidad)
        uni.setStyleSheet("color:#666; font-size:9px; font-weight:bold; letter-spacing:1px;")
        uni.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._val)
        lay.addWidget(uni)

    def actualizar(self, valor: float, fmt: str = "{:.1f}"):
        self._val.setText(fmt.format(valor))


# ── LogMision ────────────────────────────────────────────────

class LogMision(QtWidgets.QGroupBox):
    _C = {"INFO":"#00FF88","ADVERT":"#FFCC00","CRITICO":"#FF4444",
          "RECUP":"#00FFFF","SISTEMA":"#888","ARDUINO":"#FF88FF"}
    _I = {"INFO":"●","ADVERT":"▲","CRITICO":"✖","RECUP":"◆","SISTEMA":"◌","ARDUINO":"⬡"}

    def __init__(self):
        super().__init__("REGISTRO DE EVENTOS")
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(6, 14, 6, 6)
        self._area = QtWidgets.QPlainTextEdit()
        self._area.setReadOnly(True)
        lay.addWidget(self._area)

    def agregar(self, msg: str, nivel: str = "INFO"):
        color = self._C.get(nivel, "#FFF")
        icono = self._I.get(nivel, "●")
        ts    = time.strftime("%H:%M:%S")
        self._area.appendHtml(f'<span style="color:{color}">[{ts}] {icono} {msg}</span>')
        self._area.verticalScrollBar().setValue(
            self._area.verticalScrollBar().maximum()
        )


# ── PanelEtapa ───────────────────────────────────────────────

class PanelEtapa(QtWidgets.QWidget):
    _ORDEN  = ["PREVIA","IGNICION","MOTOR_ACTIVO","APOGEO","DESCENSO","ATERRIZAJE"]
    _NOMBRE = {"PREVIA":"En Tierra","IGNICION":"Ignición","MOTOR_ACTIVO":"Motor",
               "APOGEO":"Apogeo","DESCENSO":"Descenso","ATERRIZAJE":"Aterrizaje"}

    def __init__(self):
        super().__init__()
        self._ultima = ""
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0,0,0,0); lay.setSpacing(3)
        self._btn: dict[str, QtWidgets.QPushButton] = {}
        for e in self._ORDEN:
            b = QtWidgets.QPushButton(self._NOMBRE[e])
            b.setEnabled(False); b.setFixedHeight(26)
            b.setStyleSheet("font-size:10px;color:#555;border-color:#222;background:#111;")
            lay.addWidget(b); self._btn[e] = b

    def actualizar(self, etapa: str):
        if etapa == self._ultima:
            return
        self._ultima = etapa
        pasada = True
        for e in self._ORDEN:
            b = self._btn[e]
            if e == etapa:
                col, bg = COLORES_ETAPA.get(etapa, ("#FFF","#222"))
                b.setStyleSheet(f"font-size:10px;color:{col};border-color:{col};background:{bg};font-weight:bold;")
                pasada = False
            elif pasada:
                b.setStyleSheet("font-size:10px;color:#444;border-color:#2A2A35;background:#0D0D10;")
            else:
                b.setStyleSheet("font-size:10px;color:#555;border-color:#222;background:#111;")


# ── IndicadorEstado ──────────────────────────────────────────

class IndicadorEstado(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0,0,0,0); lay.setSpacing(14)
        self._rssi  = QtWidgets.QLabel("RSSI: ---")
        self._bat   = QtWidgets.QLabel("BAT: ---")
        self._sats  = QtWidgets.QLabel("GPS: ---")
        self._tiem  = QtWidgets.QLabel("T+00:00")
        self._tiem.setStyleSheet("color:#00FFCC;font-size:13px;font-weight:bold;font-family:Consolas;")
        for w in (self._rssi, self._bat, self._sats):
            w.setStyleSheet("color:#666;font-size:10px;")
            lay.addWidget(w)
        lay.addStretch()
        lay.addWidget(self._tiem)

    def actualizar(self, d: DatosTelemetria):
        def col(v, b, m):
            return "#00FF88" if v > b else "#FFCC00" if v > m else "#FF4444"
        self._rssi.setStyleSheet(f"color:{col(d.rssi,-80,-100)};font-size:10px;")
        self._rssi.setText(f"RSSI: {d.rssi} dBm")
        self._bat.setStyleSheet(f"color:{col(d.bateria,50,20)};font-size:10px;")
        self._bat.setText(f"BAT: {d.bateria:.0f}%")
        sc = "#00FF88" if d.satelites >= 4 else "#FFCC00"
        self._sats.setStyleSheet(f"color:{sc};font-size:10px;")
        self._sats.setText(f"GPS: {d.satelites} sats")
        m, s = int(d.tiempo//60), int(d.tiempo%60)
        self._tiem.setText(f"T+{m:02d}:{s:02d}")


# ── HorizonteArtificial ──────────────────────────────────────

class HorizonteArtificial(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self._pitch = 0.0
        self._roll  = 0.0
        self.setMinimumSize(200, 200)

    def actualizar(self, pitch: float, roll: float):
        self._pitch = max(-90.0, min(90.0, pitch))
        self._roll  = roll
        self.update()

    def paintEvent(self, _event):
        p  = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        w, h   = self.width(), self.height()
        cx, cy = w // 2, h // 2
        r      = min(w, h) // 2 - 8

        p.fillRect(0, 0, w, h, QtGui.QColor("#0A0A0C"))

        clip = QtGui.QPainterPath()
        clip.addEllipse(cx - r, cy - r, 2*r, 2*r)
        p.setClipPath(clip)

        p.save()
        p.translate(cx, cy)
        p.rotate(-self._roll)
        dy = int(self._pitch * r / 90)

        p.fillRect(-r, -r*2, 2*r, 2*r + dy, QtGui.QColor(30, 80, 160))
        p.fillRect(-r, dy,   2*r, 2*r,       QtGui.QColor(90, 55, 20))

        p.setPen(QtGui.QPen(QtGui.QColor(255,255,255), 2))
        p.drawLine(-r, dy, r, dy)

        p.setPen(QtGui.QPen(QtGui.QColor(180,180,180), 1))
        f = p.font(); f.setPointSize(8); p.setFont(f)
        for deg in range(-30, 31, 10):
            if deg == 0: continue
            y    = dy + int(deg * r / 90)
            half = r//4 if abs(deg) % 20 == 0 else r//6
            p.drawLine(-half, y, half, y)
            p.drawText(half+3, y+4, f"{-deg}°")
        p.restore()
        p.setClipping(False)

        # Marco
        p.setPen(QtGui.QPen(QtGui.QColor(60,60,80), 2))
        p.drawEllipse(cx-r, cy-r, 2*r, 2*r)

        # Cruz central fija
        p.setPen(QtGui.QPen(QtGui.QColor(255,220,0), 2))
        p.drawLine(cx - r//3, cy, cx - 12, cy)
        p.drawLine(cx + 12,   cy, cx + r//3, cy)
        p.drawEllipse(cx-4, cy-4, 8, 8)

        # Indicador roll
        p.save()
        p.translate(cx, cy)
        p.rotate(-self._roll)
        p.setPen(QtGui.QPen(QtGui.QColor(255,220,0), 2))
        p.drawLine(0, -r+2, 0, -r+14)
        p.restore()

        tri = QtGui.QPolygon([
            QtCore.QPoint(cx,    cy-r+2),
            QtCore.QPoint(cx-5,  cy-r+13),
            QtCore.QPoint(cx+5,  cy-r+13),
        ])
        p.setBrush(QtGui.QColor(255,220,0))
        p.setPen(QtCore.Qt.PenStyle.NoPen)
        p.drawPolygon(tri)

        # Texto de valores
        p.setPen(QtGui.QPen(QtGui.QColor(200,200,200)))
        f = p.font(); f.setPointSize(9); p.setFont(f)
        p.drawText(4, h-22, f"P: {self._pitch:.1f}°")
        p.drawText(4, h- 8, f"R: {self._roll:.1f}°")
        p.end()
