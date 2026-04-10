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
from blurly import BlurlyEngine

class MyGlassApp:
    def __init__(self, hwnd):
        self.hwnd = hwnd
        # Initialize the engine
        self.glass = BlurlyEngine(hwnd, preset="frost")
        
    def on_window_move_or_resize(self, x, y, width, height):
        # Tell Blurly where the window is now
        self.glass.update_position(x, y, width, height)

    def render_loop(self):
        # Call this ~60 times a second
        if self.glass.alive:
            self.glass.render()

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
)
engine.set_params(new_params)
```
