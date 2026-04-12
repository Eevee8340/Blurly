"""Blurly Framework — Demo Application (Framed)

The control panel is a Qt.Window (owned by the blur window)
that tracks the blur window exactly. D3D11 owns the blur HWND's pixels completely —
child widgets get overwritten on every Present() — so a sibling overlay window
is the correct architecture.

Run from project root:
    python examples/demo_framed.py
"""

import sys
import os

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from PyQt6.QtWidgets import (
        QApplication, QWidget, QFrame, QVBoxLayout, QHBoxLayout,
        QSlider, QLabel, QPushButton, QGridLayout, QButtonGroup, QSizeGrip,
        QLineEdit,
    )
    from PyQt6.QtCore import Qt, QTimer, QPoint, QRect
    from PyQt6.QtGui import QPainter, QColor, QPainterPath, QLinearGradient, QPen, QFont
except ImportError:
    print("\nError: PyQt6 is required to run the demo application.")
    print("To install it, run:  pip install \"blurly[examples]\"\n")
    sys.exit(1)

from blurly import BlurlyEngine, BlurlyParams, BlurMode, PRESETS


# ── Control Panel ─────────────────────────────────────────────────────────────

class ControlPanel(QWidget):
    """Frameless overlay window — stays above the blur window and covers it."""

    PANEL_W = 240

    def __init__(self, owner: "BlurlyWindow", engine: BlurlyEngine):
        super().__init__(
            owner,
            Qt.WindowType.Window |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool  # keeps it off the taskbar
        )
        self.owner = owner
        self.engine = engine
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setMouseTracking(True)

        self._tint_color = (1.0, 1.0, 1.0)

        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet("""
            QLabel {
                color: #e8f4fd;
                background: transparent;
            }
            QPushButton {
                background: rgba(20, 45, 90, 180);
                border: 1px solid rgba(147, 201, 235, 100);
                border-radius: 6px;
                color: #93c9eb;
                font-size: 10px;
                padding: 6px 10px;
            }
            QPushButton:hover  { background: rgba(42, 84, 148, 200); border-color: #93c9eb; }
            QPushButton:checked {
                background: rgba(147, 201, 235, 200);
                color: #0d1e3a;
                font-weight: bold;
            }
            QSlider::groove:horizontal {
                height: 3px; background: rgba(44, 74, 120, 180); border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #93c9eb; border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #93c9eb; border: 2px solid #0d1e3a;
                width: 12px; height: 12px; margin: -5px 0; border-radius: 6px;
            }
            QLineEdit {
                background: rgba(20, 45, 90, 180);
                color: white;
                border: 1px solid rgba(147, 201, 235, 100);
                border-radius: 4px;
                padding: 4px;
            }
        """)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        menu_widget = QWidget()
        menu_widget.setFixedWidth(self.PANEL_W)
        menu_widget.setStyleSheet("background: transparent;")

        root = QVBoxLayout(menu_widget)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Title bar (visual only)
        self._title_bar = QWidget()
        self._title_bar.setFixedHeight(38)
        self._title_bar.setStyleSheet("background: transparent;")
        tb_row = QHBoxLayout(self._title_bar)
        tb_row.setContentsMargins(16, 0, 12, 0)

        title_lbl = QLabel("✦  BLURLY  FRAMED")
        title_font = QFont("Segoe UI", 9, QFont.Weight.Bold)
        title_lbl.setFont(title_font)
        title_lbl.setStyleSheet("letter-spacing: 3px; color: rgba(147,201,235,220); background:transparent;")
        tb_row.addWidget(title_lbl)
        tb_row.addStretch()

        root.addWidget(self._title_bar)

        # ── Control panel inner
        panel = QWidget()
        panel.setStyleSheet("background: transparent;")
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(16, 14, 16, 14)
        pl.setSpacing(7)

        # Presets
        pl.addWidget(self._sec("GLASS PRESETS"))
        self._preset_grp = QButtonGroup(self)
        self._preset_grp.setExclusive(True)
        grid = QGridLayout()
        grid.setSpacing(4)
        for i, (key, preset) in enumerate(PRESETS.items()):
            btn = QPushButton(preset.name)
            btn.setCheckable(True); btn.setChecked(i == 0)
            btn.setProperty("preset_key", key)
            btn.clicked.connect(self._on_preset)
            self._preset_grp.addButton(btn)
            grid.addWidget(btn, i // 2, i % 2)
        pl.addLayout(grid)
        pl.addSpacing(4)

        # Blur slider
        pl.addWidget(self._sec("BLUR DEPTH"))
        self._blur_sl = QSlider(Qt.Orientation.Horizontal)
        self._blur_sl.setRange(0, 200); self._blur_sl.setValue(50)
        self._blur_sl.valueChanged.connect(self._on_params)
        pl.addWidget(self._blur_sl)

        # Refraction slider
        pl.addWidget(self._sec("REFRACTION"))
        self._ref_sl = QSlider(Qt.Orientation.Horizontal)
        self._ref_sl.setRange(0, 100); self._ref_sl.setValue(20)
        self._ref_sl.valueChanged.connect(self._on_params)
        pl.addWidget(self._ref_sl)

        # Transparency slider
        pl.addWidget(self._sec("TRANSPARENCY"))
        self._alpha_sl = QSlider(Qt.Orientation.Horizontal)
        self._alpha_sl.setRange(0, 100); self._alpha_sl.setValue(0)
        self._alpha_sl.valueChanged.connect(self._on_params)
        pl.addWidget(self._alpha_sl)

        # Color
        pl.addWidget(self._sec("COLOR"))
        self._color_input = QLineEdit()
        self._color_input.setPlaceholderText("#FFFFFF or rgb(255,255,255)")
        self._color_input.setText("#FFFFFF")
        self._color_input.textChanged.connect(self._on_color_changed)
        pl.addWidget(self._color_input)

        # Mode buttons
        pl.addSpacing(4)
        pl.addWidget(self._sec("STYLE"))
        mode_row = QHBoxLayout()
        mode_row.setSpacing(4)
        self._mode_grp = QButtonGroup(self)
        self._mode_grp.setExclusive(True)
        for i, name in enumerate(["Gaussian", "Frost"]):
            btn = QPushButton(name)
            btn.setCheckable(True); btn.setChecked(i == 0)
            btn.clicked.connect(self._on_params)
            self._mode_grp.addButton(btn, i)
            mode_row.addWidget(btn)
        pl.addLayout(mode_row)
        pl.addStretch()

        root.addWidget(panel)
        root.addStretch()

        main_layout.addWidget(menu_widget)
        main_layout.addStretch()

    # ── Forward Mouse Events to Owner ─────────────────────────────────────────

    def mousePressEvent(self, e):
        self.owner.mousePressEvent(e)

    def mouseMoveEvent(self, e):
        self.owner.mouseMoveEvent(e)
        self.setCursor(self.owner.cursor())

    def mouseReleaseEvent(self, e):
        self.owner.mouseReleaseEvent(e)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _sec(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "font-size: 8px; color: rgba(74,122,181,200);"
            "letter-spacing:1px; background:transparent;"
        )
        return lbl

    def _on_preset(self):
        key = self.sender().property("preset_key")
        if key:
            self.engine.apply_preset(key)

    def _on_color_changed(self, text):
        text = text.strip().lower()
        try:
            if text.startswith("#") and len(text) in (4, 7):
                if len(text) == 4:
                    r = int(text[1]*2, 16) / 255.0
                    g = int(text[2]*2, 16) / 255.0
                    b = int(text[3]*2, 16) / 255.0
                else:
                    r = int(text[1:3], 16) / 255.0
                    g = int(text[3:5], 16) / 255.0
                    b = int(text[5:7], 16) / 255.0
                self._tint_color = (r, g, b)
                self._on_params()
            elif text.startswith("rgb(") and text.endswith(")"):
                parts = text[4:-1].split(",")
                if len(parts) == 3:
                    r = int(parts[0].strip()) / 255.0
                    g = int(parts[1].strip()) / 255.0
                    b = int(parts[2].strip()) / 255.0
                    self._tint_color = (r, g, b)
                    self._on_params()
        except ValueError:
            pass # Invalid format, ignore

    def _on_params(self):
        mode_id = self._mode_grp.checkedId()
        self.engine.set_params(BlurlyParams(
            refraction=self._ref_sl.value() / 500.0,
            blur_strength=self._blur_sl.value() / 10.0,
            blur_mode=BlurMode(max(mode_id, 0)),
            frost_amount=0.5,
            transparency=self._alpha_sl.value() / 100.0,
            tint_color=self._tint_color,
        ))

    def track(self):
        """Sync size and position exactly with the blur window."""
        global_pos = self.owner.mapToGlobal(QPoint(0, 0))
        self.setGeometry(global_pos.x(), global_pos.y(), self.owner.width(), self.owner.height())

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.PANEL_W
        h = self.height()

        # Title bar gradient
        grad = QLinearGradient(0, 0, 0, 38)
        grad.setColorAt(0, QColor(10, 25, 55, 200))
        grad.setColorAt(1, QColor(10, 25, 55, 160))

        # path = QPainterPath()
        # path.addRect(0, 0, w, h)
        # p.fillPath(path, QColor(8, 20, 48, 140))

        # Subtle top highlight
        p.setPen(QPen(QColor(147, 201, 235, 50), 1))
        p.drawLine(12, 0, w - 1, 0)

        # Title bar fill
        tb_path = QPainterPath()
        tb_path.addRect(0, 0, w, 38)
        p.fillPath(tb_path, grad)

        # Right Border
        p.setPen(QPen(QColor(147, 201, 235, 60), 1))
        p.drawLine(w - 1, 0, w - 1, h)


# ── Blur Window ───────────────────────────────────────────────────────────────

class BlurlyWindow(QWidget):
    """Standard framed window that D3D11 renders into."""

    def __init__(self):
        super().__init__()
        self._interaction_active = False
        self.setWindowTitle("Blurly (Framed)")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.resize(1000, 620)
        self.setMinimumSize(500, 350)

        self.engine = BlurlyEngine(int(self.winId()), preset="ripples")

        # Tool window panel — own HWND, Qt paints it independently of D3D11
        self.panel = ControlPanel(self, self.engine)
        self.panel.show()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

        # Debounce timer to detect when OS drag/resize ends
        self._interaction_end_timer = QTimer(self)
        self._interaction_end_timer.setSingleShot(True)
        self._interaction_end_timer.timeout.connect(self._end_interaction)

    def _end_interaction(self):
        self._interaction_active = False
        self.panel.track()    # Final panel sync
        self._timer.start(16) # Resume timer-driven rendering

    # ── Render ────────────────────────────────────────────────────────────────

    def _tick(self, from_interaction: bool = False):
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

        # Single Python→C crossing per frame
        self.engine.render_at(px, py, pw, ph)

    def paintEvent(self, _):
        # Fill the client area with an almost invisible alpha so it catches mouse events
        # instead of letting clicks pass completely through the window to the desktop.
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(0, 0, 0, 1))

    # ── OS Event Hooks ────────────────────────────────────────────────────────

    def moveEvent(self, e):
        if not hasattr(self, "_timer"):
            super().moveEvent(e)
            return

        if not self._interaction_active:
            self._interaction_active = True
            self._timer.stop()    # Let OS move events drive rendering exclusively
        self._interaction_end_timer.start(100) # Reset debounce
        self._tick(from_interaction=True)
        super().moveEvent(e)

    def resizeEvent(self, e):
        if not hasattr(self, "_timer"):
            super().resizeEvent(e)
            return

        if not self._interaction_active:
            self._interaction_active = True
            self._timer.stop()    # Let OS resize events drive rendering exclusively
        self._interaction_end_timer.start(100) # Reset debounce
        self._tick(from_interaction=True)
        super().resizeEvent(e)

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
