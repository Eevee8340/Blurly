# Blurly ✨

**Blurly** is a high-performance, GPU-accelerated framework for implementing real-time frosted and refractive glass effects in Windows applications. 

By leveraging **Direct3D 11** and the **Desktop Duplication API**, it captures and processes background content with sub-millisecond latency. It combines a high-efficiency C++ core with a clean Python API, enabling developers to integrate sophisticated, modern UI aesthetics into their applications without compromising performance.

## Features

- 🚀 **Hardware Accelerated:** Pure D3D11 implementation for buttery smooth 60+ FPS.
- 🎨 **Fully Customizable:** Live-update refraction, blur depth, and frost intensity.
- 📦 **Preset System:** Comes with built-in styles like *Rain*, *Frost*, and *Ripples*.
- 🛠️ **Easy Integration:** Simple Pythonic API that works with PyQt6, PySide6, or raw Win32.
- 🧵 **Multi-Instance:** Run independent glass effects on multiple windows simultaneously.

## Quick Start

```python
from blurly import BlurlyEngine

# Create the engine for your window (HWND)
with BlurlyEngine(hwnd, preset="frost") as glass:
    # In your render loop:
    glass.update_position(x, y, w, h)
    glass.render()
```

## Installation

### From Source
1. Clone the repository:
   ```bash
   git clone https://github.com/Eevee8340/Blurly.git
   cd Blurly
   ```
2. Build the native engine (requires MSVC):
   ```bash
   ./build_engine.bat
   ```
3. Install in editable mode:
   ```bash
   pip install -e .
   ```

## Documentation

📚 **[View the Official Documentation](https://Eevee8340.github.io/Blurly/)**

## Requirements

- **OS:** Windows 10/11
- **Python:** 3.8+
- **Graphics:** DirectX 11 compatible GPU

## License

MIT
