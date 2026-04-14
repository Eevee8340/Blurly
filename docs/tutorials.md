# Tutorials & Guides

Blurly provides a clean Pythonic API that makes it easy to add glass effects to your applications.

## How Blurly Works

Blurly works by creating an independent Direct3D 11 device and swap chain for your window. It captures the screen content directly behind your window, applies advanced shaders (like Gaussian blur and frost), and renders the result.

This means you need to:
1. Provide Blurly with your window handle (HWND).
2. Tell Blurly where your window is located on the screen so it captures the correct background.
3. Call `render()` or `render_at()` repeatedly in your application's render loop or via a timer.

## Examples

The easiest way to learn how to use Blurly is by looking at the provided examples. Blurly comes with examples showing how to integrate it with **PyQt6**.

You can find the examples in the `examples/` directory of the repository:

*   [`examples/demo_framed.py`](https://github.com/Eevee8340/Blurly/blob/main/examples/demo_framed.py): Demonstrates how to use Blurly on a standard window with a title bar and borders.
*   [`examples/demo_frameless.py`](https://github.com/Eevee8340/Blurly/blob/main/examples/demo_frameless.py): Demonstrates how to use Blurly on a modern, frameless window.

### Basic Integration Structure

Here is a simplified structure of how to integrate Blurly into an application using a standard render loop and the context manager (`with` statement) to automatically manage GPU resources:

```python
from blurly import BlurlyEngine, BlurQuality
import time

def run_glass_app(hwnd):
    # Initialize the engine with performance settings
    # The 'with' statement ensures shutdown() is called automatically
    with BlurlyEngine(
        hwnd, 
        preset="frost", 
        vsync=False, 
        quality=BlurQuality.PERFORMANCE, 
        target_fps=60
    ) as glass:
        
        while True:
            # Emulate an event loop updating x, y, width, height
            x, y, width, height = get_window_rect(hwnd)
            
            # render_at combines update_position + render for lower overhead
            if glass.alive:
                glass.render_at(x, y, width, height)
                
            time.sleep(1/60)
```

## Window Integration

When working with Windows applications, dragging and resizing windows requires synchronizing the blur effect and updating positions. 

To provide a smooth experience, you should hook into standard OS events (like `WM_MOVE` and `WM_SIZE` or framework equivalents like PyQt's `moveEvent` and `resizeEvent`) and call `render_at()` or `update_position()` to keep the blur aligned with the screen. 

Additionally, you can use `set_freeze_capture(True)` during drag/resize events to skip desktop capture updates temporarily, which improves performance and reduces stuttering while the user is actively interacting with the window.

## Live Tweaking

Blurly parameters can be updated in real-time. This is perfect for creating animations or allowing users to customize the UI.

```python
from blurly import BlurlyParams, BlurMode

# Update parameters live
new_params = BlurlyParams(
    refraction=0.08,
    blur_strength=12.0,
    blur_mode=BlurMode.FROST,
    frost_amount=0.6,
    transparency=0.3,
    tint_color=(0.2, 0.4, 0.8),
    edge_highlight=0.4,
)
engine.set_params(new_params)
```

## Layered Rendering (UI Overlays)

By default, Direct3D's `SwapChain::Present()` will overwrite any standard UI elements painted on the same window. To solve this, Blurly provides a toolkit-agnostic **layered rendering architecture**. This allows you to paint your custom UI on a separate overlay window while maintaining the blurred background in a host window.

`BlurlyOverlay` helps manage this relationship. It provides a `sync()` method to align the overlay with the host window.

### Implementing an Overlay

1. Create a **host window** to render the blur.
2. Create a **transparent overlay window** to hold your UI.
3. Pass their HWNDs to `BlurlyEngine` and `BlurlyOverlay`.
4. Hook into window move/resize events and call `sync()` to keep the overlay aligned.

```python
from blurly import BlurlyEngine, BlurlyOverlay

def run_layered_app(blur_hwnd, overlay_hwnd):
    # Initialize the engine
    with BlurlyEngine(blur_hwnd, preset="frost") as engine:
        glue = BlurlyOverlay(engine, blur_hwnd, overlay_hwnd)

        while True:
            # 1. Sync overlay window position, get physical rect
            x, y, width, height = glue.sync()
            
            # 2. Render the background blur
            if engine.alive:
                engine.render_at(x, y, width, height)
```