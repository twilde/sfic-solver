"""solve_system: fills null bittings without touching known keys."""
import json
import random
import re

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


# -- pinning (opt-in): core-pinning.md step 5, part 5b ------------------------------

from conftest import FIXTURES
from sfic_solver.config import parse_config
from sfic_solver.pinning import pin_chambers
from sfic_solver.population import pinnable_fraction


@pytest.fixture
def pinned():
    """The fake pinning system without its parity pattern, the unit master left for the solver."""
    raw = json.loads((FIXTURES / "pinning.json").read_text())
    del raw["pattern"]
    raw["min_diff"] = 3
    raw["keys"]["unit_master"] = None
    return raw


def problem(raw):
    return solve_system.Problem(parse_config(raw, allow_null=True))


def unit_core(prob):
    return next(core for core in prob.cores if core["is_unit"])


def without_pinning(raw):
    raw = json.loads(json.dumps(raw))
    del raw["pinning"]
    for core in raw["cores"]:
        del core["control"]
    return raw


def pinning_adds(raw, master):
    """What switching pinning on adds to a candidate master's score."""
    return (problem(raw).score_key("unit_master", master)
            - problem(without_pinning(raw)).score_key("unit_master", master))


def test_a_master_that_cannot_be_pinned_over_a_decoded_unit_key_is_a_hard_conflict(pinned):
    unit = json.loads((FIXTURES / "pinning.json").read_text())["keys"]["unit:101"]
    # Same cuts as unit:101 but the first one apart: no pin of size 1 exists (core 'unit:101').
    master = (int(unit[0]) + 1, *map(int, unit[1:]))
    assert pinning_adds(pinned, master) >= solve_system.HARD


def test_a_master_that_pins_over_every_decoded_unit_key_adds_no_hard_conflict(pinned):
    prob = problem(pinned)
    rng = random.Random(1)
    clean = [c for c in (prob.random_candidate(rng) for _ in range(300))
             if all(not pin_chambers(prob.pinning, [prob.assign[u], c],
                                     prob.assign["control_b"])[1]
                    for u in prob.assign if u.startswith("unit:"))]
    assert clean
    assert all(pinning_adds(pinned, c) < solve_system.HARD for c in clean[:5])


def test_without_pinning_the_rule_is_off_and_retired_cores_are_ignored(pinned):
    unit = json.loads((FIXTURES / "pinning.json").read_text())["keys"]["unit:101"]
    master = (int(unit[0]) + 1, *map(int, unit[1:]))
    off = without_pinning(pinned)
    prob = problem(off)
    assert prob.pinning is None and prob.population is None and prob.population_note is None
    assert problem(off).score_key("unit_master", master) < solve_system.HARD   # no penalty off


def test_the_unpinnable_figure_is_added_to_the_score_with_its_weight(pinned):
    prob = problem(pinned)
    core = unit_core(prob)
    master = prob.assign["area_a"]
    prob.assign["unit_master"] = master
    with_figure = prob.expected_unknown_conflicts(core)
    decoded = sum(1 for n in prob.assign if n.startswith("unit:"))
    unknown = prob.unit_count - decoded
    pairs = prob.unit_count * (prob.unit_count - 1) - decoded * (decoded - 1)
    base = pairs * prob.space.pair_conflict_probability([master], prob.population)
    cannot = 1 - pinnable_fraction(prob.space, prob.population, prob.pinning, [master],
                                   prob.assign[core["control"]])
    assert with_figure == pytest.approx(base + solve_system.UNPINNABLE_WEIGHT * unknown * cannot)
    assert solve_system.UNPINNABLE_WEIGHT == 1.0 and cannot > 0


