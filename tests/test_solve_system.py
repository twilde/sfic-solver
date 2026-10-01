"""solve_system: fills null bittings without touching known keys."""
import json
import random

import pytest

from sfic_solver import solve_system
from conftest import call_main, run_script

SECTIONS = ("keys", "retired_keys", "control_keys")


@pytest.fixture
def unsolved(clean_cfg):
    """The clean system with the unit master and a control key left for the solver."""
    clean_cfg["keys"]["unit_master"] = None
    clean_cfg["control_keys"]["control_common"] = None
    return clean_cfg


def solve(write_cfg, cfg, tmp_path, *extra, seed=1):
    out = tmp_path / "solved.json"
    proc = run_script("solve_system", write_cfg(cfg), "--out", out, "--trials", 300,
                      "--seed", seed, *extra)
    return proc, out


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_solution_fills_nulls_keeps_known_keys_and_passes_check(
        unsolved, write_cfg, tmp_path, seed):
    proc, out = solve(write_cfg, unsolved, tmp_path, seed=seed)
    assert proc.returncode == 0, proc.stderr
    solved = json.loads(out.read_text())

    for section in SECTIONS:
        for name, bitting in unsolved.get(section, {}).items():
            if bitting is None:
                got = solved[section][name]
                assert isinstance(got, str) and len(got) == 7 and got.isdigit()
            else:
                assert solved[section][name] == bitting      # known keys untouched
    assert solved["cores"] == unsolved["cores"]
    assert {k: v for k, v in solved.items() if k not in SECTIONS} == \
        {k: v for k, v in unsolved.items() if k not in SECTIONS}

    # The solver ends by running the full check; run it ourselves too.
    assert run_script("check_system", out).returncode == 0
    assert "Wrote" in proc.stdout and "OK" in proc.stdout


def test_same_seed_gives_same_result(unsolved, write_cfg, tmp_path):
    _, a = solve(write_cfg, unsolved, tmp_path, seed=5)
    first = a.read_text()
    _, b = solve(write_cfg, unsolved, tmp_path, seed=5)
    assert b.read_text() == first


def test_default_output_name(unsolved, write_cfg):
    path = write_cfg(unsolved)
    proc = run_script("solve_system", path, "--trials", 100, "--seed", 1)
    assert proc.returncode == 0
    assert (path.parent / "system.solved.json").exists()


def test_solves_a_whole_system_from_scratch(clean_cfg, write_cfg, tmp_path):
    for section in SECTIONS:
        for name in clean_cfg.get(section, {}):
            if section != "retired_keys" and not name.startswith("unit:"):
                clean_cfg[section][name] = None
    proc, out = solve(write_cfg, clean_cfg, tmp_path)
    assert proc.returncode == 0, proc.stderr
    solved = json.loads(out.read_text())
    assert all(v is not None for s in SECTIONS for v in solved[s].values())
    assert run_script("check_system", out).returncode == 0


def test_known_keys_survive_even_when_they_conflict(unsolved, write_cfg, tmp_path):
    # A fixed-key conflict can't be solved away: the known keys must stay as they
    # are and the final check must report the problem.
    unsolved["keys"]["key_c"] = unsolved["keys"]["key_b"]      # duplicate known keys
    proc, out = solve(write_cfg, unsolved, tmp_path)
    solved = json.loads(out.read_text())
    assert solved["keys"]["key_b"] == solved["keys"]["key_c"] == unsolved["keys"]["key_b"]
    assert "DUPLICATE" in proc.stdout


def test_nothing_to_solve_exits_with_message(clean_cfg, write_cfg):
    proc = run_script("solve_system", write_cfg(clean_cfg))
    assert proc.returncode == 1
    assert "no unknown (null) keys" in proc.stderr


def test_retired_keys_must_be_known(unsolved, write_cfg):
    unsolved["retired_keys"]["old_master"] = None
    proc = run_script("solve_system", write_cfg(unsolved))
    assert proc.returncode != 0
    assert "retired keys must be known" in proc.stderr


def test_uses_system_randomness_by_default(unsolved, write_cfg, tmp_path, monkeypatch):
    created = []

    class Recording(random.Random):
        def __init__(self):
            super().__init__(0)
            created.append(self)

    monkeypatch.setattr(random, "SystemRandom", Recording)
    out = tmp_path / "out.json"
    rc = call_main(solve_system.main,
                   [write_cfg(unsolved), "--out", out, "--trials", 50], monkeypatch)
    assert rc == 0
    assert created, "without --seed the solver must use random.SystemRandom"


def test_seed_selects_a_seeded_generator(unsolved, write_cfg, tmp_path, monkeypatch):
    def boom():
        raise AssertionError("SystemRandom must not be used when --seed is given")

    monkeypatch.setattr(random, "SystemRandom", boom)
    out = tmp_path / "out.json"
    rc = call_main(solve_system.main,
                   [write_cfg(unsolved), "--out", out, "--trials", 50, "--seed", 3], monkeypatch)
    assert rc == 0
