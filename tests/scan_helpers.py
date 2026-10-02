"""Fake charts, rendered to images at test time, for the scanning tests.

Charts are computed from random fake bittings by the pinner; images are drawn into
memory (or a temporary directory) and never committed (the guard refuses them, D32).
Everything here is invented data.
"""
import random
import shutil
from pathlib import Path

import pytest

from sfic_solver import pinning

FONT_CANDIDATES = {
    "liberation": ["/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
                   "/usr/share/fonts/liberation-mono/LiberationMono-Regular.ttf",
                   "/usr/share/fonts/liberation/LiberationMono-Regular.ttf",
                   "/Library/Fonts/Courier New.ttf", "/System/Library/Fonts/Courier.ttc"],
    "dejavu": ["/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
               "/usr/share/fonts/dejavu/DejaVuSansMono.ttf",
               "/System/Library/Fonts/Menlo.ttc"],
    "freemono": ["/usr/share/fonts/truetype/freefont/FreeMono.ttf"],
}


def font_path(name="liberation"):
    for candidate in FONT_CANDIDATES[name]:
        if Path(candidate).exists():
            return candidate
    return None


def have_tesseract():
    return shutil.which("tesseract") is not None


def need_fonts(*names):
    return pytest.mark.skipif(any(font_path(n) is None for n in names or ("liberation",)),
                              reason="no monospaced font found for the test pages")


def random_chart(rng, chambers=7):
    """A random fake core: (lines of text in the legacy layout, what is on it).

    The truth is {"system", "control", "master", "change": [...], "rows": [(label,
    [cell as text])]}, cells being digits or "--".
    """
    system = pinning.A2
    while True:
        count = rng.randint(2, 4)
        keys = [[rng.randrange(10) for _ in range(chambers)] for _ in range(count)]
        control = [rng.randrange(10) for _ in range(chambers)]
        try:
            core = pinning.pin_core(system, keys, control)
            break
        except pinning.PinningError:
            continue
    layers = max(len(c.masters) for c in core)
    rows = [("T/D", [c.driver for c in core]), ("Control", [c.control for c in core])]
    for layer in range(layers - 1, -1, -1):
        rows.append(("Master", [c.masters[layer] if layer < len(c.masters) else None
                                for c in core]))
    rows.append(("Bottom", [c.bottom for c in core]))
    bitting = lambda cuts: "".join(map(str, cuts))
    truth = {"system": "A2", "control": bitting(control), "master": bitting(keys[0]),
             "change": [bitting(k) for k in keys[1:]],
             "rows": [(label, ["--" if c is None else str(c) for c in cells])
                      for label, cells in rows]}
    lines = ["System = A2", f"Control Key = {truth['control']}",
             f"Master Key = {truth['master']}",
             "Change Keys = " + ", ".join(truth["change"]), ""]
    for label, cells in truth["rows"]:
        lines.append(f"{label:<8}" + "".join(f"{c:>3}" for c in cells))
    return lines, truth


def row_line(label, cells):
    """One row of a chart as text, in the layout the keying software prints."""
    return f"{label:<8}" + "".join(f"{c:>3}" for c in cells)


def random_charts(count, seed=1, chambers=7):
    rng = random.Random(seed)
    return [random_chart(rng, chambers) for _ in range(count)]


def render(lines, font="liberation", pt=11, dpi=300, skew=0.0, blur=0.0, noise=0.0,
           speckle=0.0, shade=0.0, contrast=1.0, seed=0, page=(8.5, 11), margin=0.9,
           top=0.9):
    """The lines of text as a page image (PIL, mode "L") with controllable damage."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter, ImageFont

    width, height = int(page[0] * dpi), int(page[1] * dpi)
    image = Image.new("L", (width, height), 255)
    draw = ImageDraw.Draw(image)
    face = ImageFont.truetype(font_path(font), int(round(pt * dpi / 72)))
    x, y, step = int(margin * dpi), int(top * dpi), int(face.size * 1.35)
    for line in lines:
        draw.text((x, y), line, font=face, fill=0)
        y += step
    if skew:
        image = image.rotate(skew, resample=Image.BICUBIC, fillcolor=255)
    if blur:
        image = image.filter(ImageFilter.GaussianBlur(blur))
    pixels = np.asarray(image, dtype=float)
    rng = np.random.default_rng(seed)
    if contrast != 1.0:
        pixels = 255 - (255 - pixels) * contrast
    if shade:
        pixels = pixels * np.linspace(1 - shade, 1, width)[None, :] \
            * np.linspace(1 - shade / 2, 1, height)[:, None]
    if noise:
        pixels = pixels + rng.normal(0, noise, pixels.shape)
    if speckle:
        dots = rng.random(pixels.shape)
        pixels[dots < speckle / 2] = 0
        pixels[dots > 1 - speckle / 2] = 255
    return Image.fromarray(np.clip(pixels, 0, 255).astype(np.uint8))


def add_strokes(image, boxes, seed=0, count=6):
    """Draw invented handwriting-like strokes (random polylines, not text) in boxes of
    (x0, y0, x1, y1) pixels. A stand-in for notes written in a margin."""
    from PIL import ImageDraw

    rng = random.Random(seed)
    draw = ImageDraw.Draw(image)
    for x0, y0, x1, y1 in boxes:
        for _ in range(count):
            points = [(rng.randint(x0, x1), rng.randint(y0, y1)) for _ in range(4)]
            draw.line(points, fill=0, width=3)
    return image
