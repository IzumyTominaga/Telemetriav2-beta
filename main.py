# ============================================================
# HORUS GCS v3.0 — PUNTO DE ENTRADA
#
# Requisitos:
#   pip install PyQt6 PyQt6-WebEngine pyqtgraph PyOpenGL pyserial
#
# Ejecutar desde la carpeta Horus/:
#   python main.py
# ============================================================

import sys
from PyQt6 import QtWidgets, QtCore
from Telemetry.configuracion  import TEMA_HORUS
from interfaz.ventana_principal import HorusGCS


def main():
    # Necesario para compartir contexto OpenGL entre widgets
    QtWidgets.QApplication.setAttribute(
        QtCore.Qt.ApplicationAttribute.AA_ShareOpenGLContexts
    )
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("HORUS GCS v3.0")
    app.setStyleSheet(TEMA_HORUS)

    ventana = HorusGCS()
    ventana.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
