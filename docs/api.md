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

*Note: `BlurlyEngine` supports the context manager protocol (`with` statement) and implements the `__del__` destructor for automatic shutdown.*

## `BlurlyOverlay`

Helper class to manage transparent UI overlays on top of the blur window.

### Methods
- **`__init__(engine: BlurlyEngine, blur_hwnd: int, overlay_hwnd: int)`**: Initialize the overlay manager.
  - `engine`: An active `BlurlyEngine` instance bound to `blur_hwnd`.
  - `blur_hwnd`: The HWND that `BlurlyEngine` renders into.
  - `overlay_hwnd`: The top-level HWND your UI toolkit painted its custom content into.
- **`sync() -> tuple[int, int, int, int]`**: Synchronize overlay position with blur host and return physical rect `(x, y, w, h)`.
- **`raise_overlay() -> None`**: Brings the overlay window to the top. Useful after un-minimizing or when another window has covered the overlay unexpectedly.
- **`get_blur_hwnd() -> int`**: Returns the blur window handle.
- **`get_overlay_hwnd() -> int`**: Returns the overlay window handle.

## `BlurlyParams`

Data class containing parameters controlling the glass effect.

### Fields
- **`refraction`**: `float` - Distortion intensity from the normal map. Range: `0.0` – `0.2`. Default: `0.04`.
- **`blur_strength`**: `float` - Gaussian blur kernel radius in pixels. Range: `0.0` – `20.0`. Default: `5.0`.
- **`blur_mode`**: `BlurMode` - Algorithm selection (`GAUSSIAN` or `FROST`). Default: `BlurMode.GAUSSIAN`.
- **`frost_amount`**: `float` - Frost noise intensity (only used when `blur_mode=FROST`). Range: `0.0` – `1.0`. Default: `0.5`.
- **`transparency`**: `float` - Strength of the tint color blending over the blur. Range: `0.0` – `1.0`. Default: `0.0`.
- **`tint_color`**: `tuple[float, float, float]` - RGB tuple for coloring the glass. Default: `(1.0, 1.0, 1.0)`.
- **`edge_highlight`**: `float` - Intensity of the bright edge overlay. Range: `0.0` – `1.0`. Default: `0.0`.

## `BlurMode`

`IntEnum` for blur algorithm selection.

- **`GAUSSIAN`** (`0`)
- **`FROST`** (`1`)

## `BlurQuality`

`IntEnum` for blur quality / performance trade-off.

- **`PERFORMANCE`** (`0`): Uses a half-resolution intermediate render target, processing 4× fewer texels.
- **`QUALITY`** (`1`): Full resolution.

## `BlurlyPreset`

A named combination of a normal-map texture and glass parameters.

### Attributes
- **`name`**: `str` - Human-readable display name.
- **`normal_map`**: `str` - Filename of the `.raw` texture in `assets/presets/`.
- **`params`**: `BlurlyParams` - Default `BlurlyParams` for this style.

### Properties
- **`normal_map_path`**: `str` - Absolute path to the `.raw` normal-map file.

## `PRESETS`

A dictionary mapping preset names (e.g., `'ripples'`, `'frost'`, `'rain'`, `'brushed'`, `'grid'`) to their corresponding `BlurlyPreset` objects.

## `get_preset(name: str) -> BlurlyPreset`

Look up a built-in preset by key. Raises a `KeyError` if the preset name is not recognized.

## `blurly` Module

::: blurly
    options:
      show_root_heading: false