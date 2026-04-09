# ============================================================
# HORUS GCS v3.0 — VISOR 3D
#
# Reglas de estabilidad:
#   · El widget OpenGL vive siempre en memoria (nunca se destruye).
#   · El QStackedWidget lo muestra/oculta; no se re-crea.
#   · Refresco máximo: 20 FPS mediante QTimer (cada 50 ms).
#   · Operaciones OpenGL solo dentro de paintGL / initializeGL.
#   · No importar time/math en el nivel global del módulo — ya
#     está disponible en el scope de los métodos.
# ============================================================

import math, time
from PyQt6 import QtCore, QtWidgets, QtGui
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from OpenGL.GL  import *
from OpenGL.GLU import *


class Visor3D(QOpenGLWidget):
    """
    Widget OpenGL del cohete.
    Se actualiza SOLO a través de set_datos() + el timer interno.
    Nunca llames a update() desde fuera — el timer lo gestiona.
    """

    FPS = 20   # máximo fotogramas por segundo

    def __init__(self, parent=None):
        # Pedir un formato con depth buffer explícito
        fmt = QtGui.QSurfaceFormat()
        fmt.setDepthBufferSize(24)
        fmt.setSwapInterval(0)           # sin vsync — el timer controla el ritmo
        super().__init__(parent)
        self.setFormat(fmt)

        # Estado del cohete
        self.altitud      = 0.0
        self.pitch        = 0.0
        self.roll         = 0.0
        self.yaw          = 0.0
        self.paracaidas   = False
        self.motor_activo = False
        self.en_falla     = False
        self.etapa        = "PREVIA"

        # Timer de refresco
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(1000 // self.FPS)
        self._timer.timeout.connect(self.update)
        self._timer.start()

    def set_datos(self, d):
        """Llamado desde el hilo de UI — solo asigna valores."""
        self.altitud      = d.altitud
        self.pitch        = d.pitch
        self.roll         = d.roll
        self.yaw          = d.yaw
        self.paracaidas   = d.paracaidas
        self.motor_activo = d.motor_activo
        self.en_falla     = d.en_falla
        self.etapa        = d.etapa

    # ── OpenGL ────────────────────────────────────────────────

    def initializeGL(self):
        glEnable(GL_DEPTH_TEST)
        glDepthFunc(GL_LESS)
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        glEnable(GL_LIGHT1)
        glEnable(GL_COLOR_MATERIAL)
        glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
        glShadeModel(GL_SMOOTH)
        glLightfv(GL_LIGHT0, GL_POSITION, [10, 30, 20, 1.0])
        glLightfv(GL_LIGHT0, GL_DIFFUSE,  [1.0, 1.0, 0.95, 1.0])
        glLightfv(GL_LIGHT0, GL_AMBIENT,  [0.25, 0.25, 0.3, 1.0])
        glLightfv(GL_LIGHT1, GL_POSITION, [-15, 5, -10, 1.0])
        glLightfv(GL_LIGHT1, GL_DIFFUSE,  [0.3, 0.3, 0.4, 1.0])
        # Color de cielo según falla
        glClearColor(0.35, 0.55, 0.85, 1.0)

    def resizeGL(self, w, h):
        if h == 0:
            h = 1
        glViewport(0, 0, w, h)

    def paintGL(self):
        # Fondo: rojo en falla
        if self.en_falla:
            t = time.monotonic()
            r = 0.35 + 0.15 * abs(math.sin(t * 4))
            glClearColor(r, 0.1, 0.1, 1.0)
        else:
            glClearColor(0.35, 0.55, 0.85, 1.0)

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        asp = self.width() / max(self.height(), 1)
        gluPerspective(50.0, asp, 0.1, 5000.0)

        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

        y_cam = self.altitud / 14.0
        gluLookAt(22, y_cam + 14, 30,
                  0,  y_cam + 2,  0,
                  0,  1,          0)

        self._dibujar_suelo()
        self._dibujar_cohete(y_cam)

    # ── Suelo ─────────────────────────────────────────────────

    def _dibujar_suelo(self):
        glDisable(GL_LIGHTING)
        glBegin(GL_QUADS)
        for xi in range(-8, 8):
            for zi in range(-8, 8):
                c = 0.15 if (xi + zi) % 2 == 0 else 0.19
                glColor3f(c, c + 0.15, c)
                x0, x1 = xi*120, (xi+1)*120
                z0, z1 = zi*120, (zi+1)*120
                glVertex3f(x0,0,z0); glVertex3f(x1,0,z0)
                glVertex3f(x1,0,z1); glVertex3f(x0,0,z1)
        glEnd()
        glEnable(GL_LIGHTING)

    # ── Cohete completo ───────────────────────────────────────

    def _dibujar_cohete(self, y_cam):
        glPushMatrix()
        glTranslatef(0, y_cam, 0)
        glRotatef(self.yaw,   0, 1, 0)
        glRotatef(self.pitch, 1, 0, 0)
        glRotatef(self.roll,  0, 0, 1)
        glRotatef(-90,        1, 0, 0)   # eje vertical

        q = gluNewQuadric()
        gluQuadricNormals(q, GLU_SMOOTH)

        self._cuerpo(q)
        self._aletas(q)
        self._toberas(q)

        if self.motor_activo:
            self._llamas(q)

        if self.paracaidas:
            self._paracaidas(q)

        glPopMatrix()

    # ── Partes del cohete ─────────────────────────────────────

    def _cuerpo(self, q):
        # Tubo principal
        glColor3f(0.88, 0.88, 0.92)
        gluCylinder(q, 0.35, 0.35, 4.2, 20, 8)

        # Tapa inferior
        glColor3f(0.65, 0.65, 0.70)
        gluDisk(q, 0, 0.35, 20, 1)

        # Banda decorativa roja
        glPushMatrix()
        glTranslatef(0, 0, 1.7)
        glColor3f(0.9, 0.12, 0.12)
        gluCylinder(q, 0.355, 0.355, 0.45, 20, 2)
        glPopMatrix()

        # Segunda banda (negra)
        glPushMatrix()
        glTranslatef(0, 0, 2.5)
        glColor3f(0.1, 0.1, 0.1)
        gluCylinder(q, 0.355, 0.355, 0.15, 20, 1)
        glPopMatrix()

        # Ojiva (cono)
        glPushMatrix()
        glTranslatef(0, 0, 4.2)
        glColor3f(0.08, 0.08, 0.12)
        gluCylinder(q, 0.35, 0.0, 1.3, 20, 10)
        glPopMatrix()

    def _aletas(self, q):
        glColor3f(0.85, 0.10, 0.10)
        for i in range(4):
            glPushMatrix()
            glRotatef(i * 90, 0, 0, 1)
            glBegin(GL_TRIANGLES)
            # cara frontal
            glNormal3f(0, 1, 0)
            glVertex3f(0.35, 0.01,  0.1)
            glVertex3f(1.15, 0.01, -0.6)
            glVertex3f(0.35, 0.01,  1.6)
            # cara trasera
            glNormal3f(0, -1, 0)
            glVertex3f(0.35, -0.01,  0.1)
            glVertex3f(1.15, -0.01, -0.6)
            glVertex3f(0.35, -0.01,  1.6)
            glEnd()
            glPopMatrix()

    def _toberas(self, q):
        """4 toberas pequeñas en la base."""
        glColor3f(0.25, 0.25, 0.30)
        offsets = [(0.15, 0.15), (-0.15, 0.15), (0.15, -0.15), (-0.15, -0.15)]
        for ox, oy in offsets:
            glPushMatrix()
            glTranslatef(ox, oy, 0)
            gluCylinder(q, 0.07, 0.10, 0.25, 12, 3)
            glPopMatrix()

    # ── Llamas animadas ───────────────────────────────────────

    def _llamas(self, q):
        glDisable(GL_LIGHTING)
        t = time.monotonic()
        offsets = [(0.15, 0.15), (-0.15, 0.15), (0.15, -0.15), (-0.15, -0.15)]

        # Intensidad pulsante por tobera con fase distinta
        for idx, (ox, oy) in enumerate(offsets):
            fase   = idx * 0.4
            largo  = 0.8 + 0.35 * abs(math.sin(t * 18 + fase))
            largo2 = largo * 0.55

            glPushMatrix()
            glTranslatef(ox, oy, -0.25)
            glRotatef(180, 1, 0, 0)

            # Núcleo blanco-amarillo
            glColor4f(1.0, 0.95, 0.6, 0.95)
            gluCylinder(q, 0.04, 0.0, largo2, 8, 3)

            # Corona naranja
            glColor4f(1.0, 0.50, 0.05, 0.80)
            gluCylinder(q, 0.07, 0.0, largo,  8, 3)

            # Halo exterior rojo (más largo y difuso)
            glColor4f(0.9, 0.20, 0.02, 0.45)
            gluCylinder(q, 0.10, 0.0, largo * 1.3, 8, 3)

            glPopMatrix()

        glEnable(GL_LIGHTING)

    # ── Paracaídas cúpula ─────────────────────────────────────

    def _paracaidas(self, q):
        """
        Cúpula real: semiesfera achatada + 8 gajos coloreados + cuerdas.
        """
        glPushMatrix()
        glTranslatef(0, 0, 5.8)   # encima de la ojiva

        # ── Cúpula por gajos (alternando colores) ──
        GAJOS   = 8
        ANILLOS = 6
        R_BASE  = 2.0    # radio en la base de la cúpula
        ALTURA  = 1.3    # altura (achatada respecto a semiesfera perfecta)

        for gajo in range(GAJOS):
            # Alternar naranja / blanco
            if gajo % 2 == 0:
                glColor3f(1.0, 0.50, 0.0)
            else:
                glColor3f(0.95, 0.95, 0.95)

            a0 = math.radians(gajo      * 360 / GAJOS)
            a1 = math.radians((gajo + 1) * 360 / GAJOS)

            glBegin(GL_TRIANGLE_STRIP)
            for anillo in range(ANILLOS + 1):
                # phi va de 0 (polo) a pi/2 (ecuador)
                phi = (math.pi / 2) * anillo / ANILLOS
                y   =  ALTURA * math.sin(phi)
                r   =  R_BASE * math.cos(phi)

                # Normal para iluminación
                for a in (a0, a1):
                    nx = math.cos(phi) * math.cos(a)
                    ny = math.sin(phi)
                    nz = math.cos(phi) * math.sin(a)
                    glNormal3f(nx, ny, nz)
                    glVertex3f(r * math.cos(a), y, r * math.sin(a))
            glEnd()

        # ── Aro inferior (borde de la cúpula) ──
        glColor3f(0.2, 0.2, 0.2)
        glDisable(GL_LIGHTING)
        glLineWidth(1.5)
        glBegin(GL_LINE_LOOP)
        for i in range(32):
            a = math.radians(i * 360 / 32)
            glVertex3f(R_BASE * math.cos(a), 0.0, R_BASE * math.sin(a))
        glEnd()

        # ── Cuerdas (8, desde el borde hasta el cohete) ──
        glColor3f(0.85, 0.85, 0.85)
        glLineWidth(1.0)
        for gajo in range(GAJOS):
            a   = math.radians((gajo + 0.5) * 360 / GAJOS)
            bx  = R_BASE * math.cos(a)
            bz  = R_BASE * math.sin(a)
            # Punto de anclaje en la ojiva (~0.2 del centro)
            ax  = 0.15 * math.cos(a)
            az  = 0.15 * math.sin(a)
            glBegin(GL_LINES)
            glVertex3f(bx, 0.0,  bz)        # borde cúpula
            glVertex3f(ax, -5.8, az)         # ojiva del cohete (z relativo)
            glEnd()

        glLineWidth(1.0)
        glEnable(GL_LIGHTING)
        glPopMatrix()
