"""The pin count is configurable: `pins` in a system file, or implied by the pattern."""
import json

import pytest

from conftest import FIXTURES, run_script
from sfic_solver import gen_bittings
from sfic_solver.config import ConfigError, parse_config

PINS = 5


def truncate(cfg, pins):
    """Cut a config down to its first `pins` pins (only fit for parsing, not for checking)."""
    cfg["pattern"] = cfg["pattern"][:pins]
    for section in ("keys", "retired_keys", "control_keys"):
        for name, bitting in cfg[section].items():
            cfg[section][name] = bitting[:pins]
    return cfg


@pytest.fixture
def small_cfg():
    """A fake, clean 5-pin system (fixtures/five_pin.json)."""
    return json.loads((FIXTURES / "five_pin.json").read_text())


# -- config ----------------------------------------------------------------

def test_pins_defaults_to_seven_without_pattern(clean_cfg):
    del clean_cfg["pattern"]
    assert parse_config(clean_cfg).pins == 7


def test_pins_is_taken_from_the_pattern(small_cfg):
    assert "pins" not in small_cfg
    assert parse_config(small_cfg).pins == PINS


def test_explicit_pins_without_pattern(small_cfg):
    del small_cfg["pattern"]
    small_cfg["pins"] = PINS
    assert parse_config(small_cfg).pins == PINS


def test_explicit_pins_agreeing_with_pattern(small_cfg):
    small_cfg["pins"] = PINS
    assert parse_config(small_cfg).pins == PINS


def test_pins_is_not_an_unknown_field(small_cfg):
    small_cfg["pins"] = PINS
    assert parse_config(small_cfg).warnings == []


def test_pins_disagreeing_with_pattern_is_an_error(small_cfg):
    small_cfg["pins"] = 6
    with pytest.raises(ConfigError, match="pattern must be 6 characters"):
        parse_config(small_cfg)


def test_bittings_of_the_wrong_length_name_the_pin_count(small_cfg):
    small_cfg["keys"]["key_c"] = "6789876"  # 7 digits in a 5-pin system
    with pytest.raises(ConfigError, match="keys: 'key_c': bitting must be 5 digits"):
        parse_config(small_cfg)


@pytest.mark.parametrize("bad", [0, -3, "5", 2.5, True, None, [5]])
def test_bad_pins_values(small_cfg, bad):
    small_cfg["pins"] = bad
    with pytest.raises(ConfigError, match="pins must be a whole number of at least 1"):
        parse_config(small_cfg)


def test_min_diff_defaults_to_five_or_the_pin_count_if_smaller(clean_cfg, small_cfg):
    del clean_cfg["min_diff"], small_cfg["min_diff"]
    assert parse_config(clean_cfg).min_diff == 5
    for pins, expected in [(5, 5), (4, 4), (2, 2)]:
        cfg = truncate(json.loads(json.dumps(small_cfg)), pins)
        assert parse_config(cfg).min_diff == expected


def test_min_diff_above_the_pin_count_is_an_error(small_cfg):
    small_cfg["min_diff"] = PINS + 1
    with pytest.raises(ConfigError, match=r"min_diff is 6 but keys have only 5 pins"):
        parse_config(small_cfg)


# -- check_system and solve_system --------------------------------------------

def test_checker_accepts_a_five_pin_system(small_cfg, write_cfg):
    proc = run_script("check_system", write_cfg(small_cfg))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "valid bittings in the whole key space: 1,691)" in proc.stdout
    assert proc.stdout.strip().endswith("OK")


def test_checker_flags_a_planted_cross_operation_in_a_five_pin_system(small_cfg, write_cfg):
    # key_a's cuts, but the master's cut at pin 3: operates the "Area A" core.
    base, master = small_cfg["keys"]["key_a"], small_cfg["keys"]["general_master"]
    small_cfg["keys"]["planted"] = base[:2] + master[2] + base[3:]
    proc = run_script("check_system", write_cfg(small_cfg))
    assert proc.returncode == 1
    assert "CROSS     key planted operates Area A" in proc.stdout


def test_checker_still_flags_parity_with_other_pin_counts(small_cfg, write_cfg):
    small_cfg["keys"]["key_c"] = "7" + small_cfg["keys"]["key_c"][1:]
    proc = run_script("check_system", write_cfg(small_cfg))
    assert proc.returncode == 1
    assert "PARITY    key_c: wrong parity at pin(s) [1]" in proc.stdout


def test_solver_fills_nulls_with_bittings_of_the_right_length(small_cfg, write_cfg, tmp_path):
    small_cfg["keys"]["unit_master"] = None
    out = tmp_path / "solved.json"
    proc = run_script("solve_system", write_cfg(small_cfg), "--out", out,
                      "--trials", 200, "--seed", 1)
    assert proc.returncode == 0, proc.stderr
    solved = json.loads(out.read_text())
    assert len(solved["keys"]["unit_master"]) == PINS
    assert solved["keys"]["unit_master"].isdigit()
    assert proc.stdout.strip().endswith("OK")


# -- gen_bittings ---------------------------------------------------------------

@pytest.mark.parametrize("pattern", ["E", "OE", "EOEOE", "OOEOEOEOEOEE"])
def test_generator_pin_count_follows_the_pattern(pattern):
    proc = run_script("gen_bittings", pattern, "-n", 5, "--min-diff", 1)
    assert proc.returncode == 0, proc.stderr
    bittings = proc.stdout.split()
    assert len(bittings) == 5
    for b in bittings:
        assert len(b) == len(pattern) and b.isdigit()
        assert all(int(c) % 2 == (0 if p == "E" else 1) for c, p in zip(b, pattern))


def test_generator_default_min_diff_is_capped_at_the_pin_count():
    # The usual default of 3 could never be met by 2-pin bittings.
    proc = run_script("gen_bittings", "OE", "-n", 4)
    assert proc.returncode == 0, proc.stderr
    assert len(proc.stdout.split()) == 4


def test_generator_avoid_bittings_must_match_the_pattern_length():
    proc = run_script("gen_bittings", "EOEOE", "--avoid", "0123456")
    assert proc.returncode == 2
    assert "bitting must be 5 digits" in proc.stderr


def test_parse_pattern_uses_the_pattern_length():
    assert gen_bittings.parse_pattern(" eoe ") == "EOE"
