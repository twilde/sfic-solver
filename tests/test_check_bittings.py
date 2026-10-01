"""check_bittings: standalone NAME=BITTING checker (command-line behaviour)."""
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
    proc = run_script("check_bittings", "--pattern", "EOE", "a=0123456")
    assert proc.returncode == 2
    assert "--pattern must be 7 characters of E/O" in proc.stderr


def test_single_key_has_no_closest_pair():
    proc = run_script("check_bittings", "a=0123456")
    assert proc.returncode == 0
    assert "closest pair" not in proc.stdout
