"""Shared helpers for the test suite."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


def run_script(name, *args, cwd=None):
    """Run a root-level command (e.g. "check_system") as a user would."""
    return subprocess.run([sys.executable, str(ROOT / f"{name}.py"), *map(str, args)],
                          capture_output=True, text=True, cwd=cwd)


def call_main(main, args, monkeypatch):
    """Call a CLI main() in-process with the given argv; return its exit status."""
    monkeypatch.setattr(sys, "argv", ["prog", *map(str, args)])
    try:
        rc = main()
    except SystemExit as exc:
        rc = exc.code
    if rc is None:
        return 0
    return rc if isinstance(rc, int) else 1


@pytest.fixture
def clean_cfg():
    """A fresh copy of the fake, clean system (fixtures/clean.json)."""
    return json.loads((FIXTURES / "clean.json").read_text())


@pytest.fixture
def write_cfg(tmp_path):
    """Write a config dict to a temp file and return its path."""
    def write(cfg, name="system.json"):
        path = tmp_path / name
        path.write_text(json.dumps(cfg, indent=2))
        return path
    return write
