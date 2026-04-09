"""Built-in Blurly presets with tuned parameters and normal maps."""

import os
from dataclasses import dataclass

from .structs import BlurlyParams, BlurMode
from ._native import ASSETS_DIR


@dataclass
class BlurlyPreset:
    """A named combination of a normal-map texture and glass parameters.

    Attributes:
        name:       Human-readable display name.
        normal_map: Filename of the .raw texture in assets/presets/.
        params:     Default ``BlurlyParams`` for this style.
    """
    name: str
    normal_map: str
    params: BlurlyParams

    @property
    def normal_map_path(self) -> str:
        """Absolute path to the .raw normal-map file."""
        return os.path.join(ASSETS_DIR, self.normal_map)


# ─── Built-in preset registry ───────────────────────────────────────────────

PRESETS: dict[str, BlurlyPreset] = {
    "ripples": BlurlyPreset(
        name="Ripples",
        normal_map="ripples.raw",
        params=BlurlyParams(refraction=0.04, blur_strength=5.0),
    ),
    "frost": BlurlyPreset(
        name="Frost",
        normal_map="frost.raw",
        params=BlurlyParams(
            refraction=0.04,
            blur_strength=5.0,
            blur_mode=BlurMode.FROST,
            frost_amount=0.7,
        ),
    ),
    "rain": BlurlyPreset(
        name="Rain",
        normal_map="rain.raw",
        params=BlurlyParams(refraction=0.06, blur_strength=8.0),
    ),
    "brushed": BlurlyPreset(
        name="Brushed",
        normal_map="brushed.raw",
        params=BlurlyParams(refraction=0.03, blur_strength=6.0),
    ),
    "grid": BlurlyPreset(
        name="Grid",
        normal_map="grid.raw",
        params=BlurlyParams(refraction=0.05, blur_strength=4.0),
    ),
}


def get_preset(name: str) -> BlurlyPreset:
    """Look up a built-in preset by key.

    Raises:
        KeyError: If the preset name is not recognized.
    """
    if name not in PRESETS:
        available = ", ".join(PRESETS.keys())
        raise KeyError(f"Unknown preset '{name}'. Available: {available}")
    return PRESETS[name]
