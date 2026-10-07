"""solve_system: fills null bittings without touching known keys."""
import collections
import itertools
import json
import random
import re

import pytest

from sfic_solver import solve_system
from conftest import call_main, run_script

SECTIONS = ("keys", "retired_keys", "control_keys")
RULES_OFF = {name: None for name in ("max_run", "max_same_depth", "forbid_monotone",
                                     "master_min_span", "min_total_variation")}


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


# -- saying so when the search failed (issue 26, part 1) -----------------------------

@pytest.fixture
def no_pinnable_master(pinned):
    """Ten decoded units whose first cuts are 0 to 9: whatever the master cuts there, it is one
    from a unit's cut, so some core cannot be pinned (no pin of size 1 exists)."""
    for digit in range(10):
        pinned["keys"][f"unit:{200 + digit}"] = f"{digit}555555"
    return pinned


def test_a_result_that_still_has_hard_conflicts_says_it_was_not_solved(
        no_pinnable_master, write_cfg, tmp_path):
    proc, out = solve(write_cfg, no_pinnable_master, tmp_path, seed=4)
    assert proc.returncode == 0, proc.stderr           # the exit status stays 0 (README)
    assert out.exists()
    lines = proc.stdout.splitlines()
    marks = [i for i, ln in enumerate(lines) if ln.startswith("NOT SOLVED")]
    wrote = next(i for i, ln in enumerate(lines) if ln.startswith("Wrote"))
    assert len(marks) == 2 and marks[0] < wrote < marks[1] == len(lines) - 1
    assert "unit_master" in lines[marks[0]] and "UNPINNABLE" in proc.stdout


def test_a_solved_result_does_not_say_it_was_not_solved(pinned, write_cfg, tmp_path):
    proc, _ = solve(write_cfg, pinned, tmp_path, seed=4)
    assert "NOT SOLVED" not in proc.stdout


def test_failed_keys_names_the_unknown_keys_with_a_hard_penalty(pinned):
    prob = problem(pinned)
    unit = json.loads((FIXTURES / "pinning.json").read_text())["keys"]["unit:101"]
    prob.assign["unit_master"] = (int(unit[0]) + 1, *map(int, unit[1:]))
    (name, count), = solve_system.failed_keys(prob)
    assert name == "unit_master" and count >= 1
    line, = solve_system.not_solved_lines(prob)
    assert line.startswith("NOT SOLVED") and f"unit_master ({count})" in line
    assert "see the check below" in line
    assert "see the check above" in solve_system.not_solved_lines(prob, "above")[0]
    prob.assign["unit_master"] = unit_clear_master(prob)
    assert solve_system.failed_keys(prob) == []
    assert solve_system.not_solved_lines(prob) == []


def unit_clear_master(prob):
    """A master that pins over every decoded unit key, found by drawing."""
    rng = random.Random(1)
    for _ in range(2000):
        cand = prob.random_candidate(rng)
        if prob.score_key("unit_master", cand) < solve_system.HARD:
            return cand
    raise AssertionError("no clean master drawn")


# -- building pinnable answers exactly (issue 26, part 2) ------------------------------

@pytest.fixture
def two_blank_masters(pinned):
    """The fixture with both masters left for the solver, which share cores with each other
    and with the decoded keys of the area cores (it used to leave about half the runs stuck)."""
    pinned["keys"]["master_top"] = None
    pinned["keys"]["master_sub"] = None
    pinned["keys"]["unit_master"] = json.loads((FIXTURES / "pinning.json").read_text())[
        "keys"]["unit_master"]
    return pinned


def assert_every_core_pins(path):
    cfg = parse_config(json.loads(path.read_text()))
    for core in cfg.cores:
        for ch in core["changes"]:
            operating = [cfg.keys[ch]] + [cfg.keys[m] for m in core["masters"]]
            assert not pin_chambers(cfg.pinning, operating,
                                    cfg.control_keys[core["control"]])[1], (core["name"], ch)


