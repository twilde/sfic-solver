"""The scanner's optional dependencies: what happens without them (D2, D38).

These tests need none of the scan extra, because they are about its absence.
"""
import importlib
import importlib.util
import pkgutil
import subprocess
import sys
import textwrap

import pytest

import sfic_solver
from sfic_solver import scanning

BLOCKER = textwrap.dedent('''
    import importlib.abc, sys

    class Block(importlib.abc.MetaPathFinder):
        def find_spec(self, name, path=None, target=None):
            if name.split(".")[0] in {"PIL", "numpy", "pypdfium2"}:
                raise ImportError(f"{name} is blocked for this test")

    sys.meta_path.insert(0, Block())
''')


def run_blocked(code):
    return subprocess.run([sys.executable, "-c", BLOCKER + textwrap.dedent(code)],
                          capture_output=True, text=True)


def test_missing_packages_names_what_to_install(monkeypatch):
    real = importlib.util.find_spec
    monkeypatch.setattr(importlib.util, "find_spec",
                        lambda name, *a: None if name in ("PIL", "pypdfium2") else real(name, *a))
    assert scanning.missing_packages() == ["Pillow", "pypdfium2"]


def test_require_names_packages_and_install_command(monkeypatch):
    monkeypatch.setattr(scanning, "missing_packages", lambda: ["numpy"])
    monkeypatch.setattr(scanning, "find_tesseract", lambda explicit=None: "/bin/true")
    with pytest.raises(scanning.MissingDependency) as err:
        scanning.require()
    assert "numpy" in str(err.value)
    assert scanning.INSTALL_HINT in str(err.value)


def test_require_reports_everything_missing_at_once(monkeypatch):
    monkeypatch.setattr(scanning, "missing_packages", lambda: ["Pillow"])
    monkeypatch.setenv("PATH", "")
    monkeypatch.delenv(scanning.TESSERACT_ENV, raising=False)
    with pytest.raises(scanning.MissingDependency) as err:
        scanning.require()
    message = str(err.value)
    assert "Pillow" in message and "Tesseract" in message
    assert "brew install tesseract" in message


def test_tesseract_is_found_on_the_path_or_where_told(monkeypatch, tmp_path):
    fake = tmp_path / "fake-tesseract"
    fake.write_text("#!/bin/sh\necho 'tesseract 9.9.9'\n")
    fake.chmod(0o755)
    monkeypatch.delenv(scanning.TESSERACT_ENV, raising=False)
    assert scanning.find_tesseract(str(fake)) == str(fake)
    monkeypatch.setenv(scanning.TESSERACT_ENV, str(fake))
    assert scanning.find_tesseract() == str(fake)
    assert scanning.tesseract_version(str(fake)) == "tesseract 9.9.9"


def test_a_tesseract_path_that_does_not_exist_is_refused(monkeypatch, tmp_path):
    monkeypatch.delenv(scanning.TESSERACT_ENV, raising=False)
    with pytest.raises(scanning.MissingDependency, match="was not found"):
        scanning.find_tesseract(str(tmp_path / "nope"))


def test_version_of_a_program_that_cannot_run_is_empty(tmp_path):
    assert scanning.tesseract_version(str(tmp_path / "nope")) == ""


def test_the_scanning_package_imports_without_the_packages():
    run = run_blocked('''
        import sfic_solver.scanning, sfic_solver.scanning.pages
        print("imported")
    ''')
    assert run.returncode == 0, run.stderr
    assert "imported" in run.stdout


def core_modules():
    names = [info.name for info in pkgutil.iter_modules(sfic_solver.__path__, "sfic_solver.")
             if not info.name.startswith("sfic_solver.scanning")
             and not info.name.endswith("scan_charts")]
    assert "sfic_solver.check_system" in names
    return names


@pytest.mark.parametrize("module", core_modules())
def test_every_core_module_imports_with_the_scan_packages_blocked(module):
    run = run_blocked(f'''
        import importlib
        importlib.import_module({module!r})
        print("imported")
    ''')
    assert run.returncode == 0, run.stderr
    assert "imported" in run.stdout


def test_reading_pages_without_the_packages_says_so(monkeypatch):
    from sfic_solver.scanning import pages
    monkeypatch.setattr(pages, "missing_packages", lambda: ["Pillow"])
    with pytest.raises(scanning.MissingDependency):
        list(pages.iter_pages([]))
