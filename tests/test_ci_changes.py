"""CI runs the scanner's slow checks only when a change can affect them (D46)."""
import ast
import importlib.util
import re
import shutil
import subprocess
import textwrap

import pytest

from conftest import ROOT

_spec = importlib.util.spec_from_file_location("ci_changes", ROOT / "scripts" / "ci_changes.py")
ci = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ci)

# Imported by the scanner's code or tests, but only as a package marker and the version.
NOT_THE_SCANNER = {"sfic_solver/__init__.py"}


@pytest.mark.parametrize("path", [
    "sfic_solver/scanning/layout.py",
    "sfic_solver/scan_charts.py",
    "sfic_solver/charts.py",
    "sfic_solver/pinning.py",
    "check_charts.py",
    "scan_charts.py",
    "tests/test_scan_layout.py",
    "tests/scan_harness.py",
    "pyproject.toml",
    ".github/workflows/ci.yml",
    "scripts/ci_changes.py",
])
def test_scanner_files_and_what_it_uses_are_affecting(path):
    assert ci.touches_scanner([path]) == [path]


@pytest.mark.parametrize("path", [
    "README.md",
    "docs/design.md",
    "TODO.md",
    "sfic_solver/model.py",
    "sfic_solver/check_system.py",
    "sfic_solver/gen_bittings.py",
    "check_system.py",
    "gen_bittings.py",
    "tests/test_model.py",
    "tests/test_readme.py",
    "scripts/check_no_stray_data.py",
    ".github/dependabot.yml",
])
def test_other_files_are_not(path):
    assert ci.touches_scanner([path]) == []


def test_it_reports_which_paths_decided():
    assert ci.touches_scanner(["README.md", "sfic_solver/charts.py", "tests/test_model.py"]) == [
        "sfic_solver/charts.py"]


def imported_files(path):
    """The repo files (in sfic_solver/ and tests/) that `path` imports, by reading it."""
    here = path.relative_to(ROOT).parent
    found = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = here.parts[:len(here.parts) - (node.level - 1)]
                module = ".".join(base + tuple(filter(None, [node.module])))
            else:
                module = node.module
            names = [module] + [f"{module}.{a.name}" for a in node.names]
        else:
            continue
        for name in names:
            parts = name.split(".")
            for root in (ROOT, ROOT / "tests"):
                for candidate in (root.joinpath(*parts).with_suffix(".py"),
                                  root.joinpath(*parts, "__init__.py")):
                    if candidate.is_file() and candidate.is_relative_to(ROOT):
                        found.add(candidate)
    return found


def scripts_run_by(path):
    """The root scripts a test runs as commands: run_script("name", ...) or ROOT / "name.py"."""
    text = path.read_text()
    names = re.findall(r'run_script\(\s*"(\w+)"', text) + re.findall(r'ROOT / "(\w+)\.py"', text)
    return {ROOT / f"{name}.py" for name in names if (ROOT / f"{name}.py").is_file()}


def scanner_closure():
    """Every repo file the scanner's code and tests import or run as a command, transitively."""
    todo = {*(ROOT / "sfic_solver" / "scanning").glob("*.py"),
            ROOT / "sfic_solver" / "scan_charts.py",
            *(ROOT / "tests").glob("test_scan_*.py"), *(ROOT / "tests").glob("scan_*.py")}
    seen = set()
    while todo:
        path = todo.pop()
        seen.add(path)
        todo |= (imported_files(path) | scripts_run_by(path)) - seen
    return {p.relative_to(ROOT).as_posix() for p in seen} - NOT_THE_SCANNER


def test_everything_the_scanner_imports_is_in_the_list():
    """A scanner dependency missing from SCANNER_PREFIXES would let a change to it skip the tests."""
    closure = scanner_closure()
    assert {"sfic_solver/charts.py", "sfic_solver/pinning.py", "sfic_solver/check_charts.py",
            "check_charts.py", "scan_charts.py", "tests/conftest.py"} <= closure, \
        "the import walk found too little"
    missing = sorted(p for p in closure if not ci.touches_scanner([p]))
    assert missing == [], f"add these to SCANNER_PREFIXES in scripts/ci_changes.py: {missing}"


def git(cwd, *args):
    subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@example.invalid",
                    "-c", "commit.gpgsign=false", *args], cwd=cwd, check=True,
                   capture_output=True, text=True)


def commit_file(repo, name, text="x"):
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    git(repo, "add", name)
    git(repo, "commit", "-m", f"change {name}")


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q", "-b", "main")
    commit_file(tmp_path, "README.md")
    git(tmp_path, "checkout", "-q", "-b", "feature")
    return tmp_path


def run(repo, *args):
    return subprocess.run(["python3", str(ROOT / "scripts" / "ci_changes.py"), *args],
                          cwd=repo, capture_output=True, text=True)


def test_a_branch_that_changes_only_docs_skips_the_scanner(repo):
    commit_file(repo, "docs/design.md")
    commit_file(repo, "sfic_solver/model.py")
    result = run(repo, "--base", "main")
    assert result.returncode == 0
    assert result.stdout == "scanner=false\n"


def test_a_branch_that_touches_the_scanner_runs_it(repo):
    commit_file(repo, "docs/design.md")
    commit_file(repo, "sfic_solver/scanning/layout.py")
    result = run(repo, "--base", "main")
    assert result.stdout == "scanner=true\n"
    assert "sfic_solver/scanning/layout.py" in result.stderr


