"""Generate procedural normal-map presets for the Liquid Glass framework.

Run from the project root:
    python -m liquid_glass.assets.generate

Outputs .raw and .png files into liquid_glass/assets/presets/.
"""

import os
import random

from PIL import Image, ImageFilter, ImageDraw
import numpy as np


def save_normal_map(data: np.ndarray, path: str, intensity: float = 5.0):
    """Convert a grayscale heightmap to a tangent-space normal map."""
    dx, dy = np.gradient(data)
    dx *= intensity
    dy *= intensity
    dz = np.ones_like(dx) * 255.0

    mag = np.sqrt(dx**2 + dy**2 + dz**2)
    dx /= mag
    dy /= mag
    dz /= mag

    r = (dx * 127.5 + 127.5).astype("uint8")
    g = (dy * 127.5 + 127.5).astype("uint8")
    b = (dz * 127.5 + 127.5).astype("uint8")

    normal_map = np.stack([r, g, b], axis=-1)
    Image.fromarray(normal_map).save(path)

    # Raw RGBA for the C++ engine
    alpha = np.ones((data.shape[0], data.shape[1], 1), dtype="uint8") * 255
    rgba = np.concatenate([normal_map, alpha], axis=-1)
    rgba.tofile(path.replace(".png", ".raw"))


# ─── Heightmap generators ───────────────────────────────────────────────────

def gen_ripples(size=(512, 512)):
    data = np.random.rand(*size) * 255
    img = Image.fromarray(data.astype("uint8"), mode="L")
    return np.array(img.filter(ImageFilter.GaussianBlur(radius=8))).astype(float)


def gen_frost(size=(512, 512)):
    data = np.random.rand(*size) * 255
    img = Image.fromarray(data.astype("uint8"), mode="L")
    return np.array(img.filter(ImageFilter.GaussianBlur(radius=1))).astype(float)


def gen_raindrops(size=(512, 512), count=30):
    img = Image.new("L", size, 0)
    draw = ImageDraw.Draw(img)
    for _ in range(count):
        x = random.randint(0, size[0])
        y = random.randint(0, size[1])
        r = random.randint(10, 40)
        for i in range(r, 0, -1):
            val = int((i / r) * 255)
            draw.ellipse([x - i, y - i, x + i, y + i], fill=255 - val)
    return np.array(img.filter(ImageFilter.GaussianBlur(radius=4))).astype(float)


def gen_brushed(size=(512, 512)):
    data = np.random.rand(size[0], 1) * np.ones((1, size[1])) * 255
    img = Image.fromarray(data.astype("uint8"), mode="L")
    return np.array(img.filter(ImageFilter.GaussianBlur(radius=2))).astype(float)


def gen_grid(size=(512, 512)):
    data = np.zeros(size, dtype=float)
    for i in range(0, size[0], 40):
        data[i : i + 2, :] = 255
    for j in range(0, size[1], 40):
        data[:, j : j + 2] = 255
    img = Image.fromarray(data.astype("uint8"), mode="L")
    return np.array(img.filter(ImageFilter.GaussianBlur(radius=3))).astype(float)


# ─── Main ────────────────────────────────────────────────────────────────────

STYLES = {
    "ripples": gen_ripples,
    "frost": gen_frost,
    "rain": gen_raindrops,
    "brushed": gen_brushed,
    "grid": gen_grid,
}

if __name__ == "__main__":
    out_dir = os.path.join(os.path.dirname(__file__), "presets")
    os.makedirs(out_dir, exist_ok=True)

    for name, func in STYLES.items():
        print(f"Generating: {name} ...")
        data = func()
        save_normal_map(data, os.path.join(out_dir, f"{name}.png"))

    print(f"All presets generated in {out_dir}")
