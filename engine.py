"""BlurlyEngine — the main public API for the framework."""

from __future__ import annotations

import logging

from ._native import _lib, SHADER_DIR, BlurlyError
from .structs import BlurlyParams, BlurMode, BlurQuality
from .presets import BlurlyPreset, get_preset

log = logging.getLogger("blurly")


class BlurlyEngine:
    """GPU-accelerated glass blur effect for any HWND.

    Each instance owns an independent D3D11 device, swap chain, and desktop
    duplication session.  You can create multiple instances for multiple
    windows simultaneously.

    Usage::

        from blurly import BlurlyEngine, BlurlyParams, BlurMode, BlurQuality

        engine = BlurlyEngine(hwnd, preset="frost")

        # Render loop (~60 fps):
        engine.update_position(x, y, w, h)
        engine.render()

        # Or combined (one fewer Python→C crossing per frame):
        engine.render_at(x, y, w, h)

        # Live parameter tweaking:
        engine.set_params(BlurlyParams(
            refraction=0.08,
            blur_strength=12.0,
            blur_mode=BlurMode.FROST,
            frost_amount=0.6,
        ))

        # Engine configuration (VSync, quality, FPS cap):
        engine.set_config(vsync=False, quality=BlurQuality.PERFORMANCE, target_fps=60)

        # Switch texture preset at runtime:
        engine.apply_preset("rain")

        # Cleanup:
        engine.shutdown()

    Also works as a context manager::

        with BlurlyEngine(hwnd) as glass:
            ...
    """

    def __init__(
        self,
        hwnd: int,
        preset: str | BlurlyPreset = "ripples",
        *,
        vsync: bool = True,
        quality: BlurQuality = BlurQuality.QUALITY,
        target_fps: float = 0,
    ):
        """Create a new glass instance bound to *hwnd*.

        Args:
            hwnd:       Win32 window handle (``int(widget.winId())``).
            preset:     Initial preset — a key from ``PRESETS`` or a ``BlurlyPreset``.
            vsync:      Enable VSync on Present (default ``True``).
            quality:    ``BlurQuality.QUALITY`` (full-res) or ``BlurQuality.PERFORMANCE``
                        (half-res intermediate — 4× fewer texels, imperceptible at blur ≥ 3).
            target_fps: Maximum frame rate cap.  ``0`` = unlimited (default).
        """
        self._handle = None
        self._hwnd = hwnd
        self._params = BlurlyParams()
        self._vsync = vsync
        self._quality = quality
        self._target_fps = target_fps

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

        # Cache ctypes function references — eliminates __getattr__ lookup on
        # the ctypes DLL object every frame (~2–3µs/call at 60fps adds up).
        self._fn_render     = _lib.Blurly_Render
        self._fn_render_at  = _lib.Blurly_RenderAt
        self._fn_update_pos = _lib.Blurly_UpdatePosition
        self._fn_set_config = _lib.Blurly_SetConfig

        self.set_params(preset_obj.params)
        self.set_config(vsync=vsync, quality=quality, target_fps=target_fps)
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

    @property
    def vsync(self) -> bool:
        """Whether VSync is enabled."""
        return self._vsync

    @property
    def quality(self) -> BlurQuality:
        """Current quality level."""
        return self._quality

    @property
    def target_fps(self) -> float:
        """Current FPS cap (0 = unlimited)."""
        return self._target_fps

    def attach_overlay(self, overlay_hwnd: int) -> None:
        """Register the overlay HWND with the engine so it can sync natively during resizing."""
        if self._handle:
            _lib.Blurly_AttachOverlay(self._handle, overlay_hwnd)

    def update_position(self, x: int, y: int, w: int, h: int) -> None:
        """Update the glass region in **physical (DPI-scaled) pixels**."""
        if self._handle:
            self._fn_update_pos(self._handle, x, y, w, h)

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
            params.tint_color[0],
            params.tint_color[1],
            params.tint_color[2],
            params.transparency,
            params.edge_highlight,
        )

    def set_config(
        self,
        *,
        vsync: bool | None = None,
        quality: BlurQuality | None = None,
        target_fps: float | None = None,
    ) -> None:
        """Update engine configuration (VSync, quality, FPS cap).

        Only the supplied parameters are changed; others retain their
        current values.

        Args:
            vsync:      Enable/disable VSync.
            quality:    ``BlurQuality.QUALITY`` or ``BlurQuality.PERFORMANCE``.
            target_fps: Max frame rate (0 = unlimited).
        """
        if not self._handle:
            return
        if vsync is not None:
            self._vsync = vsync
        if quality is not None:
            self._quality = quality
        if target_fps is not None:
            self._target_fps = target_fps

        self._fn_set_config(
            self._handle,
            int(self._vsync),
            int(self._quality),
            float(self._target_fps),
        )

    def set_freeze_capture(self, freeze: bool) -> None:
        """Skip desktop capture updates during drag/resize for realtime performance."""
        if not self._handle:
            return
        _lib.Blurly_SetFreezeCapture(self._handle, int(freeze))

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
        """Render one frame.  Call at ~60 fps from a ``QTimer``.

        If ``target_fps`` is set, the engine will automatically skip frames
        when called more frequently than the cap allows.
        """
        if self._handle:
            self._fn_render(self._handle)

    def render_at(self, x: int, y: int, w: int, h: int) -> None:
        """Combined position update + render in a single C call.

        Equivalent to calling ``update_position()`` then ``render()``,
        but crosses the Python→C boundary only once per frame.
        """
        if self._handle:
            self._fn_render_at(self._handle, x, y, w, h)

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
