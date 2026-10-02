"""Turning inputs (PDFs and image files) into pages, in memory.

Inputs are numbered in the order given, with directories expanded to the files in
them, sorted. A page is a grey image; nothing is written to disk. Errors name the
input by number, never by file name, because file names can identify a building.
"""
from dataclasses import dataclass
from pathlib import Path

from . import InputError, MissingDependency, missing_packages

RENDER_DPI = 300
PDF_SUFFIX = ".pdf"
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp")


@dataclass(frozen=True)
class Source:
    number: int          # position among all inputs, 1-based
    path: Path
    kind: str            # "pdf" or "image"


@dataclass(frozen=True)
class Page:
    source: int          # Source.number
    number: int          # page within the source, 1-based
    image: object        # a PIL image in mode "L"


def kind_of(path):
    suffix = path.suffix.lower()
    if suffix == PDF_SUFFIX:
        return "pdf"
    if suffix in IMAGE_SUFFIXES:
        return "image"
    return None


def collect_sources(paths):
    """Expand the paths given into numbered sources: files as they come, directories
    as the sorted files in them that are PDFs or images. Raises InputError (naming the
    path's position among the arguments) for a path that is neither a file nor a
    directory, or a file that is not a PDF or an image."""
    sources = []
    for position, raw in enumerate(paths, 1):
        path = Path(raw)
        if path.is_dir():
            found = sorted(p for p in path.rglob("*") if p.is_file() and kind_of(p))
            if not found:
                raise InputError(position, "the directory holds no PDFs or images")
            for file in found:
                sources.append(Source(len(sources) + 1, file, kind_of(file)))
        elif path.is_file():
            kind = kind_of(path)
            if kind is None:
                raise InputError(position, "not a PDF or a supported image "
                                           f"({', '.join(IMAGE_SUFFIXES)})")
            sources.append(Source(len(sources) + 1, path, kind))
        else:
            raise InputError(position, "not a file or a directory")
    return sources


def _grey(image):
    """A PIL image as mode "L", with any transparency flattened onto white."""
    from PIL import Image
    if image.mode in ("RGBA", "LA") or "transparency" in image.info:
        rgba = image.convert("RGBA")
        flat = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        flat.alpha_composite(rgba)
        return flat.convert("L")
    return image.convert("L")


def _pdf_pages(source):
    import pypdfium2
    try:
        document = pypdfium2.PdfDocument(str(source.path))
    except Exception:
        raise InputError(source.number, "cannot be read as a PDF") from None
    try:
        for index in range(len(document)):
            page = document[index]
            try:
                image = page.render(scale=RENDER_DPI / 72).to_pil()
            except Exception:
                raise InputError(source.number,
                                 f"page {index + 1} cannot be rendered") from None
            finally:
                page.close()
            yield Page(source.number, index + 1, _grey(image))
    finally:
        document.close()


def _image_pages(source):
    from PIL import Image, ImageSequence
    try:
        with Image.open(source.path) as opened:
            number = 0
            for frame in ImageSequence.Iterator(opened):
                number += 1
                yield Page(source.number, number, _grey(frame.copy()))
    except (OSError, Image.DecompressionBombError, ValueError, SyntaxError):
        raise InputError(source.number, "cannot be read as an image") from None


def iter_pages(sources):
    """Every page of every source, in order, one at a time (nothing is kept)."""
    if missing_packages():
        raise MissingDependency("the Python packages needed to read pages are not installed")
    for source in sources:
        reader = _pdf_pages if source.kind == "pdf" else _image_pages
        yield from reader(source)
