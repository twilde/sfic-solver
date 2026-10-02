"""The README's worked example must stay a real, clean system file."""
import json
import re

from conftest import ROOT, run_script


def json_blocks():
    text = (ROOT / "README.md").read_text()
    return [json.loads(b) for b in re.findall(r"```json\n(.*?)```", text, re.S)]


def example_blocks():
    return [block for block in json_blocks() if "cores" in block]


def test_readme_has_a_worked_example():
    assert len(example_blocks()) == 1


def test_readme_example_is_system_example_json():
    shown = example_blocks()[0]
    actual = json.loads((ROOT / "system.example.json").read_text())
    actual.pop("_comment")
    assert shown == actual


def test_readme_example_checks_clean(write_cfg):
    proc = run_script("check_system", write_cfg(example_blocks()[0]))
    assert proc.returncode == 0, proc.stdout


def markdown_files():
    return sorted(p for p in ROOT.rglob("*.md") if ".git" not in p.parts)


def test_no_accidental_lists_from_wrapped_prose():
    """A wrapped line that starts like a list item ("+ x", "97.") renders as a list.

    Genuine list items follow a blank line or another list line; a marker right
    after ordinary prose means a sentence was wrapped at the wrong place. Checked
    for every Markdown file in the repo.
    """
    marker = re.compile(r"^\s*(\+|-|\*|\d+[.)])(\s|$)")
    offenders = []
    for path in markdown_files():
        in_fence, prev = False, ""
        for number, line in enumerate(path.read_text().splitlines(), 1):
            if line.startswith("```"):
                in_fence = not in_fence
            elif not in_fence:
                prose_before = prev.strip() and not marker.match(prev) and not prev.startswith(" ")
                if marker.match(line) and prose_before:
                    offenders.append(f"{path.relative_to(ROOT)}:{number}: {line!r}")
            prev = line
    assert not offenders, "\n".join(offenders)


def test_markdown_files_are_found():
    names = {p.name for p in markdown_files()}
    assert {"README.md", "CLAUDE.md", "TODO.md", "decisions.md"} <= names


def test_license_is_mit_and_declared_consistently():
    text = (ROOT / "LICENSE").read_text()
    assert text.startswith("MIT License")
    assert "Copyright (c) 2026 Tim Wilde" in text
    assert re.search(r'^license = "MIT"$', (ROOT / "pyproject.toml").read_text(), re.M)
    assert "[MIT](LICENSE)" in (ROOT / "README.md").read_text()


def test_minimum_python_is_stated_consistently():
    """pyproject, README and the CI matrix must agree on the oldest Python."""
    floor = re.search(r'^requires-python = ">=(\d+\.\d+)"$',
                      (ROOT / "pyproject.toml").read_text(), re.M).group(1)
    assert f"Python {floor} or newer" in (ROOT / "README.md").read_text()
    assert f"Python {floor} or newer" in (ROOT / "CONTRIBUTING.md").read_text()
    matrix = re.search(r"^\s+python-version: \[(.*)\]$",
                       (ROOT / ".github/workflows/ci.yml").read_text(), re.M).group(1)
    versions = [tuple(map(int, v.strip(' "').split("."))) for v in matrix.split(",")]
    assert min(versions) == tuple(map(int, floor.split(".")))
