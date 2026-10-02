"""check_bittings: standalone NAME=BITTING checker (command-line behaviour)."""
import pytest

from conftest import run_script


def test_clean_set_exits_zero():
    proc = run_script("check_bittings", "--pattern", "EOEOEOE", "a=0123456", "b=2345678")
    assert proc.returncode == 0
    assert "closest pair: a vs b (7 positions)" in proc.stdout
    assert proc.stdout.strip().endswith("OK")


def test_flags_wrong_parity():
    proc = run_script("check_bittings", "--pattern", "EOEOEOE", "a=1123456", "b=2345678")
    assert proc.returncode == 1
    assert "PARITY  a: wrong parity at pin(s) [1]" in proc.stdout


def test_parity_is_only_checked_when_a_pattern_is_given():
    proc = run_script("check_bittings", "a=1123456", "b=2345678")
    assert proc.returncode == 0


def test_flags_macs_violation():
    proc = run_script("check_bittings", "a=0900000", "b=2345678")
    assert proc.returncode == 1
    assert "MACS    a: adjacent cuts too far apart after pin(s) [1, 2]" in proc.stdout


def test_max_step_option():
    assert run_script("check_bittings", "a=0900000", "--max-step", 9).returncode == 0


def test_flags_close_pairs_and_respects_min_diff():
    proc = run_script("check_bittings", "a=0123456", "b=0123450")
    assert proc.returncode == 1
    assert "CLOSE   a vs b: differ in 1 position(s)" in proc.stdout
    assert run_script("check_bittings", "--min-diff", 1, "a=0123456", "b=0123450").returncode == 0


def test_bare_bitting_is_used_as_its_own_name():
    proc = run_script("check_bittings", "0123456", "0123450")
    assert "CLOSE   0123456 vs 0123450" in proc.stdout


def test_bad_bitting_is_a_usage_error():
    proc = run_script("check_bittings", "a=123")
    assert proc.returncode == 2
    assert "must be 7 digits" in proc.stderr


def test_bad_pattern_is_a_usage_error():
    proc = run_script("check_bittings", "--pins", 7, "--pattern", "EOE", "a=0123456")
    assert proc.returncode == 2
    assert "--pattern must be 7 characters of E/O" in proc.stderr


def test_single_key_has_no_closest_pair():
    proc = run_script("check_bittings", "a=0123456")
    assert proc.returncode == 0
    assert "closest pair" not in proc.stdout


# -- pin count ---------------------------------------------------------------

def test_pin_count_is_taken_from_the_pattern():
    proc = run_script("check_bittings", "--pattern", "EOEO", "a=0123", "b=2345")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "closest pair: a vs b (4 positions)" in proc.stdout


def test_pins_option_sets_the_pin_count_without_a_pattern():
    proc = run_script("check_bittings", "--pins", 5, "a=01234", "b=23456")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "closest pair: a vs b (5 positions)" in proc.stdout


def test_pins_disagreeing_with_the_pattern_is_a_usage_error():
    proc = run_script("check_bittings", "--pins", 5, "--pattern", "EOEO", "a=01234")
    assert proc.returncode == 2
    assert "--pattern must be 5 characters of E/O" in proc.stderr


def test_wrong_length_bitting_suggests_pins():
    proc = run_script("check_bittings", "a=01234")
    assert proc.returncode == 2
    assert "must be 7 digits (set --pins if that is wrong)" in proc.stderr


def test_default_min_diff_is_capped_at_the_pin_count():
    # Two different 3-pin keys differing in 2 positions: the 5-position default
    # would flag every pair, so for 3 pins the default is 3 and only this pair is close.
    proc = run_script("check_bittings", "--pins", 3, "a=012", "b=017", "c=345")
    assert proc.returncode == 1
    assert "CLOSE   a vs b: differ in 1 position(s)" in proc.stdout
    assert "a vs c" not in proc.stdout


def test_min_diff_above_the_pin_count_is_a_usage_error():
    proc = run_script("check_bittings", "--pins", 3, "--min-diff", 4, "a=012")
    assert proc.returncode == 2
    assert "--min-diff 4 is more than the 3 pins" in proc.stderr


@pytest.mark.parametrize("max_step", [0, -1])
def test_max_step_must_be_positive(max_step):
    proc = run_script("check_bittings", "--max-step", max_step, "a=0123456")
    assert proc.returncode == 2
    assert "--max-step must be at least 1" in proc.stderr
    assert "Traceback" not in proc.stderr


@pytest.mark.parametrize("pins", [0, -1])
def test_pins_must_be_positive(pins):
    proc = run_script("check_bittings", "--pins", pins, "a=012")
    assert proc.returncode == 2
    assert "--pins must be at least 1" in proc.stderr
