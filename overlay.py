"""BlurlyOverlay — toolkit-agnostic Z-order and geometry manager for the
two-HWND layered rendering pattern.

Architecture overview
---------------------
Blurly renders a blurred desktop into a "blur host" HWND via a D3D11 swap
chain.  Because ``SwapChain::Present()`` overwrites the entire client area on
every frame, any UI painted *inside* that HWND is erased immediately.

The solution is a second, independent HWND — the *overlay* — that sits *on top*
of the blur host.  The app paints its custom UI there using whatever toolkit it
likes.  DWM composites both HWNDs every VSync; the user sees:

    [blurred desktop background]  ← blur host  (D3D11 / Blurly)
    [custom UI: buttons, text …]  ← overlay    (your toolkit)

This module provides ``BlurlyOverlay``, which wires up the two windows using
**only ctypes and Win32 APIs** — no PyQt, no tkinter, no other dependency.

Z-order strategy — Win32 owner relationship
-------------------------------------------
``SetWindowLongPtr(overlay_hwnd, GWLP_HWNDPARENT, blur_hwnd)`` designates the
blur host as the Win32 *owner* of the overlay.  DWM then keeps the overlay
above its owner automatically — no per-frame polling or ``SetWindowPos`` loop
is needed.

Position sync
-------------
``BlurlyOverlay.sync()`` reads the blur host's current client-area position
with ``GetClientRect`` + ``ClientToScreen`` (pure Win32, no toolkit calls) and
moves the overlay HWND to match via ``SetWindowPos``.  Call it every frame
before ``engine.render_at()``.

Usage (toolkit-agnostic)::

    from blurly import BlurlyEngine
    from blurly.overlay import BlurlyOverlay

    # HWNDs can come from any source — PyQt, tkinter, wx, ctypes …
    blur_hwnd    = int(blur_widget.winId())    # or any HWND int
    overlay_hwnd = int(overlay_widget.winId())

    engine  = BlurlyEngine(blur_hwnd, preset="frost")
    glue    = BlurlyOverlay(engine, blur_hwnd, overlay_hwnd)

    # ── Every frame tick ──
    x, y, w, h = glue.sync()               # reposition overlay, get physical rect
    engine.render_at(x, y, w, h)           # render blurred desktop
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes

from ._native import _lib

# ── Win32 bindings ─────────────────────────────────────────────────────────────

_user32 = ctypes.windll.user32

# BOOL GetClientRect(HWND hWnd, LPRECT lpRect)
_user32.GetClientRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.wintypes.RECT)]
_user32.GetClientRect.restype  = ctypes.wintypes.BOOL

# BOOL ClientToScreen(HWND hWnd, LPPOINT lpPoint)
_user32.ClientToScreen.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.wintypes.POINT)]
_user32.ClientToScreen.restype  = ctypes.wintypes.BOOL

# BOOL SetWindowPos(HWND, HWND insertAfter, int X, int Y, int cx, int cy, UINT flags)
_user32.SetWindowPos.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    ctypes.c_uint,
]
_user32.SetWindowPos.restype = ctypes.wintypes.BOOL

# LONG_PTR SetWindowLongPtrW(HWND, int nIndex, LONG_PTR dwNewLong)
_user32.SetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
_user32.SetWindowLongPtrW.restype  = ctypes.c_void_p

# UINT GetDpiForWindow(HWND hwnd)
if hasattr(_user32, "GetDpiForWindow"):
    _user32.GetDpiForWindow.argtypes = [ctypes.c_void_p]
    _user32.GetDpiForWindow.restype = ctypes.c_uint

# ── Win32 constants ────────────────────────────────────────────────────────────

GWLP_HWNDPARENT = -8

SWP_NOACTIVATE  = 0x0010
SWP_NOZORDER    = 0x0004
SWP_NOMOVE      = 0x0002
SWP_NOSIZE      = 0x0001

HWND_TOP        = ctypes.c_void_p(0)


# ── Helper ─────────────────────────────────────────────────────────────────────

def _client_rect_on_screen(hwnd: int) -> tuple[int, int, int, int]:
    """Return (x, y, w, h) of *hwnd*'s client area in screen coordinates.

    Uses ``GetClientRect`` (client-relative) + ``ClientToScreen`` (origin only)
    so the result is DPI-unscaled physical pixels — exactly what Win32 expects.
    """
    rc = ctypes.wintypes.RECT()
    _user32.GetClientRect(ctypes.c_void_p(hwnd), ctypes.byref(rc))

    pt = ctypes.wintypes.POINT(rc.left, rc.top)
    _user32.ClientToScreen(ctypes.c_void_p(hwnd), ctypes.byref(pt))

    w = rc.right  - rc.left
    h = rc.bottom - rc.top
    return pt.x, pt.y, w, h


# ── Public class ───────────────────────────────────────────────────────────────

class BlurlyOverlay:
    """Manages Z-order and geometry between a Blurly blur host and an overlay HWND.

    Both arguments are plain ``int`` HWNDs — no toolkit objects required.

    Parameters
    ----------
    engine:
        An active ``BlurlyEngine`` instance bound to *blur_hwnd*.
    blur_hwnd:
        The HWND that ``BlurlyEngine`` renders into
        (``int(widget.winId())`` in Qt, ``widget.winfo_id()`` in tkinter, etc.).
    overlay_hwnd:
        The HWND your UI toolkit painted its custom content into.
        Must be a **top-level** window (not a child of *blur_hwnd*).

    Notes
    -----
    * The overlay window should be **translucent / per-pixel alpha** so the
      blurred background shows through — set this in your toolkit before
      constructing ``BlurlyOverlay``.
    * The Win32 owner relationship means Alt-Tab shows one combined entry
      (the blur host).  This is usually the desired UX for overlay windows.
    * ``sync()`` is pure Win32 — safe to call from any thread that owns the
      message queue, or from a ``QTimer`` / ``after()`` callback.
    """

    def __init__(
        self,
        engine: object,  # BlurlyEngine — avoiding circular import
        blur_hwnd: int,
        overlay_hwnd: int,
    ) -> None:
        self._engine      = engine
        self._blur_hwnd   = int(blur_hwnd)
        self._overlay_hwnd = int(overlay_hwnd)

        # Wire up the Win32 owner relationship.
        # DWM now keeps overlay_hwnd above blur_hwnd in Z-order automatically.
        _user32.SetWindowLongPtrW(
            ctypes.c_void_p(self._overlay_hwnd),
            ctypes.c_int(GWLP_HWNDPARENT),
            ctypes.c_void_p(self._blur_hwnd),
        )

    # ── Public API ─────────────────────────────────────────────────────────────

    def sync(self) -> tuple[int, int, int, int]:
        """Reposition the overlay to exactly cover the blur host's client area.

        Uses Win32 ``GetClientRect`` + ``ClientToScreen`` — no toolkit calls.
        Call every frame **before** ``engine.render_at()``.

        Returns:
            (x, y, w, h): The physical (DPI-scaled) coordinates of the client
            area, ready to be passed directly to ``engine.render_at()``.
        """
        x, y, w, h = _client_rect_on_screen(self._blur_hwnd)
        _user32.SetWindowPos(
            ctypes.c_void_p(self._overlay_hwnd),
            HWND_TOP,
            x, y, w, h,
            SWP_NOACTIVATE,
        )

        scale = 1.0
        if hasattr(_user32, "GetDpiForWindow"):
            dpi = _user32.GetDpiForWindow(ctypes.c_void_p(self._blur_hwnd))
            scale = dpi / 96.0

        return int(x * scale), int(y * scale), int(w * scale), int(h * scale)

    def raise_overlay(self) -> None:
        """Explicitly bring the overlay to the top of Z-order.

        Normally not needed when the Win32 owner relationship is set, but
        useful after un-minimizing or when another window has covered the
        overlay unexpectedly.
        """
        _user32.SetWindowPos(
            ctypes.c_void_p(self._overlay_hwnd),
            HWND_TOP,
            0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
        )

    def get_blur_hwnd(self) -> int:
        """Return the blur host HWND."""
        return self._blur_hwnd

    def get_overlay_hwnd(self) -> int:
        """Return the overlay HWND."""
        return self._overlay_hwnd
