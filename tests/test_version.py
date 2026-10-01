"""The version lives in one place: sfic_solver.__version__."""
import re

from conftest import ROOT
from sfic_solver import __version__


def test_version_looks_like_semver():
    assert re.fullmatch(r"\d+\.\d+\.\d+", __version__)


def test_pyproject_reads_the_version_from_the_package():
    text = (ROOT / "pyproject.toml").read_text()
    project = text[text.index("[project]"):text.index("[project.optional-dependencies]")]
    assert not re.search(r"^version\s*=", project, re.M), "version must not be duplicated"
    assert 'dynamic = ["version"]' in project
    assert re.search(r'^version = \{attr = "sfic_solver\.__version__"\}$', text, re.M)
