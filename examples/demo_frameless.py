"""Blurly Framework — Demo Application (Frameless)

The control panel is a Qt.Window (owned by the blur window)
that tracks the blur window exactly. D3D11 owns the blur HWND's pixels completely —
child widgets get overwritten on every Present() — so a sibling overlay window
is the correct architecture.

Run from project root:
    python examples/demo_frameless.py
"""

import sys
import os

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import (
    QApplication, QWidget, QFrame, QVBoxLayout, QHBoxLayout,
    QSlider, QLabel, QPushButton, QGridLayout, QButtonGroup, QSizeGrip,
)
from PyQt6.QtCore import Qt, QTimer, QPoint, QRect
from PyQt6.QtGui import QPainter, QColor, QPainterPath

from blurly import BlurlyEngine, BlurlyParams, BlurMode, PRESETS


# ── Control Panel ─────────────────────────────────────────────────────────────

class ControlPanel(QWidget):
    """Frameless overlay window — stays above the blur window and covers it."""

    PANEL_W = 240

    def __init__(self, owner: "BlurlyWindow", engine: BlurlyEngine):
        super().__init__(
            owner,
            Qt.WindowType.Window |
            Qt.WindowType.FramelessWindowHint
        )
        self.owner = owner
        self.engine = engine
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)

        self.setStyleSheet("""
            QLabel {
                font-weight: bold; font-size: 10px;
                color: #93c9eb; background: transparent;
            }
            QPushButton {
                background-color: #1e3d6e;
                border: 1px solid #4a6fa5;
                border-radius: 4px;
                color: white; font-size: 9px; padding: 5px;
            }
            QPushButton:hover  { background-color: #2a5494; }
            QPushButton:checked {
                background-color: #93c9eb;
                color: #152545; font-weight: bold;
            }
            QPushButton#CloseBtn {
                background-color: #7a1f1f; border: none;
            }
            QPushButton#CloseBtn:hover { background-color: #c0392b; }
            QSlider::groove:horizontal {
                height: 4px; background: #2c4a78; border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #93c9eb; border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #93c9eb; border: 2px solid #152545;
                width: 13px; height: 13px;
                margin: -5px 0; border-radius: 7px;
            }
        """)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        menu_widget = QWidget()
        menu_widget.setFixedWidth(self.PANEL_W)
        menu_widget.setStyleSheet("background: transparent;")

        root = QVBoxLayout(menu_widget)
        root.setContentsMargins(14, 12, 14, 14)
        root.setSpacing(6)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("BLURLY")
        title.setStyleSheet("font-size: 11px; letter-spacing: 2px; color: #93c9eb; background: transparent;")
        hdr.addWidget(title)
        hdr.addStretch()
        x_btn = QPushButton("✕")
        x_btn.setObjectName("CloseBtn")
        x_btn.setFixedSize(20, 20)
        x_btn.clicked.connect(owner.close)
        hdr.addWidget(x_btn)
        root.addLayout(hdr)
        root.addSpacing(4)

        # Presets
        root.addWidget(self._sec("GLASS PRESETS"))
        self._style_grp = QButtonGroup(self)
        self._style_grp.setExclusive(True)
        grid = QGridLayout()
        grid.setSpacing(4)
        for i, (key, preset) in enumerate(PRESETS.items()):
            btn = QPushButton(preset.name)
            btn.setCheckable(True)
            btn.setChecked(i == 0)
            btn.setProperty("preset_key", key)
            btn.clicked.connect(self._on_preset)
            self._style_grp.addButton(btn)
            grid.addWidget(btn, i // 2, i % 2)
        root.addLayout(grid)
        root.addSpacing(4)

        # Refraction slider
        root.addWidget(self._sec("REFRACTION"))
        self._ref = QSlider(Qt.Orientation.Horizontal)
        self._ref.setRange(0, 100); self._ref.setValue(20)
        self._ref.valueChanged.connect(self._on_params)
        root.addWidget(self._ref)

        # Blur depth slider
        root.addWidget(self._sec("BLUR DEPTH"))
        self._blur = QSlider(Qt.Orientation.Horizontal)
        self._blur.setRange(0, 200); self._blur.setValue(50)
        self._blur.valueChanged.connect(self._on_params)
        root.addWidget(self._blur)

        # Blur mode
        root.addSpacing(4)
        root.addWidget(self._sec("STYLE"))
        mode_row = QHBoxLayout(); mode_row.setSpacing(4)
        self._mode_grp = QButtonGroup(self)
        self._mode_grp.setExclusive(True)
        for i, name in enumerate(["Gaussian", "Frost"]):
            btn = QPushButton(name)
            btn.setCheckable(True); btn.setChecked(i == 0)
            btn.clicked.connect(self._on_params)
            self._mode_grp.addButton(btn, i)
            mode_row.addWidget(btn)
        root.addLayout(mode_row)
        root.addStretch()

        main_layout.addWidget(menu_widget)
        main_layout.addStretch()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _sec(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("font-size: 9px; color: #4a7ab5; background: transparent; letter-spacing: 1px;")
        return lbl

    def _on_preset(self):
        key = self.sender().property("preset_key")
        if key:
            self.engine.apply_preset(key)

    def _on_params(self):
        mode_id = self._mode_grp.checkedId()
        self.engine.set_params(BlurlyParams(
            refraction=self._ref.value() / 500.0,
            blur_strength=self._blur.value() / 10.0,
            blur_mode=BlurMode(max(mode_id, 0)),
            frost_amount=0.5,
        ))

    def track(self):
        """Sync size and position exactly with the blur window."""
        global_pos = self.owner.mapToGlobal(QPoint(0, 0))
        self.setGeometry(global_pos.x(), global_pos.y(), self.owner.width(), self.owner.height())


# ── Blur Window ───────────────────────────────────────────────────────────────

class BlurlyWindow(QWidget):
    """Frameless transparent window that D3D11 renders into."""

    TITLE_H = 30

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Blurly (Frameless)")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.resize(1000, 620)
        self.setMinimumSize(500, 350)

        self.engine = BlurlyEngine(int(self.winId()), preset="ripples")

        # Tool window panel — own HWND, Qt paints it independently of D3D11
        self.panel = ControlPanel(self, self.engine)
        self.panel.show()

        self._resizing = False
        self._resize_corner_px = 20   # px from corner that trigger resize

        self._drag_active = False
        self._drag_origin = QPoint()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    # ── Render ────────────────────────────────────────────────────────────────

    def _tick(self):
        if not hasattr(self, "panel"):
            return

        dpr   = self.devicePixelRatio()
        orig  = self.mapToGlobal(QPoint(0, 0))

        # Keep panel anchored to our exact geometry
        self.panel.track()

        px = int(orig.x() * dpr)
        py = int(orig.y() * dpr)
        pw = int(self.width()  * dpr)
        ph = int(self.height() * dpr)

        self.engine.update_position(px, py, pw, ph)
        self.engine.render()

    # ── Drag / resize via mouse ───────────────────────────────────────────────

    def _hit_test(self, pos: QPoint):
        """Return (resize_edges, is_title) where resize_edges is a string like 'left', 'bottom-right', etc."""
        w, h = self.width(), self.height()
        b = 10  # border thickness for resizing

        left = pos.x() < b
        right = pos.x() > w - b
        top = pos.y() < b
        bottom = pos.y() > h - b

        edges = ""
        if top: edges += "top"
        elif bottom: edges += "bottom"
        if left: edges += ("-" if edges else "") + "left"
        elif right: edges += ("-" if edges else "") + "right"

        in_title = (not edges) and (pos.y() < self.TITLE_H)
        return edges, in_title

    def _set_cursor_for_edges(self, edges: str):
        if edges in ("top-left", "bottom-right"):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif edges in ("top-right", "bottom-left"):
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        elif edges in ("left", "right"):
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif edges in ("top", "bottom"):
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def mousePressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        
        pos = e.position().toPoint()
        edges, in_title = self._hit_test(pos)
        
        if edges:
            self._resize_edges = edges
            self._resize_start_geo = self.geometry()
            self._resize_start_global = e.globalPosition().toPoint()
        elif in_title:
            self._drag_active = True
            self._drag_origin = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        pos = e.position().toPoint()
        
        if hasattr(self, "_resize_edges") and self._resize_edges:
            delta = e.globalPosition().toPoint() - self._resize_start_global
            geo = self._resize_start_geo
            
            new_x, new_y = geo.x(), geo.y()
            new_w, new_h = geo.width(), geo.height()
            min_w, min_h = self.minimumWidth(), self.minimumHeight()

            if "left" in self._resize_edges:
                max_dx = geo.width() - min_w
                dx = min(delta.x(), max_dx)
                new_x += dx
                new_w -= dx
            elif "right" in self._resize_edges:
                new_w = max(min_w, geo.width() + delta.x())

            if "top" in self._resize_edges:
                max_dy = geo.height() - min_h
                dy = min(delta.y(), max_dy)
                new_y += dy
                new_h -= dy
            elif "bottom" in self._resize_edges:
                new_h = max(min_h, geo.height() + delta.y())

            self.setGeometry(new_x, new_y, new_w, new_h)
            self._tick()  # Immediate render tick for smooth resizing
            
        elif getattr(self, "_drag_active", False):
            self.move(e.globalPosition().toPoint() - self._drag_origin)
            self._tick()  # Immediate render tick for smooth dragging
        else:
            # Update cursor hint for hovering
            edges, in_title = self._hit_test(pos)
            if edges:
                self._set_cursor_for_edges(edges)
            elif in_title:
                self.setCursor(Qt.CursorShape.SizeAllCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, e):
        self._drag_active = False
        self._resize_edges = ""
        self.setCursor(Qt.CursorShape.ArrowCursor)

    # ── Paint a thin title bar hint (D3D11 will draw the blurred bg) ──────────

    def paintEvent(self, _):
        # We only draw a slim title strip; the rest is pure D3D11 blur
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # FIX: Fill the entire window with an almost invisible alpha so it catches mouse events!
        p.fillRect(self.rect(), QColor(0, 0, 0, 1))

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(10, 20, 45, 180))
        p.drawRoundedRect(0, 0, self.width(), self.TITLE_H + 6, 8, 8)
        p.fillRect(0, self.TITLE_H, self.width(), 6, QColor(10, 20, 45, 180))

        # Resize corner hint
        r = self._resize_corner_px
        pts_color = QColor("#2e5c9e")
        p.setPen(pts_color)
        for i in range(3):
            o = i * 5 + 4
            p.drawLine(self.width() - r + o, self.height() - 4,
                       self.width() - 4, self.height() - r + o)

        # Title text
        p.setPen(QColor("#93c9eb"))
        p.drawText(14, 0, self.width() - 14, self.TITLE_H,
                   Qt.AlignmentFlag.AlignVCenter, "BLURLY")

    def closeEvent(self, e):
        self.panel.close()
        self.engine.shutdown()
        super().closeEvent(e)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = BlurlyWindow()
    win.show()
    win.raise_()
    sys.exit(app.exec())
