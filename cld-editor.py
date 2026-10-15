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

NODE_FILL = QColor("#ffffff")
NODE_BORDER = QColor("#374151")
NODE_BORDER_SELECTED = QColor("#2563eb")
NODE_BORDER_PENDING  = QColor("#f59e0b")   # highlighted while waiting for target
NODE_TEXT = QColor("#111827")

LINK_COLOR           = QColor("#374151")

NODE_W, NODE_H = 130, 44
ARROW_SIZE     = 10   # arrowhead depth in px
LABEL_OFFSET = 16
LABEL_T = 0.9
LABEL_PERP = 15

# ── helpers ───────────────────────────────────────────────────────────────────

def _angle_at_end(path: QPainterPath) -> float:
    """Tangent angle (degrees) at the very end of a path."""
    p1 = path.pointAtPercent(0.97)
    p2 = path.pointAtPercent(1.00)
    return math.degrees(math.atan2(-(p2.y() - p1.y()), p2.x() - p1.x()))


def _border_intersection(node: "Node", path: QPainterPath) -> tuple[QPointF, float]:
    """
    Walk backwards along *path* (which ends at the node centre) until we
    leave the node's bounding box. Return (point on border, t value).
    """
    hw = NODE_W / 2 + 1
    hh = NODE_H / 2 + 1
    cp = node.scenePos()
    for i in range(1, 100):
        t = 1.0 - i * 0.01
        pt = path.pointAtPercent(max(t, 0.0))
        if abs(pt.x() - cp.x()) > hw or abs(pt.y() - cp.y()) > hh:
            return pt, t
    return path.pointAtPercent(0.0), 0.0

def _src_border_intersection(node: "Node", path: QPainterPath) -> tuple[QPointF, float]:
    """Walk forwards from t=0 until we leave the node bbox. Used for source."""
    hw = NODE_W / 2 + 1
    hh = NODE_H / 2 + 1
    cp = node.scenePos()
    for i in range(1, 100):
        t  = i * 0.01
        pt = path.pointAtPercent(min(t, 1.0))
        if abs(pt.x() - cp.x()) > hw or abs(pt.y() - cp.y()) > hh:
            return pt, t
    return path.pointAtPercent(1.0), 1.0


# ── Polarity dialog ───────────────────────────────────────────────────────────

