"""gen_bittings: output must always satisfy parity, MACS and min-diff."""
import itertools
import random
import secrets

import pytest

from sfic_solver import gen_bittings, model
from conftest import call_main, run_script


def assert_valid(bitting, pattern, max_step):
    assert len(bitting) == 7 and bitting.isdigit(), bitting
    cuts = [int(c) for c in bitting]
    for cut, p in zip(cuts, pattern):
        assert cut % 2 == (0 if p == "E" else 1), (bitting, pattern)
    assert all(abs(a - b) <= max_step for a, b in zip(cuts, cuts[1:])), bitting


def distance(a, b):
    return sum(x != y for x, y in zip(a, b))


def test_generate_always_satisfies_parity_and_macs():
    rng = random.Random(10)
    for _ in range(300):
        pattern = "".join(rng.choice("EO") for _ in range(7))
        max_step = rng.randint(3, 9)
        cuts = gen_bittings.generate(model.KeySpace(7, pattern, max_step))
        assert_valid("".join(map(str, cuts)), pattern, max_step)


@pytest.mark.parametrize("seed", range(12))
def test_cli_output_satisfies_every_constraint(seed):
    rng = random.Random(seed)
    pattern = "".join(rng.choice("EO") for _ in range(7))
    max_step = rng.randint(4, 9)
    min_diff = rng.randint(3, 5)
    count = rng.randint(3, 8)
    avoid = [b for b in run_script("gen_bittings", pattern, "-n", 3,
                                   "--max-step", max_step).stdout.split()]

    proc = run_script("gen_bittings", pattern, "-n", count, "--max-step", max_step,
                      "--min-diff", min_diff, "--avoid", *avoid)
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout.split()
    assert len(out) == count
    for b in out:
        assert_valid(b, pattern, max_step)
    # min-diff holds against the avoid list AND among the generated bittings
    for b in out:
        for old in avoid:
            assert distance(b, old) >= min_diff
    for a, b in itertools.combinations(out, 2):
        assert distance(a, b) >= min_diff, (a, b)


def test_avoid_flag_can_be_repeated():
    proc = run_script("gen_bittings", "OOEOEOE", "-n", 2, "--avoid", "0123456",
                      "--avoid", "2345678", "--min-diff", 4)
    assert proc.returncode == 0
    for b in proc.stdout.split():
        assert distance(b, "0123456") >= 4 and distance(b, "2345678") >= 4


def test_output_is_in_generation_order_not_sorted(monkeypatch, capsys):
    # Deterministic randomness for this test only. With 20 bittings the chance
    # of already being in sorted order by accident is ~1 in 20!.
    monkeypatch.setattr(secrets, "choice", random.Random(1).choice)
    assert call_main(gen_bittings.main, ["OOEOEOE", "-n", "20", "--min-diff", "3"], monkeypatch) == 0
    out = capsys.readouterr().out.split()
    assert len(out) == 20
    assert out != sorted(out)


def test_uses_secrets_module_by_default(monkeypatch, capsys):
    calls = []
    real = random.Random(5).choice

    def recording_choice(seq):
        calls.append(1)
        return real(seq)

    monkeypatch.setattr(secrets, "choice", recording_choice)
    assert call_main(gen_bittings.main, ["OOEOEOE", "-n", "2"], monkeypatch) == 0
    assert calls, "gen_bittings must draw its randomness from the secrets module"


def test_impossible_constraints_exit_with_message(monkeypatch):
    # 200 bittings that all differ at every pin cannot exist; give up quickly.
    monkeypatch.setattr(gen_bittings, "MAX_ATTEMPTS", 50)
    with pytest.raises(SystemExit) as exc:
        gen_bittings.main(["OOEOEOE", "-n", "200", "--min-diff", "7"])
    assert "loosen the constraints" in str(exc.value.code)


def test_max_step_must_be_positive():
    proc = run_script("gen_bittings", "OOEOEOE", "--max-step", 0)
    assert proc.returncode == 2


def test_default_count_is_ten():
    proc = run_script("gen_bittings", "OOEOEOE")
    assert len(proc.stdout.split()) == 10


@pytest.mark.parametrize("args, message", [
    (["EOEEOOX"], "pattern must be 7 characters of E/O"),
    (["EOEEOOX1"], "pattern must be 8 characters of E/O"),
    (["  "], "pattern must have at least one E/O character"),
    (["EOE", "--avoid", "0123456"], "bitting must be 3 digits"),
    (["OOEOEOE", "--min-diff", "8"], "--min-diff 8 is more than the 7 pins"),
    (["OOEOEOE", "--avoid", "12345"], "bitting must be 7 digits"),
    (["OOEOEOE", "--avoid", "0123456", "01234x6"], "bitting must be 7 digits"),
])
def test_bad_arguments_are_usage_errors_not_tracebacks(args, message):
    proc = run_script("gen_bittings", *args)
    assert proc.returncode == 2
    assert proc.stderr.startswith("usage:")
    assert message in proc.stderr
    assert "Traceback" not in proc.stderr


# -- without a pattern (core-pinning.md, step 5b) ------------------------------------

def test_without_a_pattern_any_parity_is_allowed_and_macs_still_holds(monkeypatch, capsys):
    monkeypatch.setattr(secrets, "choice", random.Random(3).choice)
    assert call_main(gen_bittings.main, ["-n", "200", "--min-diff", "0"], monkeypatch) == 0
    keys = capsys.readouterr().out.split()
    assert len(keys) == 200
    for key in keys:
        assert len(key) == 7 and key.isdigit()
        cuts = [int(c) for c in key]
        assert all(abs(a - b) <= 5 for a, b in zip(cuts, cuts[1:])), key
    for position in range(7):                    # both parities turn up at every position
        assert {int(key[position]) % 2 for key in keys} == {0, 1}


def test_pins_gives_the_length_when_there_is_no_pattern():
    proc = run_script("gen_bittings", "--pins", 5, "-n", 20)
    assert proc.returncode == 0
    assert all(len(key) == 5 for key in proc.stdout.split()) and len(proc.stdout.split()) == 20


def test_the_default_without_a_pattern_is_seven_pins_and_ten_keys():
    proc = run_script("gen_bittings")
    assert proc.returncode == 0
    keys = proc.stdout.split()
    assert len(keys) == 10 and all(len(key) == 7 for key in keys)


def test_a_pattern_still_sets_the_length_and_agrees_with_pins():
    ok = run_script("gen_bittings", "OOEOEOE", "--pins", 7, "-n", 3)
    assert ok.returncode == 0 and all(len(key) == 7 for key in ok.stdout.split())


@pytest.mark.parametrize("args, message", [
    (["OOEOEOE", "--pins", "6"], "--pins 6 disagrees with the 7 pins of the pattern"),
    (["--pins", "0"], "--pins must be at least 1"),
    (["--pins", "5", "--avoid", "0123456"], "bitting must be 5 digits"),
    (["--pins", "5", "--min-diff", "6"], "--min-diff 6 is more than the 5 pins"),
])
def test_bad_pins_arguments_are_usage_errors(args, message):
    proc = run_script("gen_bittings", *args)
    assert proc.returncode == 2 and message in proc.stderr
    assert "Traceback" not in proc.stderr


def test_without_a_pattern_the_default_closeness_follows_the_pin_count():
    # Four pins: the default min-diff is 3, so no two of 5 keys are closer than 3 positions.
    proc = run_script("gen_bittings", "--pins", 4, "-n", 5)
    keys = proc.stdout.split()
    assert proc.returncode == 0 and len(keys) == 5
    for a, b in itertools.combinations(keys, 2):
        assert distance(a, b) >= 3
