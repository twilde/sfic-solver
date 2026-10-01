"""The stray-JSON guard (pre-commit hook and CI), plus fixture hygiene."""
import importlib.util
import json
import subprocess
import sys

import pytest

from conftest import FIXTURES, ROOT

_spec = importlib.util.spec_from_file_location(
    "check_no_stray_json", ROOT / "scripts" / "check_no_stray_json.py")
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)


@pytest.mark.parametrize("path", [
    "system.example.json",
    "tests/fixtures/clean.json",
    "tests/fixtures/nested/other.json",
    "README.md",
    "sfic_solver/check_system.py",
    "notes.jsonl",
])
def test_allowed(path):
    assert guard.find_stray([path]) == []


@pytest.mark.parametrize("path", [
    "system.json",
    "system.solved.json",
    "mine/system.json",
    "tests/system.json",
    "tests/fixtures.json",
    "subdir/system.example.json",       # only the root example is allowed
    "SYSTEM.JSON",
    "tests/fixturesX/a.json",
])
def test_stray(path):
    assert guard.find_stray([path]) == [path]


def test_main_exit_status(capsys):
    assert guard.main(["system.example.json"]) == 0
    assert guard.main(["real.json"]) == 1
    assert "real.json" in capsys.readouterr().err


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), "-c", "user.name=t",
                           "-c", "user.email=t@example.invalid", *args],
                          capture_output=True, text=True, check=True)


def run_guard(repo, mode):
    return subprocess.run([sys.executable, str(ROOT / "scripts" / "check_no_stray_json.py"), mode],
                          cwd=repo, capture_output=True, text=True)


def test_staged_and_history_modes_in_a_scratch_repo(tmp_path):
    git(tmp_path, "init", "-q")
    (tmp_path / "ok.txt").write_text("x")
    git(tmp_path, "add", "ok.txt")
    assert run_guard(tmp_path, "--staged").returncode == 0

    (tmp_path / "real.json").write_text("{}")
    git(tmp_path, "add", "-f", "real.json")
    assert run_guard(tmp_path, "--staged").returncode == 1

    git(tmp_path, "commit", "-q", "-m", "c1")
    assert run_guard(tmp_path, "--tracked").returncode == 1
    git(tmp_path, "rm", "-q", "real.json")
    git(tmp_path, "commit", "-q", "-m", "c2")
    assert run_guard(tmp_path, "--tracked").returncode == 0
    assert run_guard(tmp_path, "--history").returncode == 1      # still in history


def test_fixtures_are_marked_fake():
    files = sorted(FIXTURES.rglob("*.json"))
    assert files
    for path in files:
        cfg = json.loads(path.read_text())
        assert str(cfg.get("_comment", "")).startswith("FAKE"), \
            f"{path.name}: fixtures must carry a _comment starting with FAKE"