class PolarityDialog(QDialog):
    """Ask the user: S (same) or O (opposite)?"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Link type")
        self.polarity = "S"  # default

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Choose the link polarity:"))

        row = QHBoxLayout()
        self._s_btn = QPushButton("S  —  same polarity")
        self._o_btn = QPushButton("O  —  opposite polarity")
        self._s_btn.setCheckable(True)
        self._o_btn.setCheckable(True)
        self._s_btn.setChecked(True)
        self._s_btn.clicked.connect(lambda: self._select("S"))
        self._o_btn.clicked.connect(lambda: self._select("O"))
        row.addWidget(self._s_btn)
        row.addWidget(self._o_btn)
        layout.addLayout(row)

        ok = QPushButton("Add link")
        ok.clicked.connect(self.accept)
        layout.addWidget(ok)
        self.setFixedWidth(300)

    def _select(self, p: str):
        self.polarity = p
        self._s_btn.setChecked(p == "S")
        self._o_btn.setChecked(p == "O")

# ── Link ──────────────────────────────────────────────────────────────────────

class Link(QGraphicsPathItem):
    """Curved arrow between two Nodes."""

    def __init__(self, src: "Node", dst: "Node", polarity: str = "S"):
        super().__init__()
        self.src = src
        self.dst = dst
        self.polarity = polarity

        self.setPos(0, 0)
        self.setZValue(0)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setAcceptHoverEvents(True)

        src.links.append(self)
        dst.links.append(self)
        self._refresh()

    # ── geometry ──────────────────────────────────────────────────────────────

    def _refresh(self):
        sp = self.src.scenePos()
        dp = self.dst.scenePos()

        dx, dy = dp.x() - sp.x(), dp.y() - sp.y()
        length = math.hypot(dx, dy) or 1
        # perpendicular unit vector for the bezier bend
        nx, ny = -dy / length, dx / length
        bend = min(60, length * 0.35)
        ctrl = QPointF(
            (sp.x() + dp.x()) / 2 + nx * bend,
            (sp.y() + dp.y()) / 2 + ny * bend,
        )

        # full curve from centre to centre
        full = QPainterPath(sp)
        full.quadTo(ctrl, dp)

        # find where the curve exits the destination node border
        border_pt, tip_t = _border_intersection(self.dst, full)
        self._tip = border_pt
        self._angle = _angle_at_end(full)

        # shorten the drawn stroke so it ends at the arrowhead base
        base_t = tip_t
        for i in range(1, 200):
            t = tip_t - i * 0.001
            if t <= 0:
                break
            pt = full.pointAtPercent(t)
            dist = math.hypot(pt.x() - border_pt.x(), pt.y() - border_pt.y())
            if dist >= ARROW_SIZE:
                base_t = t
                break

        # --- source: find where the curve exits the src border ---
        src_border_pt, src_t = _src_border_intersection(self.src, full)

        # build the stroke only between the two borders (src_t → base_t)
        stroke = QPainterPath()
        stroke.moveTo(src_border_pt)
        STEPS = 60
        for i in range(1, STEPS + 1):
            t = src_t + (base_t - src_t) * i / STEPS
            stroke.lineTo(full.pointAtPercent(t))

        # label position: LABEL_OFFSET px past the tip along the arrow direction
        # Label sits at a fixed position along the drawn stroke (0.0 = src, 1.0 = arrowhead base).
        # Sampling from stroke (not full) means the position is always visually accurate.
        # label position: LABEL_OFFSET px past the tip along the arrow direction
        # Sample a point on the stroke and offset it perpendicularly.
        # The perpendicular is the tangent rotated 90 degrees.
        lp = stroke.pointAtPercent(LABEL_T)
        la = stroke.pointAtPercent(max(LABEL_T - 0.01, 0.0))
        lb = stroke.pointAtPercent(min(LABEL_T + 0.01, 1.0))
        tdx = lb.x() - la.x()
        tdy = lb.y() - la.y()
        mag = math.hypot(tdx, tdy) or 1
        # perpendicular: rotate tangent 90 degrees counter-clockwise (-tdy, tdx)
        px = -tdy / mag
        py = tdx / mag
        self._label_pos = QPointF(
            lp.x() + px * LABEL_PERP,
            lp.y() + py * LABEL_PERP,
        )

        self.setPath(stroke)
        self.prepareGeometryChange()

    def boundingRect(self):
        pad = ARROW_SIZE + LABEL_OFFSET + 20  # enough for label text
        return self.path().boundingRect().adjusted(-pad, -pad, pad, pad)

    # ── painting ──────────────────────────────────────────────────────────────

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = LINK_COLOR
        width = 2.0 if self.isSelected() else 1.5

        # stroke the curve
        painter.setPen(QPen(color, width, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(self.path())

        # filled arrowhead triangle
        a = math.radians(self._angle)
        tip = self._tip
        left = QPointF(tip.x() - ARROW_SIZE * math.cos(a - 0.4),
                       tip.y() + ARROW_SIZE * math.sin(a - 0.4))
        right = QPointF(tip.x() - ARROW_SIZE * math.cos(a + 0.4),
                        tip.y() + ARROW_SIZE * math.sin(a + 0.4))
        head = QPainterPath()
        head.moveTo(tip)
        head.lineTo(left)
        head.lineTo(right)
        head.closeSubpath()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(color))
        painter.drawPath(head)

        # polarity label past the tip
        font = QFont("Segoe UI", 9, QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(QPen(color))
        fm = painter.fontMetrics()
        lp = self._label_pos
        tw = fm.horizontalAdvance(self.polarity)
        painter.drawText(
            QPointF(lp.x() - tw / 2, lp.y() + fm.ascent() / 2),
            self.polarity,
        )

    # ── interaction ───────────────────────────────────────────────────────────

    def hoverEnterEvent(self, event):
        self.setSelected(True)

    def hoverLeaveEvent(self, event):
        self.setSelected(False)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            canvas = self.scene().views()[0]
            canvas.remove_link(self)
            event.accept()
            return
        super().mousePressEvent(event)

    def cleanup(self):
        if self in self.src.links:
            self.src.links.remove(self)
        if self in self.dst.links:
            self.dst.links.remove(self)


# ── Node ──────────────────────────────────────────────────────────────────────

class Node(QGraphicsRectItem):
    def __init__(self, label: str):
        super().__init__(-NODE_W / 2, -NODE_H / 2, NODE_W, NODE_H)

        self.links: list[Link] = []
        self._pending = False

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setZValue(1)

        # invisible pen — we draw our own in paint()
        self.setPen(QPen(Qt.PenStyle.NoPen))
        self.setBrush(QBrush(NODE_FILL))

        self._label = QGraphicsTextItem(label, self)
        self._label.setDefaultTextColor(NODE_TEXT)
        self._label.setFont(QFont("Segoe UI", 9))
        self._label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextEditorInteraction)
        self._center_label()

    # ── helpers ───────────────────────────────────────────────────────────────

    def _center_label(self):
        r = self.rect()
        lr = self._label.boundingRect()
        self._label.setPos(
            r.left() + (r.width() - lr.width()) / 2,
            r.top() + (r.height() - lr.height()) / 2,
        )

    def label_text(self) -> str:
        return self._label.toPlainText()

    def set_pending(self, val: bool):
        self._pending = val
        self.update()

    def is_pending(self) -> bool:
        return self._pending

    # ── painting ──────────────────────────────────────────────────────────────

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # border_color = NODE_BORDER_SELECTED if self.isSelected() else NODE_BORDER
        border_color = NODE_BORDER
        if self._pending:
            border_color = NODE_BORDER_PENDING
        elif self.isSelected():
            border_color = NODE_BORDER_SELECTED

        pen = QPen(border_color, 2 if self.isSelected() else 1.5)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(QBrush(NODE_FILL))
        painter.drawRoundedRect(self.rect(), 6, 6)

    # ── interaction ───────────────────────────────────────────────────────────

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            for link in self.links:
                link._refresh()
        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            canvas = self.scene().views()[0]
            canvas.remove_node(self)
            event.accept()
            return
        super().mousePressEvent(event)


    def mouseDoubleClickEvent(self, event):
        self._label.setFocus()

# ── Canvas ────────────────────────────────────────────────────────────────────

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
        self._holding = False
        self._pan_start = QPointF()
        self._link_source: Node | None = None  # node waiting for a target

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

    # ── node / link helpers ───────────────────────────────────────────────────

    def _node_at(self, viewport_pos) -> "Node | None":
        for item in self.items(viewport_pos):
            if isinstance(item, Node):
                return item
            if isinstance(item, QGraphicsTextItem):
                p = item.parentItem()
                if isinstance(p, Node):
                    return p
        return None

    def remove_link(self, link: Link):
        link.cleanup()
        self._scene.removeItem(link)

    def remove_node(self, node: Node):
        for link in list(node.links):
            link.cleanup()
            self._scene.removeItem(link)
        self._scene.removeItem(node)
        if self._link_source is node:
            self._link_source = None

    def _cancel_link(self):
        if self._link_source:
            self._link_source.set_pending(False)
            self._link_source = None

    # ── pan ───────────────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = True
            self._pan_start = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return

        if event.button() == Qt.MouseButton.LeftButton:
            self._holding = True
            node = self._node_at(event.pos())
            if node:
                if self._link_source is None:
                    # first click — mark as source
                    self._link_source = node
                    node.set_pending(True)
                else:
                    # second click — complete the link
                    src = self._link_source
                    self._cancel_link()
                    if node is not src:
                        dlg = PolarityDialog()
                        if dlg.exec() == QDialog.DialogCode.Accepted:
                            link = Link(src, node, dlg.polarity)
                            self._scene.addItem(link)
                            self.update()

                super().mousePressEvent(event)
                return   # don't pass to base (prevents accidental drag-select)

            self._cancel_link()  # clicked on empty space, cancel any pending link

            # unselect all nodes if clicked on empty space
            for item in self._scene.selectedItems():
                if isinstance(item, Node):
                    item.setSelected(False)

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

            node = self._node_at(event.pos())
            if node:
                if node.is_pending() and self._holding:
                    self._cancel_link()
                    node.set_pending(False)

            super().mouseMoveEvent(event)
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
        else:
            self._holding = False
            super().mouseReleaseEvent(event)
            self.update()

    # ── zoom ──────────────────────────────────────────────────────────────────

    def wheelEvent(self, event: QWheelEvent):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_0 and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.resetTransform()
        else:
            super().keyPressEvent(event)

    # ── add node on double-click ───────────────────────────────────────────────

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            item = self.itemAt(event.pos())
            if item is None:
                pos = self.mapToScene(event.pos())
                node = Node("Variable")
                node.setPos(pos)
                self._scene.addItem(node)
                return
        super().mouseDoubleClickEvent(event)


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




