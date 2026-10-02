"""Reading marks with Tesseract, run as a subprocess.

Images go to Tesseract over its standard input (`tesseract stdin stdout`), so that no
image of a page ever exists as a file, and the command line names no file and no
host. Each crop is read several times ("renditions": the flattened grey page or the
cleaned black-and-white one, at several sizes). Tesseract's own confidence is not
used to decide anything: the prototype showed it is no error detector. A reading is
usable only if it returns as many characters as there are marks in the crop, and
what the readings are used for is voting (see groups.py), not agreeing.
"""
import io
import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor

from . import find_tesseract, tesseract_version

# (source, text height in pixels): "g" is the flattened grey page, "b" the cleaned
# black-and-white one. Sizes near native read best; much larger invents characters.
ROW_RENDITIONS = (("g", 28), ("g", 36), ("g", 44), ("b", 32), ("b", 40), ("b", 48))
LABEL_RENDITIONS = (("g", 32), ("g", 44), ("b", 40))
DIGITS = "0123456789 "          # the space matters: without it Tesseract merges a row
LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz/ "
ALPHANUMERIC = LETTERS + "0123456789"
PAD = 40                        # white border added around every crop, in pixels
TIMEOUT = 120

CHAR = re.compile(r"<span class='ocrx_cinfo' title='[^']*'>([^<]*)</span>")


def source_arrays(prepared):
    """The two arrays crops are cut from: {"g": flattened grey, "b": cleaned B&W}."""
    import numpy as np
    from PIL import Image, ImageFilter

    black_on_white = np.where(prepared.mask, 0, 255).astype(np.uint8)
    smoothed = Image.fromarray(black_on_white).filter(ImageFilter.GaussianBlur(0.8))
    return {"g": prepared.gray, "b": np.asarray(smoothed, dtype=np.float32)}


def crop_png(array, box, height, scale, blank=()):
    """PNG bytes of the crop `box` = (x0, y0, x1, y1) of `array`, scaled so that text
    `height` pixels tall is `scale` pixels, with the boxes in `blank` painted white
    first and a white border around it."""
    import numpy as np
    from PIL import Image

    x0, y0, x1, y1 = (max(0, v) for v in box)
    piece = np.array(array[y0:y1, x0:x1], dtype=np.float32)
    for bx0, by0, bx1, by1 in blank:
        piece[max(0, by0 - y0):max(0, by1 - y0 + 1), max(0, bx0 - x0 - 1):max(0, bx1 - x0 + 1)] = 255
    image = Image.fromarray(np.clip(piece, 0, 255).astype(np.uint8))
    factor = scale / height
    image = image.resize((max(1, int(image.width * factor)),
                          max(1, int(image.height * factor))), Image.LANCZOS)
    canvas = Image.new("L", (image.width + 2 * PAD, image.height + 2 * PAD), 255)
    canvas.paste(image, (PAD, PAD))
    out = io.BytesIO()
    canvas.save(out, "PNG")
    return out.getvalue()


class Recogniser:
    """Tesseract, found and ready; `jobs` readings run at once."""

    def __init__(self, program=None, jobs=None):
        self.program = find_tesseract(program)
        self.version = tesseract_version(self.program)
        self.jobs = max(1, jobs or os.cpu_count() or 1)
        self.pool = ThreadPoolExecutor(self.jobs)
        # One thread per Tesseract process: parallelism is ours, not OpenMP's.
        self.env = dict(os.environ, OMP_THREAD_LIMIT="1")

    def close(self):
        self.pool.shutdown()

    def _run(self, png, whitelist, characters):
        command = [self.program, "stdin", "stdout", "--psm", "7",
                   "-c", f"tessedit_char_whitelist={whitelist}"]
        if characters:
            command += ["-c", "hocr_char_boxes=1", "hocr"]
        try:
            done = subprocess.run(command, input=png, capture_output=True,
                                  env=self.env, timeout=TIMEOUT)
        except (OSError, subprocess.SubprocessError):
            return None
        if done.returncode != 0:
            return None
        text = done.stdout.decode("utf-8", errors="replace")
        if characters:
            return [c for c in CHAR.findall(text) if c.strip()]
        return " ".join(text.split())

    def read_all(self, requests):
        """Run (png bytes, whitelist, characters?) requests in parallel, keeping order.
        Each result is a list of characters, a string, or None if Tesseract failed."""
        return list(self.pool.map(lambda r: self._run(*r), requests))


def read_marks(recogniser, arrays, box, height, blank=(), renditions=ROW_RENDITIONS,
               whitelist=DIGITS):
    """One reading per rendition of the digits in `box`: a list of characters, or None
    where Tesseract failed. The caller decides which readings are usable by comparing
    their length with the number of marks it knows are in the box."""
    requests = [(crop_png(arrays[source], box, height, scale, blank), whitelist, True)
                for source, scale in renditions]
    return recogniser.read_all(requests)


def read_text(recogniser, arrays, box, height, whitelist=LETTERS, renditions=LABEL_RENDITIONS):
    """The text in `box` as read in each rendition (strings, empty where unread)."""
    requests = [(crop_png(arrays[source], box, height, scale), whitelist, False)
                for source, scale in renditions]
    return [r or "" for r in recogniser.read_all(requests)]


def normalise(text):
    """Text for comparing labels: lower case, one space between words."""
    return " ".join(text.lower().split())


def agreed(readings, minimum=2):
    """The one normalised text that every non-empty reading gives, or None if there are
    fewer than `minimum` non-empty readings or they differ."""
    texts = [normalise(r) for r in readings if r and normalise(r)]
    if len(texts) < minimum or len(set(texts)) != 1:
        return None
    return texts[0]
