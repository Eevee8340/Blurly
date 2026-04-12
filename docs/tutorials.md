# Tutorials & Guides

Blurly provides a clean Pythonic API that makes it easy to add glass effects to your applications.

## How Blurly Works

Blurly works by creating an independent Direct3D 11 device and swap chain for your window. It captures the screen content directly behind your window, applies advanced shaders (like Gaussian blur and frost), and renders the result.

This means you need to:
1. Provide Blurly with your window handle (HWND).
2. Tell Blurly where your window is located on the screen so it captures the correct background.
3. Call `render()` repeatedly in your application's render loop or via a timer.

## Examples

The easiest way to learn how to use Blurly is by looking at the provided examples. Blurly comes with examples showing how to integrate it with **PyQt6**.

You can find the examples in the `examples/` directory of the repository:

*   [`examples/demo_framed.py`](https://github.com/Eevee8340/Blurly/blob/main/examples/demo_framed.py): Demonstrates how to use Blurly on a standard window with a title bar and borders.
*   [`examples/demo_frameless.py`](https://github.com/Eevee8340/Blurly/blob/main/examples/demo_frameless.py): Demonstrates how to use Blurly on a modern, frameless window.

### Basic Integration Structure

Here is a simplified structure of how to integrate Blurly into an application using a generic render loop:

```python
from blurly import BlurlyEngine, BlurQuality

class MyGlassApp:
    def __init__(self, hwnd):
        self.hwnd = hwnd
        # Initialize the engine with performance settings
        self.glass = BlurlyEngine(
            hwnd, 
            preset="frost", 
            vsync=False, 
            quality=BlurQuality.PERFORMANCE, 
            target_fps=60
        )
        
    def on_performance_mode_toggled(self, quality_mode):
        # Dynamically change engine configuration
        self.glass.set_config(quality=quality_mode)

    def render_loop(self, x, y, width, height):
        # Call this in your event loop or a timer
        # render_at combines update_position + render for lower overhead
        if self.glass.alive:
            self.glass.render_at(x, y, width, height)

    def cleanup(self):
        # Clean up GPU resources when done
        self.glass.shutdown()
```

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

`BlurlyOverlay` manages the Z-order automatically (making the blur window the owner) and synchronizes the overlay window's position with the blur host using native Win32 calls for zero overhead.

### Implementing an Overlay

1. Create a **host window** to render the blur.
2. Create a **transparent overlay window** to hold your UI.
3. Pass their HWNDs to `BlurlyEngine` and `BlurlyOverlay`.
4. Call `sync()` in your loop to keep the overlay aligned.

```python
from blurly import BlurlyEngine, BlurlyOverlay

class LayeredGlassApp:
    def __init__(self, blur_hwnd, overlay_hwnd):
        # Initialize the engine
        self.engine = BlurlyEngine(blur_hwnd, preset="frost")
        
        # Link the windows so the overlay stays perfectly on top
        self.glue = BlurlyOverlay(self.engine, blur_hwnd, overlay_hwnd)

    def render_loop(self, x, y, width, height):
        # 1. Sync overlay window position to the blur host
        self.glue.sync()
        
        # 2. Render the background blur
        if self.engine.alive:
            self.engine.render_at(x, y, width, height)
```