def test_changes_made_on_main_after_the_branch_left_it_are_not_the_branchs(repo):
    git(repo, "checkout", "-q", "main")
    commit_file(repo, "sfic_solver/scanning/layout.py")       # lands on main only
    git(repo, "checkout", "-q", "feature")
    commit_file(repo, "docs/design.md")
    assert run(repo, "--base", "main").stdout == "scanner=false\n"


def test_with_no_base_everything_runs(repo):
    assert run(repo).stdout == "scanner=true\n"


def test_when_git_cannot_say_everything_runs(repo):
    result = run(repo, "--base", "no-such-branch")
    assert result.returncode == 0
    assert result.stdout == "scanner=true\n"
    assert "could not list the changes" in result.stderr


def test_ci_runs_the_script_and_gates_the_scanner_job_on_it():
    """The workflow, the script and the job names must agree."""
    text = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    assert "scripts/ci_changes.py" in text
    scanner_job = text[text.index("\n  scanner:"):text.index("\n  ci:")]
    assert re.search(r"needs\.changes\.outputs\.scanner == 'true'", scanner_job)
    # the core job must not install the extra, or it would not show that the core runs without it
    test_job = text[text.index("\n  test:"):text.index("\n  scanner:")]
    commands = "\n".join(line for line in test_job.splitlines() if not line.lstrip().startswith("#"))
    assert "scan]" not in commands and "tesseract" not in commands.lower()


def test_ci_runs_once_per_change_not_on_every_push():
    """Pull requests plus main and tags; an unrestricted `push:` tests each PR commit twice."""
    text = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    triggers = text[text.index("\non:"):text.index("\npermissions:")]
    lines = [line.strip() for line in triggers.splitlines() if not line.lstrip().startswith("#")]
    assert "pull_request:" in lines
    assert "workflow_dispatch:" in lines
    assert "branches: [main]" in lines, "push must be limited to main"


def test_only_pull_requests_cancel_each_other():
    """Cancel superseded pull request runs; give every other run its own group (D48)."""
    text = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    block = text[text.index("\nconcurrency:"):text.index("\njobs:")]
    lines = [line.strip() for line in block.splitlines() if not line.lstrip().startswith("#")]
    group = next(line for line in lines if line.startswith("group:"))
    assert "github.event_name == 'pull_request'" in group and "github.run_id" in group
    assert "cancel-in-progress: ${{ github.event_name == 'pull_request' }}" in lines


def workflow_jobs():
    """The workflow's jobs, each as its block of text, by job id."""
    text = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    section = text[text.index("\njobs:\n") + len("\njobs:\n"):]
    parts = re.split(r"^  ([a-z][a-z0-9-]*):\n", section, flags=re.M)
    return dict(zip(parts[1::2], parts[2::2]))


def test_every_job_has_a_timeout():
    """The default is six hours; a hung Tesseract should not run that long."""
    for name, block in workflow_jobs().items():
        assert re.search(r"^    timeout-minutes: \d+", block, re.M), f"job {name} has no timeout"


def test_the_tests_report_their_slowest_cases():
    text = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    runs = re.findall(r"run: python -m pytest .*", text)
    assert len(runs) == 2 and all("--durations=10" in run for run in runs)


def test_the_summary_job_waits_for_every_other_job_and_always_runs():
    jobs = workflow_jobs()
    summary = jobs["ci"]
    assert re.search(r"^    if: always\(\)$", summary, re.M)
    needs = re.search(r"^    needs: \[(.*)\]$", summary, re.M).group(1).split(", ")
    assert sorted(needs) == sorted(set(jobs) - {"ci"}), "a job is missing from the summary's needs"


def summary_script():
    block = workflow_jobs()["ci"]
    lines = block[block.index("        run: |\n") + len("        run: |\n"):].splitlines()
    return textwrap.dedent("\n".join(line for line in lines if line.strip() and not
                                      line.lstrip().startswith("#")))


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")
@pytest.mark.parametrize("results, wanted, passes", [
    (("success", "success", "success", "skipped"), "false", True),
    (("success", "success", "success", "success"), "true", True),
    (("success", "success", "success", "skipped"), "true", False),     # wanted but not run
    (("success", "success", "success", "failure"), "true", False),
    (("success", "success", "success", "cancelled"), "true", False),
    (("success", "success", "failure", "skipped"), "false", False),
    (("cancelled", "success", "success", "skipped"), "false", False),
    (("success", "failure", "success", "skipped"), "", False),         # the comparison failed
    (("success", "success", "skipped", "skipped"), "false", False),    # tests must not be skipped
])
def test_the_summary_passes_only_when_everything_that_should_have_run_did(results, wanted, passes):
    guard, changes, test, scanner = results
    env = {"GUARD": guard, "CHANGES": changes, "TEST": test, "SCANNER": scanner,
           "SCANNER_WANTED": wanted, "PATH": "/usr/bin:/bin"}
    result = subprocess.run(["bash", "-e", "-c", summary_script()], env=env,
                            capture_output=True, text=True)
    assert (result.returncode == 0) is passes, result.stdout + result.stderr


def test_sessions_and_reviewers_are_told_the_command_the_script_answers_to():
    """CLAUDE.md and docs/reviewing.md name the command (D50); it must stay a real one."""
    command = "python3 scripts/ci_changes.py --base origin/main"
    for name in ("CLAUDE.md", "docs/reviewing.md"):
        assert command in " ".join((ROOT / name).read_text().split()), name
    assert (ROOT / "scripts" / "ci_changes.py").is_file()
