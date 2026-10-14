"""
Most of this was vibe coded (NOT A COPY AND PASTE JOB). I'm only really concerned with the underlying algorithms for archetype detection.
My understanding of the library is limited, so Generative AI is a necessary evil here.
Maybe one day I will consider caring about this more, but for now, I cannot be assed :)
"""

import sys
import math

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QGraphicsView, QGraphicsScene,
    QGraphicsRectItem, QGraphicsTextItem, QGraphicsPathItem,
    QGraphicsEllipseItem, QDialog, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QCheckBox, QLineEdit, QGraphicsItem,
    QMessageBox, QToolBar, QStatusBar, QWidget
)
from PyQt6.QtGui import (
    QPen, QBrush, QColor, QPainter, QWheelEvent, QPainterPath, QFont,
    QTransform, QCursor, QAction, QKeySequence
)
from PyQt6.QtCore import Qt, QRectF, QPointF, QLineF

CANVAS_BG   = QColor("#f9fafb")
GRID_COLOR  = QColor("#e2e8f0")
GRID_STEP   = 40

class Canvas(QGraphicsView):
    def __init__(self):
        super().__init__()

        self._scene = QGraphicsScene()
        self._scene.setSceneRect(-5000, -5000, 10000, 10000)
        self.setScene(self._scene)

        self.setRenderHints(
            QPainter.RenderHint.Antialiasing |
            QPainter.RenderHint.TextAntialiasing
        )
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._panning = False
        self._pan_start = QPointF()

    # ── background grid ───────────────────────────────────────────────────────

    def drawBackground(self, painter, rect):
        painter.fillRect(rect, CANVAS_BG)

        pen = QPen(GRID_COLOR, 1)
        pen.setCosmetic(True)  # grid lines stay 1 px regardless of zoom
        painter.setPen(pen)

        left = int(rect.left()) - (int(rect.left()) % GRID_STEP)
        top = int(rect.top()) - (int(rect.top()) % GRID_STEP)
        right = int(rect.right()) + GRID_STEP
        bot = int(rect.bottom()) + GRID_STEP

        # logic for the grid lines
        x = left
        while x <= right:
            painter.drawLine(x, int(rect.top()), x, int(rect.bottom()))
            x += GRID_STEP

        y = top
        while y <= bot:
            painter.drawLine(int(rect.left()), y, int(rect.right()), y)
            y += GRID_STEP

    # ── pan ───────────────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = True
            self._pan_start = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._panning:
            delta = event.position() - self._pan_start
            self._pan_start = event.position()
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - int(delta.x()))
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - int(delta.y()))
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
        else:
            super().mouseReleaseEvent(event)

    # ── zoom ──────────────────────────────────────────────────────────────────

    def wheelEvent(self, event: QWheelEvent):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_0 and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.resetTransform()
        else:
            super().keyPressEvent(event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CLD Editor")
        self.resize(1100, 720)
        self.setCentralWidget(Canvas())


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()




