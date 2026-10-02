"""Cleaning a page: grey, de-speckled, evenly lit, straight, and thresholded.

All of this works on arrays in memory. A page whose ink cannot be told from its
background is blank, and the caller says so instead of looking for a chart in it.
"""
from dataclasses import dataclass

# A page with less ink than this (as a share of its pixels) is called blank.
BLANK_INK_SHARE = 0.0004
# Pixels this close to the page edge are ignored: scanners leave dark borders there.
EDGE_SHARE = 0.015
# Contrast (background level less ink level) below which there is nothing to read.
MIN_CONTRAST = 40
MAX_SKEW = 5.0


@dataclass
class Prepared:
    gray: object        # float array, 0 (ink) to 255 (paper), flattened and straightened
    mask: object        # bool array, True where there is ink; the edge is cleared
    angle: float        # degrees the page was turned to straighten it
    blank: bool


def flatten(image):
    """The page as a float array with speckle removed and the lighting evened out."""
    import numpy as np
    from PIL import ImageFilter

    grey = image.convert("L").filter(ImageFilter.MedianFilter(3))
    width, height = grey.size
    from PIL import Image
    small = grey.resize((max(1, width // 8), max(1, height // 8)), Image.BILINEAR)
    paper = small.filter(ImageFilter.MaxFilter(7)).resize((width, height), Image.BILINEAR)
    paper = paper.filter(ImageFilter.GaussianBlur(8))
    flat = np.asarray(grey, dtype=np.float32) / np.maximum(np.asarray(paper, np.float32), 1)
    return np.clip(flat * 255, 0, 255)


def otsu(values):
    """The grey level that best separates dark from light (Otsu's method)."""
    import numpy as np
    histogram = np.bincount(values.astype(np.uint8).ravel(), minlength=256).astype(float)
    total = histogram.sum()
    if total == 0:
        return 128
    probability = histogram / total
    weight = np.cumsum(probability)
    mean = np.cumsum(probability * np.arange(256))
    with np.errstate(divide="ignore", invalid="ignore"):
        between = (mean[-1] * weight - mean) ** 2 / (weight * (1 - weight))
    between = np.nan_to_num(between)
    return int(np.argmax(between))


def threshold(gray):
    """(ink mask, blank?) for a flattened page."""
    import numpy as np
    level = otsu(gray)
    mask = gray <= level
    dark = gray[mask]
    light = gray[~mask]
    if dark.size == 0 or light.size == 0 or light.mean() - dark.mean() < MIN_CONTRAST:
        return np.zeros(gray.shape, bool), True
    return mask, False


def find_skew(mask, span=MAX_SKEW, step=0.25):
    """The angle (degrees) that turns the page's lines of text level, found by trying
    small rotations of a reduced copy and keeping the one whose lines are sharpest."""
    import numpy as np
    from PIL import Image

    image = Image.fromarray((mask * 255).astype(np.uint8))
    scale = 1000 / max(image.size)
    if scale < 1:
        image = image.resize((int(image.width * scale), int(image.height * scale)),
                             Image.BILINEAR)

    def sharpness(angle):
        rows = np.asarray(image.rotate(angle, resample=Image.BILINEAR, fillcolor=0),
                          dtype=float).sum(axis=1)
        return float(np.sum(np.diff(rows) ** 2))

    best_angle, best = 0.0, sharpness(0.0)
    for angle in np.arange(-span, span + 1e-9, step * 2):
        score = sharpness(angle)
        if score > best:
            best_angle, best = float(angle), score
    for angle in np.arange(best_angle - step * 2, best_angle + step * 2 + 1e-9, step / 2):
        score = sharpness(angle)
        if score > best:
            best_angle, best = float(angle), score
    return best_angle


def clear_edges(mask):
    """The mask with the page edge cleared of ink."""
    height, width = mask.shape
    cleared = mask.copy()
    border_y, border_x = int(height * EDGE_SHARE), int(width * EDGE_SHARE)
    cleared[:border_y] = False
    cleared[height - border_y:] = False
    cleared[:, :border_x] = False
    cleared[:, width - border_x:] = False
    return cleared


def prepare(image):
    """Clean a page image (PIL) and return a Prepared."""
    import numpy as np
    from PIL import Image

    gray = flatten(image)
    mask, blank = threshold(gray)
    if blank:
        return Prepared(gray, mask, 0.0, True)
    angle = find_skew(clear_edges(mask))
    if abs(angle) > 0.05:
        turned = Image.fromarray(gray.astype(np.uint8)).rotate(
            angle, resample=Image.BICUBIC, fillcolor=255)
        gray = np.asarray(turned, dtype=np.float32)
        mask, blank = threshold(gray)
    mask = clear_edges(mask)
    if mask.mean() < BLANK_INK_SHARE:
        blank = True
    return Prepared(gray, mask, angle, blank)
