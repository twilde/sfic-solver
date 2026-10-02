"""Config validation: clear one-line errors instead of tracebacks."""
import json

import pytest

from conftest import FIXTURES, ROOT, run_script
from sfic_solver.config import ConfigError, load_config, parse_config


def fails(clean_cfg, mutate, *fragments, write_cfg, tool="check_system"):
    """Apply `mutate` to the clean config, run a tool, expect a clean error."""
    mutate(clean_cfg)
    proc = run_script(tool, write_cfg(clean_cfg))
    assert proc.returncode == 1, proc.stdout
    assert proc.stderr.startswith("error: "), proc.stderr
    assert "Traceback" not in proc.stderr
    for fragment in fragments:
        assert fragment in proc.stderr, proc.stderr


# -- keys and bittings --------------------------------------------------------

@pytest.mark.parametrize("bad", ["12345", "12345678", "01234x6", "", "²²²²²²²", 1234567, [1], True])
def test_bad_bitting_strings(clean_cfg, write_cfg, bad):
    fails(clean_cfg, lambda c: c["keys"].update(key_c=bad),
          "keys: 'key_c': bitting must be 7 digits", write_cfg=write_cfg)


def test_bad_bitting_in_other_sections_names_the_section(clean_cfg, write_cfg):
    fails(clean_cfg, lambda c: c["control_keys"].update(control_common="abc"),
          "control_keys: 'control_common'", write_cfg=write_cfg)


def test_null_bitting_in_checker(clean_cfg, write_cfg):
    fails(clean_cfg, lambda c: c["keys"].update(key_c=None),
          "'key_c': bitting is unknown (null)", write_cfg=write_cfg)


def test_null_retired_key_is_rejected_by_solver_too(clean_cfg, write_cfg):
    fails(clean_cfg, lambda c: c["retired_keys"].update(old_master=None),
          "retired keys must be known", tool="solve_system", write_cfg=write_cfg)


def test_duplicate_name_across_sections(clean_cfg, write_cfg):
    fails(clean_cfg, lambda c: c["control_keys"].update(key_a="1357913"),
          "key name 'key_a' appears in both keys and control_keys", write_cfg=write_cfg)


def test_duplicate_name_across_sections_is_caught_by_solver(clean_cfg, write_cfg):
    def mutate(c):
        c["keys"]["unit_master"] = None
        c["retired_keys"]["unit_master"] = "1357913"
    fails(clean_cfg, mutate, "appears in both keys and retired_keys",
          tool="solve_system", write_cfg=write_cfg)


def test_duplicate_name_within_one_section(tmp_path):
    path = tmp_path / "dup.json"
    path.write_text('{"keys": {"a": "0123456", "a": "2345678"}}')
    proc = run_script("check_system", path)
    assert proc.returncode == 1
    assert "duplicate entry 'a'" in proc.stderr and "Traceback" not in proc.stderr


# -- pattern and numbers ------------------------------------------------------

@pytest.mark.parametrize("bad", ["EOE", "EOEOEOEO", "EOEOEOX", "1010101", 7])
def test_bad_pattern(clean_cfg, write_cfg, bad):
    fails(clean_cfg, lambda c: c.update(pins=7, pattern=bad), "pattern must be",
          write_cfg=write_cfg)


def test_pattern_error_reports_length(clean_cfg, write_cfg):
    fails(clean_cfg, lambda c: c.update(pins=7, pattern="EOE"), "(3 characters)",
          write_cfg=write_cfg)


def test_lowercase_pattern_is_accepted(clean_cfg):
    assert parse_config({**clean_cfg, "pattern": "eoeoeoe"}).space.pattern == "EOEOEOE"


@pytest.mark.parametrize("field, bad", [("max_step", 0), ("max_step", "5"), ("max_step", 2.5),
                                        ("max_step", True), ("min_diff", -1),
                                        ("unit_count", "many"), ("unit_prefix", ""),
                                        ("close_check_units", "yes")])
def test_bad_scalar_settings(clean_cfg, write_cfg, field, bad):
    fails(clean_cfg, lambda c: c.update({field: bad}), field, write_cfg=write_cfg)


def test_unit_count_below_known_unit_keys(clean_cfg, write_cfg):
    fails(clean_cfg, lambda c: c.update(unit_count=2),
          "unit_count is 2 but 3 unit keys", write_cfg=write_cfg)


# -- cores --------------------------------------------------------------------

def test_unknown_master(clean_cfg, write_cfg):
    fails(clean_cfg, lambda c: c["cores"][0].update(masters=["general_mastr"]),
          "core 'Area A': unknown master 'general_mastr'", "did you mean 'general_master'",
          write_cfg=write_cfg)


