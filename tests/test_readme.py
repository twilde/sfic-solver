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


def test_every_command_is_in_the_readme_table_and_the_scanner_exception_is_stated():
    """One fact in several files (D43): the commands, the scan extra and the exception."""
    import tomllib

    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    readme = (ROOT / "README.md").read_text()
    for script in project["scripts"]:
        assert f"`{script}`" in readme, script
    # The extra's packages are named where the README says what the extra is.
    for package in project["optional-dependencies"]["scan"]:
        assert package in readme, package
    assert project["dependencies"] == []
    for name in ("README.md", "CLAUDE.md", "CONTRIBUTING.md", "SECURITY.md"):
        assert says_standard_library_with_the_exception(ROOT / name), name


def says_standard_library_with_the_exception(path):
    """Whether a paragraph of the file says "standard library" and, in the same
    paragraph, names the scanner as an exception. A file that mentions scanning
    elsewhere does not count; reverting the sentence must fail the test."""
    for paragraph in re.split(r"\n\s*\n", path.read_text()):
        text = " ".join(paragraph.lower().split())
        if "standard library" in text and "exception" in text and "scan" in text:
            return True
    return False


def test_the_readme_install_line_is_the_one_the_tool_prints():
    from sfic_solver.scanning import INSTALL_HINT, TESSERACT_ENV

    readme = (ROOT / "README.md").read_text()
    assert INSTALL_HINT in readme
    assert "brew install tesseract" in readme and "apt install tesseract-ocr" in readme
    assert TESSERACT_ENV in readme


# -- the key shape rules table (D64) -------------------------------------------------

def shape_rule_rows():
    """{rule: (flag cell, default cell)} from the README's key shape rules table."""
    text = (ROOT / "README.md").read_text()
    section = text.split("## Key shape rules")[1].split("\n## ")[0]
    rows = re.findall(r"^\| `(\w+)` \| (.+?) \| (.+?) \| .+ \|$", section, re.M)
    return {rule: (flag, default) for rule, flag, default in rows}


def test_readme_shape_table_has_every_rule_with_its_default():
    from sfic_solver import model
    defaults = model.ShapeRules()
    rows = shape_rule_rows()
    assert list(rows) == list(model.SHAPE_RULES)
    for rule, (_, shown) in rows.items():
        value = getattr(defaults, rule)
        assert shown == ("off" if value is None else "on" if value is True else str(value)), rule


def test_readme_shape_table_names_every_flag_the_tools_take():
    import argparse
    from sfic_solver.shape_args import add_shape_arguments
    ap = argparse.ArgumentParser()
    add_shape_arguments(ap)
    flags = {s for action in ap._actions for s in action.option_strings if s.startswith("--")}
    flags.discard("--help")
    cells = " ".join(flag for flag, _ in shape_rule_rows().values())
    assert all(flag in cells for flag in flags), flags


def test_readme_shape_example_commands_run():
    proc = run_script("check_bittings", "--master", "top", "top=0453037", "area=6130254")
    assert proc.returncode == 0 and "SHAPE" not in proc.stdout, proc.stdout
    assert run_script("gen_bittings", "--pins", 7, "-n", 3, "--master").returncode == 0
    assert run_script("gen_bittings", "OOEOEOE", "-n", 8, "--max-run", 2).returncode == 0
