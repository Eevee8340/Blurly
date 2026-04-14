# API Reference

This section provides detailed documentation for the Python API.

## `BlurlyEngine`

The main class for managing the GPU-accelerated glass blur effect.

### Properties (Read-Only)
- **`alive`**: `bool` - `True` while the native instance is active.
- **`params`**: `BlurlyParams` - Currently active parameters.
- **`vsync`**: `bool` - Whether VSync is enabled.
- **`quality`**: `BlurQuality` - Current quality level.
- **`target_fps`**: `float` - Current FPS cap (0 = unlimited).

### Methods
- **`__init__(hwnd: int, preset: str | BlurlyPreset = 'ripples', *, vsync: bool = True, quality: BlurQuality = BlurQuality.QUALITY, target_fps: float = 0)`**: Creates a new instance.
- **`attach_overlay(overlay_hwnd: int) -> None`**: Register an overlay HWND to sync natively.
- **`update_position(x: int, y: int, w: int, h: int) -> None`**: Update the glass region in physical pixels.
- **`set_params(params: BlurlyParams) -> None`**: Live-update blur parameters.
- **`set_config(*, vsync: bool | None, quality: BlurQuality | None, target_fps: float | None) -> None`**: Update engine configuration.
- **`set_freeze_capture(freeze: bool) -> None`**: Skip desktop capture updates during drag/resize for realtime performance.
- **`apply_preset(preset: str | BlurlyPreset) -> None`**: Switch to a named preset or a custom `BlurlyPreset`.
- **`load_normal_map(path: str) -> None`**: Load a custom `.raw` normal map from an arbitrary path.
- **`render() -> None`**: Render one frame.
- **`render_at(x: int, y: int, w: int, h: int) -> None`**: Combined position update and render.
- **`shutdown() -> None`**: Release all GPU resources.

*Note: `BlurlyEngine` supports the context manager protocol (`with` statement) for automatic shutdown.*

## `BlurlyOverlay`

Helper class to manage transparent UI overlays on top of the blur window.

### Methods
- **`__init__(engine: BlurlyEngine, blur_hwnd: int, overlay_hwnd: int)`**
- **`sync() -> tuple[int, int, int, int]`**: Synchronize overlay position with blur host and return physical rect `(x, y, w, h)`.
- **`raise_overlay() -> None`**: Brings the overlay window to the top.
- **`get_blur_hwnd() -> int`**: Returns the blur window handle.
- **`get_overlay_hwnd() -> int`**: Returns the overlay window handle.

## `blurly` Module

::: blurly
    options:
      show_root_heading: false