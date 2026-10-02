"""Reading scanned pinning charts (see docs/designs/chart-scanning.md).

This subpackage is the one place in the project that needs more than the standard
library, and it is an exception to D2 on stated terms: the dependencies are optional
(the `scan` extra, plus the Tesseract program), nothing outside this subpackage
imports them, and the command says what is missing instead of failing with a
traceback. Importing this module imports nothing optional; each stage imports what
it needs when it runs, after `require()` has checked that it is there.

A scan is key data. Nothing here writes an image to disk, opens a network
connection, or puts a digit read from a page into an error message: errors say which
input, page, chart, row and chamber, and what kind of problem.
"""
import importlib.util
import os
import shutil
import subprocess

# Python package (import name) -> what to install.
PACKAGES = {"PIL": "Pillow", "numpy": "numpy", "pypdfium2": "pypdfium2"}
INSTALL_HINT = 'pip install -e ".[scan]"'
TESSERACT_HINT = ("brew install tesseract (macOS), apt install tesseract-ocr "
                  "(Debian, Ubuntu), or the UB Mannheim installer (Windows)")
TESSERACT_ENV = "SFIC_TESSERACT"


class ScanError(Exception):
    """Something went wrong reading a scan. The message never contains page content."""


class MissingDependency(ScanError):
    """A package or program the scanner needs is not installed."""


class InputError(ScanError):
    """An input cannot be used. `source` is its position in the order given (1-based)."""

    def __init__(self, source, reason):
        super().__init__(f"input {source}: {reason}")
        self.source, self.reason = source, reason


def missing_packages():
    """The names to install for the optional Python packages that are not there."""
    return [name for module, name in PACKAGES.items()
            if importlib.util.find_spec(module) is None]


def find_tesseract(explicit=None):
    """The Tesseract program: `explicit` (--tesseract), else $SFIC_TESSERACT, else the
    path. Raises MissingDependency, with how to install it, if there is none."""
    wanted = explicit or os.environ.get(TESSERACT_ENV)
    found = shutil.which(wanted) if wanted else shutil.which("tesseract")
    if found is None:
        what = f"the Tesseract program {wanted!r} was not found" if wanted \
            else "the Tesseract program was not found on the path"
        raise MissingDependency(f"{what}; install it with {TESSERACT_HINT}, or say where "
                                f"it is with --tesseract or ${TESSERACT_ENV}")
    return found


def tesseract_version(program):
    """The first line of `tesseract --version`, for the report ('' if it cannot be run)."""
    try:
        out = subprocess.run([program, "--version"], capture_output=True, text=True,
                             timeout=30)
    except (OSError, subprocess.SubprocessError):
        return ""
    text = (out.stdout or out.stderr).strip()
    return text.splitlines()[0] if text else ""


def require(tesseract=None):
    """Check everything the scanner needs and return the path of Tesseract.

    Raises MissingDependency naming everything that is missing and how to install it.
    """
    problems = []
    missing = missing_packages()
    if missing:
        problems.append(f"the Python packages {', '.join(missing)} are not installed; "
                        f"install them with {INSTALL_HINT}")
    program = None
    try:
        program = find_tesseract(tesseract)
    except MissingDependency as err:
        problems.append(str(err))
    if problems:
        raise MissingDependency("; and ".join(problems))
    return program