def test_master_that_is_a_retired_key(clean_cfg, write_cfg):
    fails(clean_cfg, lambda c: c["cores"][0].update(masters=["old_master"]),
          "'old_master' is in retired_keys", write_cfg=write_cfg)


def test_unknown_change_key_and_wildcard(clean_cfg, write_cfg):
    fails(clean_cfg, lambda c: c["cores"][0].update(change="key_z"),
          "core 'Area A': change 'key_z' matches no key", write_cfg=write_cfg)


def test_wildcard_matching_nothing(clean_cfg, write_cfg):
    fails(clean_cfg, lambda c: c["cores"][3].update(change="apt:*"),
          "change 'apt:*' matches no key", write_cfg=write_cfg)


def test_duplicate_core_names(clean_cfg, write_cfg):
    fails(clean_cfg, lambda c: c["cores"][1].update(name="Area A"),
          "core 'Area A': core names must be unique", write_cfg=write_cfg)


def test_master_listed_twice(clean_cfg, write_cfg):
    fails(clean_cfg, lambda c: c["cores"][0].update(masters=["general_master"] * 2),
          "master 'general_master' is listed twice", write_cfg=write_cfg)


def test_master_equal_to_change_key(clean_cfg, write_cfg):
    fails(clean_cfg, lambda c: c["cores"][0].update(masters=["key_a"]),
          "'key_a' is both a change key and a master", write_cfg=write_cfg)


def test_change_key_matched_twice(clean_cfg, write_cfg):
    fails(clean_cfg, lambda c: c["cores"][3].update(change=["unit:*", "unit:101"]),
          "'unit:101' is matched by more than one change entry", write_cfg=write_cfg)


@pytest.mark.parametrize("mutate, fragment", [
    (lambda c: c["cores"][0].pop("name"), "cores[1] needs a non-empty 'name'"),
    (lambda c: c["cores"][0].pop("change"), "core 'Area A': needs 'change'"),
    (lambda c: c["cores"][0].update(masters="general_master"), "masters must be a list"),
    (lambda c: c["cores"].append("oops"), "cores[5] must be an object"),
    (lambda c: c.update(cores={"a": 1}), "cores must be a list"),
    (lambda c: c.update(keys=["a"]), "keys must be an object"),
])
def test_malformed_core_structure(clean_cfg, write_cfg, mutate, fragment):
    fails(clean_cfg, mutate, fragment, write_cfg=write_cfg)


# -- files --------------------------------------------------------------------

def test_missing_file():
    proc = run_script("check_system", "/nonexistent/system.json")
    assert proc.returncode == 1
    assert "cannot read file" in proc.stderr and "Traceback" not in proc.stderr


def test_invalid_json(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text('{"keys": ')
    proc = run_script("check_system", path)
    assert proc.returncode == 1
    assert "not valid JSON" in proc.stderr and "Traceback" not in proc.stderr


def test_top_level_must_be_an_object(tmp_path):
    path = tmp_path / "list.json"
    path.write_text("[1, 2]")
    assert run_script("check_system", path).returncode == 1


def test_load_config_raises_config_error(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{")
    with pytest.raises(ConfigError):
        load_config(path)


# -- warnings (misspelled optional fields) ------------------------------------

def test_misspelled_fields_warn_but_run(clean_cfg, write_cfg):
    clean_cfg["min_dff"] = 3
    clean_cfg["cores"][0]["master"] = ["general_master"]
    proc = run_script("check_system", write_cfg(clean_cfg))
    assert proc.returncode == 0
    assert "warning:" in proc.stderr and "'min_dff'" in proc.stderr
    assert "core 'Area A': unknown field 'master'" in proc.stderr


def test_underscore_fields_are_free_text(clean_cfg, write_cfg):
    clean_cfg["_notes"] = "anything"
    clean_cfg["cores"][0]["_note"] = "anything"
    proc = run_script("check_system", write_cfg(clean_cfg))
    assert proc.returncode == 0 and proc.stderr == ""


# -- valid files are unaffected ------------------------------------------------

def test_valid_files_load():
    for path in (FIXTURES / "clean.json", ROOT / "system.example.json"):
        cfg = load_config(path)
        assert cfg.warnings == [] and cfg.cores


def test_null_keys_allowed_for_the_solver(clean_cfg):
    clean_cfg["keys"]["unit_master"] = None
    cfg = parse_config(clean_cfg, allow_null=True)
    assert cfg.keys["unit_master"] is None
    with pytest.raises(ConfigError):
        parse_config(clean_cfg)