def test_the_solver_picks_a_unit_master_every_decoded_unit_core_can_take(
        pinned, write_cfg, tmp_path):
    proc, out = solve(write_cfg, pinned, tmp_path, seed=4)
    assert proc.returncode == 0, proc.stderr
    assert "Undecoded unit keys are assumed to have sat in the retired core(s) Original cores." \
        in proc.stdout
    solved = json.loads(out.read_text())
    cfg = parse_config(solved)
    core = next(c for c in cfg.cores if c["is_unit"])
    for ch in core["changes"]:
        operating = [cfg.keys[ch]] + [cfg.keys[m] for m in core["masters"]]
        assert not pin_chambers(cfg.pinning, operating, cfg.control_keys[core["control"]])[1]
    assert "UNPINNABLE" not in proc.stdout


def test_the_solver_leaves_far_fewer_undecoded_units_unable_to_take_its_master(
        pinned, write_cfg, tmp_path):
    proc, out = solve(write_cfg, pinned, tmp_path, seed=4)
    cfg = parse_config(json.loads(out.read_text()))
    prob = solve_system.Problem(cfg)
    core = unit_core(prob)
    chosen = 1 - pinnable_fraction(cfg.space, prob.population, cfg.pinning,
                                   [cfg.keys["unit_master"]], cfg.control_keys[core["control"]])
    rng = random.Random(9)
    typical = sum(1 - pinnable_fraction(cfg.space, prob.population, cfg.pinning,
                                        [prob.random_candidate(rng)],
                                        cfg.control_keys[core["control"]])
                  for _ in range(50)) / 50
    assert chosen < 0.5 < typical          # about 21% against about 80% for a random master


def test_a_control_key_left_for_the_solver_pins_with_every_core_that_uses_it(
        pinned, write_cfg, tmp_path):
    pinned["keys"]["unit_master"] = json.loads((FIXTURES / "pinning.json").read_text())[
        "keys"]["unit_master"]
    pinned["control_keys"]["control_b"] = None
    proc, out = solve(write_cfg, pinned, tmp_path, seed=6)
    assert proc.returncode == 0, proc.stderr
    cfg = parse_config(json.loads(out.read_text()))
    for core in cfg.cores:
        for ch in core["changes"]:
            operating = [cfg.keys[ch]] + [cfg.keys[m] for m in core["masters"]]
            assert not pin_chambers(cfg.pinning, operating,
                                    cfg.control_keys[core["control"]])[1], (core["name"], ch)


def test_more_covering_retired_cores_than_the_limit_are_not_used_and_the_solver_says_so(
        pinned, write_cfg, tmp_path):
    template = pinned["retired_cores"][0]
    pinned["retired_cores"] = [{**template, "name": f"Old {n}"} for n in range(4)]
    prob = problem(pinned)
    assert prob.population is None
    assert "4 of them cover unit keys, and at most 3 can be combined exactly" \
        in prob.population_note
    proc, _ = solve(write_cfg, pinned, tmp_path, seed=4)
    assert "The retired cores were not used: 4 of them cover unit keys" in proc.stdout


def test_an_impossible_description_of_the_old_cores_is_not_used_and_the_solver_says_so(pinned):
    pinned["retired_keys"]["old_master"] = "9" * 7
    pinned["retired_keys"]["old_control"] = "0" * 7
    prob = problem(pinned)
    assert prob.population is None
    assert prob.population_note == "no valid bitting could have been pinned in them"


def test_the_summary_says_the_unpinnable_figure_was_weighed_first(pinned, write_cfg, tmp_path):
    proc, _ = solve(write_cfg, pinned, tmp_path, seed=4)
    line = next(ln for ln in proc.stdout.splitlines()
                if ln.startswith("The solver weighed this first:"))
    figure = re.search(r"about ([\d.]+) of (\d+) \((\d+)%\) vs (\d+)% for a typical random one",
                       line)
    assert figure and int(figure.group(2)) == 97
    assert int(figure.group(3)) < 50 < int(figure.group(4))
    assert "a master with more chance cross-operation can be the better one" in line


def test_without_pinning_the_summary_has_no_unpinnable_line(unsolved, write_cfg, tmp_path):
    proc, _ = solve(write_cfg, unsolved, tmp_path, seed=1)
    assert "The solver weighed this first" not in proc.stdout
