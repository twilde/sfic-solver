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


def test_no_accidental_lists_from_wrapped_prose():
    """A wrapped line that starts like a list item ("+ x", "97.") renders as a list.

    Genuine list items follow a blank line or another list line; a marker right
    after ordinary prose means a sentence was wrapped at the wrong place.
    """
    marker = re.compile(r"^\s*(\+|-|\*|\d+[.)])(\s|$)")
    in_fence, prev = False, ""
    offenders = []
    for number, line in enumerate((ROOT / "README.md").read_text().splitlines(), 1):
        if line.startswith("```"):
            in_fence = not in_fence
        elif not in_fence:
            prose_before = prev.strip() and not marker.match(prev) and not prev.startswith(" ")
            if marker.match(line) and prose_before:
                offenders.append(f"README.md:{number}: {line!r}")
        prev = line
    assert not offenders, "\n".join(offenders)
