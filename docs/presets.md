# Presets Guide

Blurly comes with a built-in preset system. A preset (`BlurlyPreset`) is a named combination of a normal-map texture and specific glass parameters (`BlurlyParams`).

This allows you to quickly switch between completely different aesthetics without manually loading textures or fine-tuning parameters.

## Available Presets

Here are the built-in presets you can use right out of the box:

*   **`ripples`**: A wavy, water-like distortion. Good for subtle, organic effects.
*   **`frost`**: A heavily frosted, icy look. Uses the `FROST` blur mode with added noise.
*   **`rain`**: Simulates water droplets on the glass.
*   **`brushed`**: A directional blur, simulating brushed metal or glass.
*   **`grid`**: A subtle, repeating grid distortion pattern.

## Applying Presets

You can apply a preset when creating the `BlurlyEngine`, or change it at runtime.

### During Initialization

Pass the name of the preset to the constructor:

```python
from blurly import BlurlyEngine

engine = BlurlyEngine(hwnd, preset="rain")
```

### At Runtime

Use the `apply_preset()` method to switch styles instantly:

```python
# Change from rain to frost
engine.apply_preset("frost")
```

## Custom Presets

While Blurly comes with built-in presets, you can easily load custom normal maps for entirely new effects.

1. Ensure your normal map is a 512x512 RGBA `.raw` file (1,048,576 bytes).
2. Load it at runtime:

```python
engine.load_normal_map("path/to/my_custom_map.raw")

# Optionally update parameters to match your new map
from blurly import BlurlyParams
engine.set_params(BlurlyParams(refraction=0.1, blur_strength=8.0))
```
