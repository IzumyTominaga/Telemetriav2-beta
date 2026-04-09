# ============================================================
# HORUS GCS v3.0 — CONFIGURACIÓN VISUAL
# ============================================================

COLORES_ETAPA = {
    "PREVIA":       ("#888888", "#1A1A1A"),
    "IGNICION":     ("#FF8800", "#2A1500"),
    "MOTOR_ACTIVO": ("#FF4400", "#2A0800"),
    "APOGEO":       ("#FFFF00", "#2A2A00"),
    "DESCENSO":     ("#00FFFF", "#002A2A"),
    "ATERRIZAJE":   ("#00FF88", "#002A15"),
    "FALLA":        ("#FF0000", "#2A0000"),
    "OFFLINE":      ("#555555", "#111111"),
}

TEMA_HORUS = """
    QMainWindow { background-color: #0A0A0C; }
    QWidget { color: #E0E0E0; font-family: 'Segoe UI', sans-serif; font-size: 12px; }
    QTabWidget::pane { border: 1px solid #2A2A35; background: #0D0D10; }
    QTabBar::tab {
        background: #12121A; color: #7A7A8A;
        padding: 8px 16px; border: 1px solid #2A2A35;
        margin-right: 2px; border-radius: 4px 4px 0 0;
    }
    QTabBar::tab:selected { background: #1E1E28; color: #FFF; border-bottom: 2px solid #00FFCC; }
    QGroupBox {
        border: 1px solid #2A2A35; border-radius: 6px; margin-top: 14px;
        color: #7A7A8A; font-weight: 800; font-size: 9px; letter-spacing: 1px;
    }
    QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 6px; }
    QPushButton {
        background-color: #1A1A22; border: 1px solid #3A3A50;
        color: #DDD; padding: 8px 14px; font-weight: bold;
        border-radius: 5px; font-size: 11px;
    }
    QPushButton:checked { background-color: #8B0000; border: 1px solid #FF2222; color: #FF8888; }
    QPushButton:hover:!checked { background-color: #282835; }
    QPushButton:disabled { color: #444; border-color: #222; }
    QComboBox {
        background: #12121A; border: 1px solid #3A3A50;
        padding: 5px 10px; border-radius: 4px; color: #CCC;
    }
    QComboBox::drop-down { border: none; }
    QPlainTextEdit {
        background-color: #050508; border: 1px solid #1A1A25;
        font-family: 'Consolas', monospace; font-size: 11px; border-radius: 4px;
    }
    QScrollBar:vertical { background: #0D0D10; width: 6px; }
    QScrollBar::handle:vertical { background: #3A3A50; border-radius: 3px; }
"""
