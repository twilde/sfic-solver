"""check_system: whole-scheme checker (command-line behaviour)."""
import json
import re

import pytest

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


@pytest.fixture
def pinned():
    """A fresh copy of the fake system that opts in to pinning."""
    return json.loads((FIXTURES / "pinning.json").read_text())


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
    clean_cfg["min_diff"] = 7
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


# -- pinning (opt-in): core-pinning.md, step 4 --------------------------------------

def test_a_system_without_pinning_prints_no_pinning_section():
    assert "== Pinning" not in run_script("check_system", FIXTURES / "clean.json").stdout


def test_a_pinnable_system_passes_the_pinning_checks():
    proc = run_script("check_system", FIXTURES / "pinning.json")
    assert proc.returncode == 0, proc.stdout
    assert "== Pinning (A2)" in proc.stdout
    assert re.search(r"== Pinning \(A2\)[^\n]*==\nnone\n", proc.stdout)
    assert proc.stdout.strip().endswith("OK")


def test_flags_an_operating_gap_of_one_and_says_which_chamber(pinned, write_cfg):
    # master_sub's first cut moves to 6, one from area_a's 5, in the Area A cores.
    pinned["keys"]["master_sub"] = "6" + pinned["keys"]["master_sub"][1:]
    proc = check(write_cfg, pinned)
    assert proc.returncode == 1
    assert ("UNPINNABLE Area A cores [area_a], chamber 1: operating cuts 5 and 6 are 1 apart, "
            "so the pin between them would be 1, outside 2 to 19") in proc.stdout


def test_flags_a_control_cut_of_zero_beside_an_operating_cut_of_nine(pinned, write_cfg):
    # area_b's first cut is 9; a control key cut of 0 there cannot be pinned (the gap rule).
    pinned["control_keys"]["control_a"] = "0" + pinned["control_keys"]["control_a"][1:]
    proc = check(write_cfg, pinned)
    assert proc.returncode == 1
    assert ("UNPINNABLE Area B cores [area_b], chamber 1: control cut 0 puts the control "
            "boundary 1 above the highest operating cut 9") in proc.stdout
    assert "UNPINNABLE Unit cores" not in proc.stdout        # they use the other control key


def test_every_chamber_that_fails_is_listed(pinned, write_cfg):
    # master_sub moves to 6 in chamber 1 (beside area_a's 5) and to 3 in chamber 5 (beside 2).
    sub = pinned["keys"]["master_sub"]
    pinned["keys"]["master_sub"] = "6" + sub[1:4] + "3" + sub[5:]
    out = check(write_cfg, pinned).stdout
    chambers = [ln.split("]")[1].split(":")[0].strip(", ")
                for ln in out.splitlines() if ln.startswith("UNPINNABLE Area A cores [area_a]")]
    assert chambers == ["chamber 1", "chamber 5"]


def test_flags_a_known_key_that_operates_a_control_shear_line(pinned, write_cfg):
    pinned["keys"]["stray"] = pinned["control_keys"]["control_b"]
    proc = check(write_cfg, pinned)
    assert proc.returncode == 1
    assert "CONTROL   key stray operates the control shear line of Unit cores" in proc.stdout
    assert "DUPLICATE" in proc.stdout        # the same fact, seen as two keys with one bitting
    assert "operates the control shear line of Area A cores" not in proc.stdout


def test_a_core_is_not_flagged_for_its_own_control_key(pinned, write_cfg):
    out = check(write_cfg, pinned).stdout
    assert "CONTROL " not in out


def test_the_listing_of_unpinnable_cores_is_capped(pinned, write_cfg):
    # 40 unit keys whose first cut is 1 from unit_master's 7: each unit core fails in chamber 1.
    unit = pinned["keys"]["unit:101"]
    for number in range(40):
        pinned["keys"][f"unit:{200 + number}"] = f"8{number:02d}" + unit[3:]
    proc = check(write_cfg, pinned)
    out = proc.stdout
    assert len([ln for ln in out.splitlines() if ln.startswith("UNPINNABLE")]) == 30
    assert re.search(r"\.\.\. and \d+ more\n", out.split("== Pinning")[1])


# -- retired cores: the rules checked against the old pinning ----------------------

def test_consistent_retired_cores_are_reported_as_none(pinned):
    out = run_script("check_system", FIXTURES / "pinning.json").stdout
    assert re.search(r"== Retired cores[^\n]*==\nnone\n", out)


def test_a_decoded_key_that_could_not_have_shared_a_retired_core_is_a_warning(pinned, write_cfg):
    # The old master's first cut becomes 2, one from unit:101's 3. Retired keys are exempt
    # from the parity pattern, so this is only a question of whether the old cores were
    # pinnable, which these two keys together could not have been.
    pinned["retired_keys"]["old_master"] = "2" + pinned["retired_keys"]["old_master"][1:]
    proc = check(write_cfg, pinned)
    assert proc.returncode == 0, proc.stdout
    assert ("WARNING   Original cores [unit:101], chamber 1: operating cuts 2 and 3 are 1 apart"
            in proc.stdout)
    assert "Either the description of the old cores is wrong or the rules are too strict." \
        in proc.stdout
    assert proc.stdout.strip().endswith("OK, 1 warning(s)")


def test_the_old_control_key_is_checked_against_the_decoded_keys_too(pinned, write_cfg):
    # unit:104 has a 9 in chamber 1 and the old control key a 0 there.
    pinned["keys"]["unit:104"] = "95" + pinned["keys"]["unit:101"][2:]
    assert pinned["retired_keys"]["old_control"][0] == "0"
    out = check(write_cfg, pinned).stdout
    assert ("WARNING   Original cores [unit:104], chamber 1: control cut 0 puts the control "
            "boundary 1 above the highest operating cut 9") in out


def test_warnings_do_not_hide_problems_and_are_counted_beside_them(pinned, write_cfg):
    pinned["retired_keys"]["old_master"] = "2" + pinned["retired_keys"]["old_master"][1:]
    pinned["keys"]["master_sub"] = "6" + pinned["keys"]["master_sub"][1:]
    proc = check(write_cfg, pinned)
    assert proc.returncode == 1
    assert proc.stdout.strip().endswith("problem(s) flagged, 1 warning(s)")


def test_a_retired_wildcard_with_no_decoded_keys_yet_is_none(pinned, write_cfg):
    pinned["retired_cores"][0]["change"] = "flat:*"
    out = check(write_cfg, pinned).stdout
    assert re.search(r"== Retired cores[^\n]*==\nnone\n", out)


def test_there_is_no_retired_core_section_without_pinning(pinned, write_cfg):
    del pinned["pinning"]
    for core in pinned["cores"]:
        del core["control"]
    proc = check(write_cfg, pinned)
    assert "== Retired cores" not in proc.stdout
    assert "retired_cores is ignored" in proc.stderr


def test_the_retired_core_warnings_are_capped(pinned, write_cfg):
    unit = pinned["keys"]["unit:101"]
    for number in range(35):
        pinned["keys"][f"unit:{300 + number}"] = f"95{number:02d}" + unit[4:]
    out = check(write_cfg, pinned).stdout
    section = out.split("== Retired cores")[1].split("\n\n")[0]
    assert len([ln for ln in section.splitlines() if ln.startswith("WARNING")]) == 30
    assert re.search(r"\.\.\. and \d+ more\n", section)