@pytest.mark.parametrize("seed", [5, 6, 7, 9, 11])     # 5, 6, 7, 9, 11 got stuck before
def test_two_blank_masters_sharing_cores_with_known_keys_come_out_pinnable(
        two_blank_masters, write_cfg, tmp_path, seed):
    proc, out = solve(write_cfg, two_blank_masters, tmp_path, seed=seed)
    assert proc.returncode == 0, proc.stderr
    assert "pinnable combinations with the known keys; scored" in proc.stdout
    assert "NOT SOLVED" not in proc.stdout and "UNPINNABLE" not in proc.stdout
    assert_every_core_pins(out)


def decoded_units(prob, count, seed=1):
    """Fake decoded unit keys, drawn at random: with seven of them a unit master has few
    pinnable bittings among about three million."""
    rng = random.Random(seed)
    return {f"unit:{300 + i}": "".join(map(str, prob.random_candidate(rng)))
            for i in range(count)}


def test_with_few_pinnable_masters_the_solver_scores_every_one_of_them(
        pinned, write_cfg, tmp_path):
    pinned["keys"].update(decoded_units(problem(pinned), 7))
    pinned["shape"] = RULES_OFF          # this test is about listing them all; see the rules below
    prob = problem(pinned)
    pinnable, _ = prob.pinnable_set(["unit_master"])
    # Count them without the construction: every bitting whose cuts can all be pinned.
    expected = brute_force_pinnable_masters(prob)
    assert 0 < expected < 2000 and pinnable.count == expected
    proc, out = solve(write_cfg, pinned, tmp_path, seed=3)
    assert f"unit_master: {expected} pinnable bittings with the known keys; scored all of them" \
        in proc.stdout
    assert "NOT SOLVED" not in proc.stdout and "UNPINNABLE" not in proc.stdout
    assert_every_core_pins(out)


def brute_force_pinnable_masters(prob):
    """How many MACS-valid bittings pin over every decoded unit, tried one position at a
    time (a per-position filter, then a plain walk over what is left)."""
    import itertools
    control = prob.assign["control_b"]
    units = [prob.assign[n] for n in prob.assign if n.startswith("unit:")]
    per_position = [[d for d in prob.space.digits[p]
                     if all(not pin_chambers(prob.pinning, [(u[p],), (d,)], (control[p],))[1]
                            for u in units)]
                    for p in range(prob.space.pins)]
    return sum(1 for cuts in itertools.product(*per_position) if prob.space.macs_ok(cuts))


def test_a_system_with_no_pinnable_master_says_so_and_that_running_again_will_not_help(
        no_pinnable_master, write_cfg, tmp_path):
    proc, out = solve(write_cfg, no_pinnable_master, tmp_path, seed=4)
    assert proc.returncode == 0 and out.exists()
    assert "unit_master: NO bitting can be pinned with the known keys: no cut at position 1 " \
        "leaves every core there pinnable" in proc.stdout
    lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("NOT SOLVED")]
    assert len(lines) == 2 and lines[-1] == proc.stdout.splitlines()[-1]
    assert "running it again will not help" in lines[0] and "a known key has to change" in lines[0]
    assert "hard conflicts involving" not in proc.stdout      # not also reported as a bad draw


