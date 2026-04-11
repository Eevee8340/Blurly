"""Core types for the Blurly framework."""

from enum import IntEnum
from dataclasses import dataclass


class BlurMode(IntEnum):
    """Blur algorithm selection."""
    GAUSSIAN = 0
    FROST = 1


class BlurQuality(IntEnum):
    """Blur quality / performance trade-off.

    PERFORMANCE uses a half-resolution intermediate render target,
    processing 4× fewer texels.  The bilinear sampler handles free
    upscaling in the second pass.  Imperceptible at blur strengths ≥ 3.
    """
    PERFORMANCE = 0
    QUALITY = 1


@dataclass
class BlurlyParams:
    """Parameters controlling the glass effect.

    Attributes:
        refraction:    Distortion intensity from the normal map.  Range: 0.0 – 0.2
        blur_strength: Gaussian blur kernel radius in pixels.     Range: 0.0 – 20.0
        blur_mode:     Algorithm selection (Gaussian or Frost).
        frost_amount:  Frost noise intensity (only used when blur_mode=FROST). Range: 0.0 – 1.0
    """
    refraction: float = 0.04
    blur_strength: float = 5.0
    blur_mode: BlurMode = BlurMode.GAUSSIAN
    frost_amount: float = 0.5
