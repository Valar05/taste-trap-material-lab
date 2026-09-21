#!/usr/bin/env python3
"""Derive a grounded Mars EVA texture witness from the donor's exact UV maps."""

from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"


def smoothstep(edge0, edge1, value):
    value = np.clip((value - edge0) / (edge1 - edge0), 0.0, 1.0)
    return value * value * (3.0 - 2.0 * value)


base_image = Image.open(ASSETS / "fps-arms-basecolor.png").convert("RGB")
base = np.asarray(base_image, dtype=np.float32) / 255.0
r, g, b = base[..., 0], base[..., 1], base[..., 2]
luma = r * 0.2126 + g * 0.7152 + b * 0.0722
saturation = base.max(axis=2) - base.min(axis=2)

# Preserve Meshy's semantic breakup: dark authored regions become rubber/seals,
# pale regions become pressure fabric/composite, and olive panels become safety paint.
rubber = smoothstep(0.46, 0.16, luma)
olive = smoothstep(0.018, 0.105, g - b)
olive *= smoothstep(0.045, 0.22, saturation)
olive *= smoothstep(0.78, 0.86, g / np.maximum(r, 0.001))
olive *= smoothstep(0.18, 0.42, luma) * smoothstep(0.78, 0.48, luma)
olive *= 1.0 - rubber

charcoal = np.array([0.055, 0.064, 0.068], dtype=np.float32)
off_white = np.array([0.72, 0.70, 0.64], dtype=np.float32)
safety_yellow = np.array([0.72, 0.43, 0.075], dtype=np.float32)
mars_dust = np.array([0.34, 0.145, 0.075], dtype=np.float32)

micro = np.clip((luma - 0.5) * 0.55 + 0.5, 0.15, 0.86)[..., None]
surface = off_white * (0.76 + micro * 0.34)
surface = surface * (1.0 - olive[..., None]) + safety_yellow * olive[..., None]
surface = surface * (1.0 - rubber[..., None]) + charcoal * (0.74 + micro * 0.42) * rubber[..., None]

# Reuse existing warm grime as localized Martian dust rather than a uniform orange wash.
dust = np.clip((r - b) * 1.8 + (0.48 - luma) * 0.38, 0.0, 1.0)
dust *= (0.12 + saturation * 0.65) * (1.0 - rubber * 0.62)
surface = surface * (1.0 - dust[..., None] * 0.42) + mars_dust * dust[..., None] * 0.42

# Edge-aware abrasion from high-frequency donor albedo changes. Keep it restrained.
blur = np.asarray(base_image.convert("L").filter(ImageFilter.GaussianBlur(3.0)), dtype=np.float32) / 255.0
edges = np.clip(np.abs(luma - blur) * 4.4 - 0.08, 0.0, 0.34)
wear_tint = np.array([0.76, 0.72, 0.61], dtype=np.float32)
surface = surface * (1.0 - edges[..., None]) + wear_tint * edges[..., None]

mars_base = Image.fromarray(np.uint8(np.clip(surface, 0.0, 1.0) * 255.0), "RGB")
mars_base.save(ASSETS / "mars-eva-basecolor.png", optimize=True)

source_roughness = np.asarray(Image.open(ASSETS / "fps-arms-roughness.png").convert("L"), dtype=np.float32) / 255.0
roughness = 0.78 + (source_roughness - 0.5) * 0.24
roughness = roughness * (1.0 - rubber * 0.12) + 0.74 * rubber * 0.12
roughness = roughness * (1.0 - olive * 0.18) + 0.63 * olive * 0.18
roughness = np.clip(roughness + dust * 0.08 - edges * 0.18, 0.48, 0.96)
Image.fromarray(np.uint8(roughness * 255.0), "L").save(ASSETS / "mars-eva-roughness.png", optimize=True)

print("generated assets/mars-eva-basecolor.png")
print("generated assets/mars-eva-roughness.png")