def test_a_group_larger_than_the_limit_is_searched_a_key_at_a_time_and_says_so(
        two_blank_masters, write_cfg, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(solve_system, "MAX_JOINT_KEYS", 1)
    out = tmp_path / "solved.json"
    rc = call_main(solve_system.main, [write_cfg(two_blank_masters), "--out", out, "--trials", 100,
                                      "--seed", 5], monkeypatch)
    assert rc == 0 and out.exists()
    printed = capsys.readouterr().out
    assert "master_top, master_sub share cores and are more than the 1 keys that can be " \
        "built together: searching one key at a time" in printed
    assert "of random candidates were free of hard conflicts" in printed


def test_keys_that_share_a_core_are_grouped_and_others_are_not(pinned):
    pinned["keys"]["master_top"] = None
    pinned["keys"]["master_sub"] = None
    pinned["control_keys"]["control_b"] = None
    groups = problem(pinned).joint_groups()
    assert sorted(sorted(g) for g in groups) == [["control_b", "unit_master"],
                                                 ["master_sub", "master_top"]]


def test_without_pinning_no_group_is_built_and_the_search_is_the_old_one(unsolved, write_cfg,
                                                                         tmp_path):
    proc, _ = solve(write_cfg, unsolved, tmp_path, seed=1)
    assert "pinnable" not in proc.stdout
    assert "of random candidates were free of hard conflicts" in proc.stdout


# -- shape rules (docs/designs/key-shape-rules.md) ------------------------------------

def shape_breaks(key, master=False):
    """What a key breaks of the default shape rules, by plain loops, so the tests do not
    lean on ShapeRules."""
    cuts = [int(c) for c in key]
    broken = []
    if any(a == b for a, b in zip(cuts, cuts[1:])):
        broken.append("equal neighbours")
    if max(cuts.count(d) for d in set(cuts)) > 3:
        broken.append("a depth over three times")
    steps = [b - a for a, b in zip(cuts, cuts[1:])]
    if all(s >= 0 for s in steps) or all(s <= 0 for s in steps):
        broken.append("one way")
    if master and max(cuts) - min(cuts) < 6:
        broken.append("narrow master")
    return broken


def solved_keys(raw, names):
    return {n: (raw["keys"].get(n) or raw["control_keys"].get(n)) for n in names}


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_solved_keys_follow_the_shape_rules(unsolved, write_cfg, tmp_path, seed):
    proc, out = solve(write_cfg, unsolved, tmp_path, seed=seed)
    assert proc.returncode == 0, proc.stderr
    got = solved_keys(json.loads(out.read_text()), ["unit_master", "control_common"])
    assert shape_breaks(got["unit_master"], master=True) == []      # a master of the unit cores
    assert shape_breaks(got["control_common"]) == []
    assert "NOT SOLVED" not in proc.stdout


def test_a_whole_system_from_scratch_follows_the_shape_rules(clean_cfg, write_cfg, tmp_path):
    for section in SECTIONS:
        for name in clean_cfg.get(section, {}):
            if section != "retired_keys" and not name.startswith("unit:"):
                clean_cfg[section][name] = None
    proc, out = solve(write_cfg, clean_cfg, tmp_path)
    solved = json.loads(out.read_text())
    masters = {"general_master", "unit_master"}
    for name in ("general_master", "key_a", "key_b", "key_c", "unit_master", "control_common"):
        assert shape_breaks(solved_keys(solved, [name])[name], name in masters) == [], name


def test_pinning_solutions_with_keys_built_together_follow_the_shape_rules(
        pinned, write_cfg, tmp_path):
    for name in ("area_a", "area_b", "master_sub"):
        pinned["keys"][name] = None                                # one group of three keys
    pinned["keys"]["area_c"] = None
    proc, out = solve(write_cfg, pinned, tmp_path, seed=2)
    assert proc.returncode == 0, proc.stderr
    assert "that follow the shape rules" in proc.stdout
    solved = json.loads(out.read_text())
    for name in ("area_a", "area_b", "area_c", "master_sub", "unit_master"):
        masters = {"master_sub", "unit_master", "master_top"}
        assert shape_breaks(solved["keys"][name], name in masters) == [], name


# Recorded from the solver before the shape rules (D64, step 4), with every rule off: the
# seeded results of the "unsolved" system must not change when the rules are turned off.
BEFORE_THE_RULES = {1: ("8961038", "0165210"), 2: ("8961038", "0101630"),
                    3: ("8989410", "0105030")}


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_with_every_rule_off_seeded_results_are_what_they_were(
        unsolved, write_cfg, tmp_path, seed):
    unsolved["shape"] = RULES_OFF
    proc, out = solve(write_cfg, unsolved, tmp_path, seed=seed)
    assert proc.returncode == 0, proc.stderr
    solved = json.loads(out.read_text())
    assert (solved["keys"]["unit_master"], solved["control_keys"]["control_common"]) \
        == BEFORE_THE_RULES[seed]
    assert "shape rules" not in proc.stdout


def test_the_file_s_shape_settings_are_used(unsolved):
    free = {**unsolved, "pattern": None}          # alternating parity cannot have equal neighbours
    default = problem(free)
    pairs = problem({**free, "shape": {"max_run": 2}})
    rng = random.Random(4)
    runs = lambda cands: {max(len(list(g)) for _, g in itertools.groupby(c)) for c in cands}
    assert runs(default.shaped_candidates(rng, "key_c", 400)[0]) == {1}
    assert runs(pairs.shaped_candidates(rng, "key_c", 400)[0]) == {1, 2}


def test_the_span_rule_is_for_the_keys_that_are_masters(unsolved):
    prob = problem(unsolved)
    assert "unit_master" in prob.masters and "general_master" in prob.masters
    assert "key_a" not in prob.masters and "control_common" not in prob.masters
    rng = random.Random(1)
    assert all(max(c) - min(c) >= 6 for c in prob.shaped_candidates(rng, "unit_master", 200)[0])
    assert any(max(c) - min(c) < 6 for c in prob.shaped_candidates(rng, "key_a", 200)[0])


def test_neighbors_and_random_candidates_for_a_key_follow_the_shape_rules(unsolved):
    prob = problem({**unsolved, "pattern": None})
    start = prob.random_candidate(random.Random(2), "unit_master")
    assert shape_breaks("".join(map(str, start)), master=True) == []
    near = list(prob.neighbors(start, "unit_master"))
    assert near and all(not shape_breaks("".join(map(str, c)), master=True) for c in near)
    assert len(list(prob.neighbors(start))) > len(near)          # without a key: not filtered


def test_a_key_no_bitting_can_be_for_raises_with_the_rules_that_turned_draws_down(unsolved):
    unsolved["shape"] = {"min_total_variation": 30}              # only 0,5,0,5... reach it
    prob = problem(unsolved)
    with pytest.raises(solve_system.NoShapedBitting, match="max_same_depth"):
        prob.random_candidate(random.Random(1), "key_a")
    assert prob.shaped_candidates(random.Random(1), "key_a", 5)[0] == []


# Three pins and a master: no key of three cuts spans six unless it only goes one way.
@pytest.fixture
def three_pin_master():
    return {"pins": 3, "keys": {"a": "135", "m": None},
            "cores": [{"name": "x", "change": "a", "masters": ["m"]}]}


def test_a_key_with_no_bitting_that_follows_the_rules_is_left_null_and_said_so(
        three_pin_master, write_cfg, tmp_path):
    proc, out = solve(write_cfg, three_pin_master, tmp_path)
    assert proc.returncode == 0 and "Traceback" not in proc.stderr
    assert json.loads(out.read_text())["keys"]["m"] is None
    assert "m: NO bitting found that follows the shape rules (draws broke" in proc.stdout
    assert "master_min_span" in proc.stdout
    assert "The full check is skipped: m still has no bitting" in proc.stdout
    lines = proc.stdout.strip().splitlines()
    assert lines[-1].startswith("NOT SOLVED: no bitting for m follows the shape rules")
    assert "left null and running it again will not help" in lines[-1]
    assert sum(line.startswith("NOT SOLVED") for line in lines) == 2     # before Wrote, and last


def test_relaxing_the_rule_in_the_file_lets_the_same_system_solve(
        three_pin_master, write_cfg, tmp_path):
    three_pin_master["shape"] = {"master_min_span": 4}
    proc, out = solve(write_cfg, three_pin_master, tmp_path)
    got = json.loads(out.read_text())["keys"]["m"]
    assert got and len(got) == 3 and max(map(int, got)) - min(map(int, got)) >= 4
    assert "NOT SOLVED" not in proc.stdout and "skipped" not in proc.stdout


def test_pinned_keys_with_no_shaped_bitting_are_reported_as_that(pinned, write_cfg, tmp_path):
    """The bound allows 30, but only keys that alternate two depths reach it, and they use one
    of them four times."""
    pinned["keys"].update({"master_sub": "7305496", "area_a": "5721276", "area_b": "9565698",
                           "area_c": "3323872", "unit_master": "7587672"})
    pinned["keys"]["area_d"] = None
    pinned["shape"] = {"min_total_variation": 30}
    proc, out = solve(write_cfg, pinned, tmp_path)
    assert proc.returncode == 0 and "Traceback" not in proc.stderr
    assert "area_d: NO pinnable bitting follows the shape rules (draws broke" in proc.stdout
    assert json.loads(out.read_text())["keys"]["area_d"] is None
    assert proc.stdout.strip().splitlines()[-1].startswith(
        "NOT SOLVED: no bitting for area_d follows the shape rules")


def seven_decoded_units(pinned):
    """The system of test_with_few_pinnable_masters...: 24 pinnable unit masters, all of which
    end in two equal cuts and half of which span too few depths."""
    pinned["keys"].update(decoded_units(problem(pinned), 7))
    return pinned


def test_a_thin_pinnable_set_that_the_shape_rules_empty_is_reported_not_relaxed(
        pinned, write_cfg, tmp_path):
    seven_decoded_units(pinned)
    proc, out = solve(write_cfg, pinned, tmp_path, seed=3)
    assert proc.returncode == 0 and "Traceback" not in proc.stderr
    assert ("unit_master: 24 pinnable bittings with the known keys; scored all of them"
            not in proc.stdout)
    assert "unit_master: NO pinnable bitting follows the shape rules (draws broke max_run 24" \
        in proc.stdout
    assert json.loads(out.read_text())["keys"]["unit_master"] is None
    assert proc.stdout.strip().splitlines()[-1].startswith(
        "NOT SOLVED: no bitting for unit_master follows the shape rules")


def test_a_thin_pinnable_set_is_listed_and_filtered_whole(pinned, write_cfg, tmp_path):
    seven_decoded_units(pinned)
    pinned["shape"] = {"max_run": None}                  # leaves the depth and span rules
    prob = problem(pinned)
    pinnable, _ = prob.pinnable_set(["unit_master"])
    follow = sum(not prob.joint_broken(["unit_master"], c) for c in pinnable.enumerate())
    assert 0 < follow < pinnable.count == 24
    proc, out = solve(write_cfg, pinned, tmp_path, seed=3)
    assert (f"unit_master: 24 pinnable bittings with the known keys; {follow} follow the shape "
            f"rules; scored all of those") in proc.stdout
    got = json.loads(out.read_text())["keys"]["unit_master"]
    assert got and set(shape_breaks(got, master=True)) <= {"equal neighbours"}   # the rule left off
    assert "NOT SOLVED" not in proc.stdout


# -- review of #38: the middle band between easy rules and impossible ones -------------------

@pytest.fixture
def tight_rules(unsolved):
    """About 0.03% of MACS-valid bittings pass these, so a key exists but 300 draws of a
    summary would each need thousands of tries."""
    unsolved["shape"] = {"master_min_span": 9, "min_total_variation": 26}
    return unsolved


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_tight_but_satisfiable_rules_solve_and_do_not_crash_the_summary(
        tight_rules, write_cfg, tmp_path, seed):
    proc, out = solve(write_cfg, tight_rules, tmp_path, seed=seed)
    assert proc.returncode == 0 and "Traceback" not in proc.stderr, proc.stderr
    got = json.loads(out.read_text())["keys"]["unit_master"]
    cuts = [int(c) for c in got]
    assert max(cuts) - min(cuts) >= 9 and sum(abs(a - b) for a, b in zip(cuts, cuts[1:])) >= 26
    assert "NOT SOLVED" not in proc.stdout and proc.stdout.strip().endswith("OK")


def test_the_summary_is_left_out_when_no_typical_master_follows_the_rules(
        unsolved, capsys, monkeypatch):
    prob = problem(unsolved)
    prob.assign["unit_master"] = tuple(map(int, "8765432"))
    monkeypatch.setattr(solve_system.Problem, "shaped_candidates",
                        lambda self, rng, k, n: ([], {}))
    solve_system.unit_pair_summary(prob, random.Random(1), samples=5)
    assert capsys.readouterr().out == ""


def test_the_summary_reuses_the_typical_masters_it_found(unsolved, capsys, monkeypatch):
    prob = problem(unsolved)
    prob.assign["unit_master"] = tuple(map(int, "8765432"))
    few = [tuple(map(int, key)) for key in ("0549494", "9450505")]
    monkeypatch.setattr(solve_system.Problem, "shaped_candidates",
                        lambda self, rng, k, n: (few, {}))
    solve_system.unit_pair_summary(prob, random.Random(1), samples=7)
    assert "Unit-to-unit cross-operation by chance" in capsys.readouterr().out


def test_with_every_rule_off_the_summary_draws_what_it_always_drew(unsolved, monkeypatch):
    """The unfiltered draws, in the old order, so seeded output is unchanged (D64)."""
    unsolved["shape"] = RULES_OFF
    prob = problem(unsolved)
    prob.assign["unit_master"] = tuple(map(int, "8765432"))
    calls = []
    real = solve_system.Problem.random_candidate
    monkeypatch.setattr(solve_system.Problem, "random_candidate",
                        lambda self, rng, k=None: calls.append(k) or real(self, rng, k))
    monkeypatch.setattr(solve_system.Problem, "shaped_candidates",
                        lambda *a: pytest.fail("no filtering with every rule off"))
    solve_system.unit_pair_summary(prob, random.Random(1), samples=4)
    assert calls == [None] * 4


def test_a_group_blames_the_key_that_broke_the_rules_in_most_draws_not_one_that_did_by_chance(
        pinned, write_cfg, tmp_path):
    """unit_master has no pinnable bitting that follows the rules; control_b breaks one in
    about half the draws, as any random key does, and has plenty of shaped bittings."""
    seven_decoded_units(pinned)
    pinned["control_keys"]["control_b"] = None
    proc, out = solve(write_cfg, pinned, tmp_path, seed=3)
    assert proc.returncode == 0 and "Traceback" not in proc.stderr
    assert ("unit_master, control_b: NO pinnable combination follows the shape rules "
            "(draws broke unit_master: max_run 20,001") in proc.stdout
    lines = [line for line in proc.stdout.splitlines() if line.startswith("NOT SOLVED")]
    master = next(line for line in lines if "for unit_master" in line)
    waiting = next(line for line in lines if "for control_b" in line)
    assert "(draws broke max_run 20,001" in master and "built together" not in master
    assert ("(built together with unit_master, which has none: draws broke unit_master: "
            in waiting)
    assert "control_b:" not in waiting.split("which has none")[1]      # it is not blamed


def tallied(*draws):
    """The tally of draws, each a list of (key, rule) pairs, as the solver keeps it."""
    rejected = collections.Counter()
    for broken in draws:
        solve_system.tally_broken(rejected, broken)
    return rejected


def test_group_reasons_for_one_key_are_the_plain_tally():
    rejected = tallied([("k", "max_run"), ("k", "master_min_span")], [("k", "max_run")])
    summary, reasons = solve_system.group_reasons(["k"], rejected, 2)
    assert summary == reasons["k"] == "draws broke max_run 2, master_min_span 1"


def test_group_reasons_blame_only_keys_that_broke_a_rule_in_most_draws():
    draws = [[("a", "max_run"), ("b", "max_run")]] * 4 + [[("a", "forbid_monotone")]] * 5 \
        + [[("b", "max_same_depth")]]
    summary, reasons = solve_system.group_reasons(["a", "b"], tallied(*draws), 10)
    assert summary == "draws broke a: forbid_monotone 5, max_run 4"          # b: 5 of 10 draws
    assert reasons["a"] == "draws broke forbid_monotone 5, max_run 4"
    assert reasons["b"] == f"built together with a, which has none: {summary}"


def test_group_reasons_with_no_key_to_blame_give_the_group_the_whole_picture():
    draws = [[("a", "max_run")]] * 5 + [[("b", "max_run")]] * 5
    summary, reasons = solve_system.group_reasons(["a", "b"], tallied(*draws), 10)
    assert summary == "draws broke a: max_run 5; b: max_run 5"
    assert reasons == {"a": summary, "b": summary}


def test_group_reasons_when_the_draws_broke_nothing_say_none_could_be_drawn():
    summary, reasons = solve_system.group_reasons(["a", "b"], collections.Counter(), 0)
    assert summary == reasons["a"] == reasons["b"] == \
        "none of the bittings that could be drawn follows them"
