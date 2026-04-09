"""Blurly — GPU-accelerated glass blur framework for Windows.

Create real-time frosted/refractive glass effects on any HWND using
Direct3D 11 Desktop Duplication.

Quick start:
    from blurly import BlurlyEngine

    hwnd = int(widget.winId())
    with BlurlyEngine(hwnd, preset="frost") as glass:
        # In your render loop (~60 fps):
        glass.update_position(x, y, w, h)
        glass.render()
"""

from .engine import BlurlyEngine
from .structs import BlurlyParams, BlurMode
from .presets import BlurlyPreset, PRESETS, get_preset

__all__ = [
    "BlurlyEngine",
    "BlurlyParams",
    "BlurMode",
    "BlurlyPreset",
    "PRESETS",
    "get_preset",
]
