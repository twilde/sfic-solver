"""check_system: whole-scheme checker (command-line behaviour)."""
import json

from conftest import FIXTURES, ROOT, run_script


def mix(base, other, positions):
    """A bitting taking `other`'s cut at the given 0-based positions, `base`'s elsewhere.

    Such a key operates the core pinned with `base` as change key and `other`
    as master. Asserts the result is a legal key, so a planted conflict can't be
    flagged for the wrong reason.
    """
    cuts = [int(o) if i in positions else int(b) for i, (b, o) in enumerate(zip(base, other))]
    assert all(abs(a - b) <= 5 for a, b in zip(cuts, cuts[1:])), "planted key breaks MACS"
    return "".join(map(str, cuts))


def check(write_cfg, cfg):
    return run_script("check_system", write_cfg(cfg))


def test_clean_system_exits_zero():
    proc = run_script("check_system", FIXTURES / "clean.json")
    assert proc.returncode == 0, proc.stdout
    assert proc.stdout.strip().endswith("OK")
    assert "== Cross-operation among known keys ==\nnone" in proc.stdout


def test_reports_operating_set_sizes_and_residual_risk():
    out = run_script("check_system", FIXTURES / "clean.json").stdout
    assert "valid bittings in the whole key space: 31,448" in out
    assert "128 operating bittings, of which 2 intended" in out
    assert "Area C: 1 core(s), change" in out
    assert "== Residual risk from undecoded unit keys (3 of 5 decoded) ==" in out
    assert "Unit doors: 3 core(s), change + unit_master" in out


def test_no_residual_risk_section_without_unit_count(clean_cfg, write_cfg):
    del clean_cfg["unit_count"]
    proc = check(write_cfg, clean_cfg)
    assert proc.returncode == 0
    assert "Residual risk" not in proc.stdout


def test_flags_planted_unit_key_cross_operation(clean_cfg, write_cfg):
    # A unit key made of unit:101's cuts and the unit master's cuts operates
    # unit:101's core even though it is a different unit's key.
    keys = clean_cfg["keys"]
    keys["unit:104"] = mix(keys["unit:101"], keys["unit_master"], {1, 3, 5})
    proc = check(write_cfg, clean_cfg)
    assert proc.returncode == 1
    assert "CROSS     key unit:104 operates Unit doors [unit:101]" in proc.stdout


def test_flags_planted_retired_key_cross_operation(clean_cfg, write_cfg):
    # A retired key mixing a change key's cuts with a master's cuts operates
    # that area's core.
    clean_cfg["retired_keys"]["old_mix"] = mix(
        clean_cfg["keys"]["key_a"], clean_cfg["keys"]["general_master"], {1, 3, 5})
    proc = check(write_cfg, clean_cfg)
    assert proc.returncode == 1
    assert "CROSS     retired key old_mix operates Area A [key_a]" in proc.stdout


def test_control_keys_are_not_tested_for_operation(clean_cfg, write_cfg):
    clean_cfg["control_keys"]["control_mix"] = mix(
        clean_cfg["keys"]["key_a"], clean_cfg["keys"]["general_master"], {1, 3, 5})
    proc = check(write_cfg, clean_cfg)
    assert "CROSS" not in proc.stdout


def test_flags_duplicate_bittings_across_sections(clean_cfg, write_cfg):
    clean_cfg["retired_keys"]["old_master"] = clean_cfg["keys"]["key_c"]
    proc = check(write_cfg, clean_cfg)
    assert proc.returncode == 1
    assert "DUPLICATE key_c, old_master share bitting 6789876" in proc.stdout


def test_flags_wrong_parity(clean_cfg, write_cfg):
    clean_cfg["keys"]["key_c"] = "7789876"
    proc = check(write_cfg, clean_cfg)
    assert proc.returncode == 1
    assert "PARITY    key_c: wrong parity at pin(s) [1]" in proc.stdout


def test_flags_macs_violation(clean_cfg, write_cfg):
    clean_cfg["keys"]["key_c"] = "6789870"
    proc = check(write_cfg, clean_cfg)
    assert proc.returncode == 1
    assert "MACS      key_c: adjacent cuts too far apart" in proc.stdout


def test_control_keys_must_follow_parity(clean_cfg, write_cfg):
    clean_cfg["control_keys"]["control_common"] = "1101030"
    proc = check(write_cfg, clean_cfg)
    assert proc.returncode == 1
    assert "PARITY    control_common: wrong parity at pin(s) [1]" in proc.stdout


def test_control_keys_must_follow_macs(clean_cfg, write_cfg):
    clean_cfg["control_keys"]["control_common"] = "0901030"
    proc = check(write_cfg, clean_cfg)
    assert proc.returncode == 1
    assert "MACS      control_common: adjacent cuts too far apart" in proc.stdout


def test_retired_keys_are_exempt_from_parity_and_macs(clean_cfg, write_cfg):
    # Old keys are what they are; only their operation of new cores matters.
    clean_cfg["retired_keys"]["old_master"] = "1900000"
    proc = check(write_cfg, clean_cfg)
    assert "PARITY" not in proc.stdout and "MACS" not in proc.stdout


def test_flags_close_non_unit_keys(clean_cfg, write_cfg):
    clean_cfg["keys"]["key_c"] = "4567896"      # differs from key_b in one position
    proc = check(write_cfg, clean_cfg)
    assert proc.returncode == 1
    assert "CLOSE     key_b vs key_c: 1 position(s)" in proc.stdout


def test_unit_keys_skip_closeness_unless_requested(clean_cfg, write_cfg):
    # unit:105 differs from unit:101 in one position but does not operate its core.
    clean_cfg["keys"]["unit:105"] = "6543214"
    assert check(write_cfg, clean_cfg).returncode == 0
    clean_cfg["close_check_units"] = True
    proc = check(write_cfg, clean_cfg)
    assert proc.returncode == 1
    assert "CLOSE     unit:101 vs unit:105: 1 position(s)" in proc.stdout


def test_min_diff_is_configurable(clean_cfg, write_cfg):
    clean_cfg["min_diff"] = 8
    proc = check(write_cfg, clean_cfg)
    assert proc.returncode == 1 and "CLOSE" in proc.stdout


def test_null_bitting_is_rejected(clean_cfg, write_cfg):
    clean_cfg["keys"]["key_c"] = None
    proc = check(write_cfg, clean_cfg)
    assert proc.returncode != 0
    assert "key_c" in proc.stderr and "unknown" in proc.stderr


def test_usage_without_arguments():
    proc = run_script("check_system")
    assert proc.returncode == 1
    assert "Usage:" in proc.stderr


def test_example_file_is_a_clean_demo():
    proc = run_script("check_system", ROOT / "system.example.json")
    assert proc.returncode == 0, proc.stdout
    assert proc.stderr == ""
    assert "== Core operating sets" in proc.stdout
    assert proc.stdout.strip().endswith("OK")


def test_example_file_loads_as_json_with_expected_sections():
    cfg = json.loads((ROOT / "system.example.json").read_text())
    assert {"pattern", "keys", "cores"} <= set(cfg)
