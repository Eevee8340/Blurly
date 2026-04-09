"""BlurlyEngine — the main public API for the framework."""

from __future__ import annotations

import logging

from ._native import _lib, SHADER_DIR, BlurlyError
from .structs import BlurlyParams, BlurMode
from .presets import BlurlyPreset, get_preset

log = logging.getLogger("blurly")


class BlurlyEngine:
    """GPU-accelerated glass blur effect for any HWND.

    Each instance owns an independent D3D11 device, swap chain, and desktop
    duplication session.  You can create multiple instances for multiple
    windows simultaneously.

    Usage::

        from blurly import BlurlyEngine, BlurlyParams, BlurMode

        engine = BlurlyEngine(hwnd, preset="frost")

        # Render loop (~60 fps):
        engine.update_position(x, y, w, h)
        engine.render()

        # Live parameter tweaking:
        engine.set_params(BlurlyParams(
            refraction=0.08,
            blur_strength=12.0,
            blur_mode=BlurMode.FROST,
            frost_amount=0.6,
        ))

        # Switch texture preset at runtime:
        engine.apply_preset("rain")

        # Cleanup:
        engine.shutdown()

    Also works as a context manager::

        with BlurlyEngine(hwnd) as glass:
            ...
    """

    def __init__(self, hwnd: int, preset: str | BlurlyPreset = "ripples"):
        """Create a new glass instance bound to *hwnd*.

        Args:
            hwnd:   Win32 window handle (``int(widget.winId())``).
            preset: Initial preset — a key from ``PRESETS`` or a ``BlurlyPreset``.
        """
        self._handle = None
        self._hwnd = hwnd
        self._params = BlurlyParams()

        # Resolve preset
        preset_obj = get_preset(preset) if isinstance(preset, str) else preset
        normal_map = preset_obj.normal_map_path

        log.info("Creating Blurly for HWND 0x%X (preset=%s)", hwnd, preset_obj.name)

        handle = _lib.Blurly_Create(
            hwnd,
            SHADER_DIR.encode("utf-8"),
            normal_map.encode("utf-8"),
        )
        if not handle:
            err = _lib.Blurly_GetError()
            msg = err.decode("utf-8") if err else "Unknown error"
            raise BlurlyError(f"Engine init failed: {msg}")

        self._handle = handle
        self.set_params(preset_obj.params)
        log.info("Blurly ready")

    # ── Public API ───────────────────────────────────────────────────────────

    @property
    def alive(self) -> bool:
        """``True`` while the native instance is active."""
        return self._handle is not None

    @property
    def params(self) -> BlurlyParams:
        """Currently active parameters (read-only snapshot)."""
        return self._params

    def update_position(self, x: int, y: int, w: int, h: int) -> None:
        """Update the glass region in **physical (DPI-scaled) pixels**."""
        if self._handle:
            _lib.Blurly_UpdatePosition(self._handle, x, y, w, h)

    def set_params(self, params: BlurlyParams) -> None:
        """Live-update blur parameters without reloading the normal map."""
        if not self._handle:
            return
        self._params = params
        _lib.Blurly_SetParams(
            self._handle,
            params.refraction,
            params.blur_strength,
            int(params.blur_mode),
            params.frost_amount,
        )

    def apply_preset(self, preset: str | BlurlyPreset) -> None:
        """Switch to a named preset or a custom ``BlurlyPreset``.

        Reloads the normal map and updates parameters.
        """
        if not self._handle:
            return
        preset_obj = get_preset(preset) if isinstance(preset, str) else preset

        path = preset_obj.normal_map_path
        if not _lib.Blurly_LoadNormalMap(self._handle, path.encode("utf-8")):
            err = _lib.Blurly_GetError()
            msg = err.decode("utf-8") if err else "Unknown error"
            raise BlurlyError(f"Failed to load normal map: {msg}")

        self.set_params(preset_obj.params)
        log.info("Applied preset: %s", preset_obj.name)

    def load_normal_map(self, path: str) -> None:
        """Load a custom .raw normal map from an arbitrary path.

        The file must be 512×512 RGBA (1 048 576 bytes).
        """
        if not self._handle:
            return
        if not _lib.Blurly_LoadNormalMap(self._handle, path.encode("utf-8")):
            err = _lib.Blurly_GetError()
            msg = err.decode("utf-8") if err else "Unknown error"
            raise BlurlyError(f"Failed to load normal map: {msg}")

    def render(self) -> None:
        """Render one frame.  Call at ~60 fps from a ``QTimer``."""
        if self._handle:
            _lib.Blurly_Render(self._handle)

    def shutdown(self) -> None:
        """Release all GPU resources owned by this instance."""
        if self._handle:
            log.info("Shutting down Blurly 0x%X", self._hwnd)
            _lib.Blurly_Destroy(self._handle)
            self._handle = None

    # ── Context manager & destructor ─────────────────────────────────────────

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.shutdown()

    def __del__(self):
        self.shutdown()
