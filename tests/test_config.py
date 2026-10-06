"""Config validation: clear one-line errors instead of tracebacks."""
import json

import pytest

from conftest import FIXTURES, ROOT, run_script
from sfic_solver import model
from sfic_solver.config import ConfigError, _shape_rules, load_config, parse_config


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



# -- shape rules (docs/designs/key-shape-rules.md) ------------------------------------

def test_without_a_shape_object_the_rules_are_the_defaults(clean_cfg):
    assert "shape" not in clean_cfg
    assert parse_config(clean_cfg).shape == model.ShapeRules()


def test_an_empty_shape_object_is_the_defaults(clean_cfg):
    cfg = parse_config({**clean_cfg, "shape": {}})
    assert cfg.shape == model.ShapeRules() and cfg.warnings == []


def test_shape_settings_replace_the_defaults(clean_cfg):
    shape = {"max_run": 2, "max_same_depth": 4, "forbid_monotone": False,
             "master_min_span": 5, "min_total_variation": 12}
    assert parse_config({**clean_cfg, "shape": shape}).shape == model.ShapeRules(
        max_run=2, max_same_depth=4, forbid_monotone=False, master_min_span=5,
        min_total_variation=12)


def test_null_turns_each_rule_off(clean_cfg):
    shape = {name: None for name in model.SHAPE_RULES}
    assert parse_config({**clean_cfg, "shape": shape}).shape == model.ShapeRules(
        max_run=None, max_same_depth=None, forbid_monotone=False, master_min_span=None,
        min_total_variation=None)


def test_a_rule_left_out_keeps_its_default(clean_cfg):
    rules = parse_config({**clean_cfg, "shape": {"max_run": None}}).shape
    assert rules == model.ShapeRules(max_run=None)


def test_the_master_span_follows_the_depth_count():
    """A file cannot set the depth count yet (it is 10), so ask the helper with a small space."""
    few = model.KeySpace(pins=7, depths=5)
    assert _shape_rules({}, few).master_min_span == 4
    assert _shape_rules({"shape": {"master_min_span": 4}}, few).master_min_span == 4
    with pytest.raises(ConfigError, match="only from 0 to 4"):
        _shape_rules({"shape": {"master_min_span": 5}}, few)


def test_shape_is_not_an_unknown_field_and_underscore_notes_are_free_text(clean_cfg):
    cfg = parse_config({**clean_cfg, "shape": {"_comment": "free text", "max_run": 2}})
    assert cfg.warnings == [] and cfg.shape.max_run == 2


def test_shape_survives_a_solve(clean_cfg, write_cfg, tmp_path):
    clean_cfg["shape"] = {"max_run": 2}
    clean_cfg["keys"]["key_c"] = None
    out = tmp_path / "solved.json"
    proc = run_script("solve_system", write_cfg(clean_cfg), "--out", out, "--seed", 1)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(out.read_text())["shape"] == {"max_run": 2}


@pytest.mark.parametrize("bad", [[], "strict", 3, None, True])
def test_shape_must_be_an_object(clean_cfg, write_cfg, bad):
    fails(clean_cfg, lambda c: c.update(shape=bad), "shape must be an object", write_cfg=write_cfg)


def test_an_unknown_rule_is_an_error_with_a_hint(clean_cfg, write_cfg):
    fails(clean_cfg, lambda c: c.update(shape={"max_runs": 2}),
          "shape: unknown rule 'max_runs'", "did you mean 'max_run'?", "the rules are max_run",
          write_cfg=write_cfg)


@pytest.mark.parametrize("field", ["max_run", "max_same_depth", "master_min_span",
                                   "min_total_variation"])
@pytest.mark.parametrize("bad", [0, -1, 1.5, "2", True])
def test_bad_shape_counts(clean_cfg, write_cfg, field, bad):
    fails(clean_cfg, lambda c: c.update(shape={field: bad}), f"shape: {field} must be",
          "null in a system file", write_cfg=write_cfg)


@pytest.mark.parametrize("bad", ["yes", 1, 0])
def test_bad_forbid_monotone(clean_cfg, write_cfg, bad):
    fails(clean_cfg, lambda c: c.update(shape={"forbid_monotone": bad}),
          "shape: forbid_monotone must be true or false", write_cfg=write_cfg)


def test_a_master_span_wider_than_the_cuts_is_rejected(clean_cfg, write_cfg):
    fails(clean_cfg, lambda c: c.update(shape={"master_min_span": 10}),
          "shape: master_min_span is 10 but the cuts run only from 0 to 9",
          write_cfg=write_cfg)
    assert parse_config({**clean_cfg, "shape": {"master_min_span": 9}}).shape.master_min_span == 9


def test_a_total_variation_no_key_can_reach_is_rejected(clean_cfg, write_cfg):
    fails(clean_cfg, lambda c: c.update(shape={"min_total_variation": 31}),
          "shape: min_total_variation is 31", "more than 30", "max_step is 5",
          write_cfg=write_cfg)
    assert parse_config({**clean_cfg, "shape": {"min_total_variation": 30}}) \
        .shape.min_total_variation == 30


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


# -- pinning: the optional fields (core-pinning.md, step 4) -----------------------

PINNING = FIXTURES / "pinning.json"


@pytest.fixture
def pinned():
    """A fresh copy of the fake system that opts in to pinning (fixtures/pinning.json)."""
    return json.loads(PINNING.read_text())


def refused(raw, *fragments):
    with pytest.raises(ConfigError) as caught:
        parse_config(raw)
    for fragment in fragments:
        assert fragment in str(caught.value), str(caught.value)


def test_the_pinning_fixture_loads(pinned):
    cfg = load_config(PINNING)
    assert cfg.warnings == []
    assert cfg.pinning.name == "A2" and cfg.name == pinned["name"]
    assert {core["name"]: core["control"] for core in cfg.cores} == {
        "Area A cores": "control_a", "Area B cores": "control_a", "Area C cores": "control_a",
        "Sub-master cores": "control_a", "Standalone cores": "control_a",
        "Unit cores": "control_b"}
    assert cfg.retired_cores == [{
        "name": "Original cores", "changes": ["unit:101", "unit:102", "unit:103"],
        "masters": ["old_master"], "control": "old_control", "covers_units": True}]


def test_the_pinning_fixture_mirrors_the_example_system(pinned):
    """The fixture is the example with pinning switched on: it keeps every example key."""
    example = json.loads((ROOT / "system.example.json").read_text())
    for section in ("keys", "retired_keys", "control_keys"):
        for name, bitting in example[section].items():
            assert pinned[section][name] == bitting, (section, name)


def test_files_that_do_not_opt_in_are_read_as_before():
    for path in (FIXTURES / "clean.json", ROOT / "system.example.json"):
        cfg = load_config(path)
        assert cfg.pinning is None and cfg.name is None and cfg.retired_cores == []
        assert all(core["control"] is None for core in cfg.cores)


def test_the_pinning_system_name_ignores_case(pinned):
    pinned["pinning"] = "a2"
    assert parse_config(pinned).pinning.name == "A2"


@pytest.mark.parametrize("bad", ["A9", "", 2, None, ["A2"]])
def test_an_unknown_pinning_system_is_refused_and_the_known_ones_are_listed(pinned, bad):
    pinned["pinning"] = bad
    refused(pinned, "pinning: unknown pinning system", "known systems: A2")


def test_a_pinning_system_with_another_depth_count_is_refused(pinned, monkeypatch):
    from dataclasses import replace
    from sfic_solver import pinning
    monkeypatch.setitem(pinning.SYSTEMS, "A8", replace(pinning.A2, name="A8", depths=8))
    pinned["pinning"] = "A8"
    refused(pinned, "pinning system A8 has 8 cut depths but the key space has 10")


@pytest.mark.parametrize("bad", ["", "  ", 5, ["x"]])
def test_the_system_name_must_be_text(pinned, bad):
    pinned["name"] = bad
    refused(pinned, "name must be a non-empty string")


def test_a_core_needs_a_control_key_when_pinning_is_set(pinned):
    del pinned["cores"][2]["control"]
    refused(pinned, "core 'Area C cores': needs 'control'", "since the system sets pinning")


def test_a_core_may_leave_out_its_control_key_without_pinning(pinned):
    del pinned["pinning"]
    del pinned["cores"][2]["control"]
    cfg = parse_config(pinned)
    assert cfg.cores[2]["control"] is None and cfg.cores[0]["control"] == "control_a"


@pytest.mark.parametrize("bad, hint", [
    ("control_z", ""),
    ("controla", "did you mean 'control_a'?"),
    ("master_top", "'master_top' is in keys, not control_keys"),
    (7, ""), (["control_a"], ""),
])
def test_a_core_control_must_name_a_control_key(pinned, bad, hint):
    pinned["cores"][0]["control"] = bad
    refused(pinned, f"core 'Area A cores': unknown control {bad!r}", hint,
            "must name an entry in control_keys")


def test_a_control_is_checked_even_when_pinning_is_off(pinned):
    del pinned["pinning"]
    pinned["cores"][0]["control"] = "nope"
    refused(pinned, "unknown control 'nope'")


def test_retired_cores_match_changes_among_keys_and_retired_keys(pinned):
    assert "old_area" in pinned["retired_keys"]             # from the example, via the fixture
    pinned["retired_cores"][0]["change"] = ["unit:*", "old_area"]
    cfg = parse_config(pinned)
    assert cfg.retired_cores[0]["changes"] == ["unit:101", "unit:102", "unit:103", "old_area"]


def test_a_retired_wildcard_may_match_nothing_but_a_name_may_not(pinned):
    pinned["retired_cores"][0]["change"] = "flat:*"       # no decoded keys yet: fine
    assert parse_config(pinned).retired_cores[0]["changes"] == []
    pinned["retired_cores"][0]["change"] = "unit:999"
    refused(pinned, "retired core 'Original cores': change 'unit:999' matches no key in "
                    "keys or retired_keys")


@pytest.mark.parametrize("mutate, fragments", [
    (lambda c: c.update(retired_cores={"name": "x"}), ["retired_cores must be a list"]),
    (lambda c: c.update(retired_cores=["x"]), ["retired_cores[1] must be an object"]),
    (lambda c: c["retired_cores"][0].pop("name"), ["retired_cores[1] needs a non-empty 'name'"]),
    (lambda c: c["retired_cores"].append(dict(c["retired_cores"][0])),
     ["retired core names must be unique"]),
    (lambda c: c["retired_cores"][0].pop("change"),
     ["retired core 'Original cores': needs 'change'"]),
    (lambda c: c["retired_cores"][0].update(masters=["master_top"]),
     ["unknown master 'master_top'", "'master_top' is in keys, not retired_keys"]),
    (lambda c: c["retired_cores"][0].update(masters=["old_master", "old_master"]),
     ["master 'old_master' is listed twice"]),
    (lambda c: c["retired_cores"][0].update(change=["old_master"]),
     ["'old_master' is both a change key and a master"]),
    (lambda c: c["retired_cores"][0].pop("control"),
     ["retired core 'Original cores': needs 'control', the name of an entry in retired_keys"]),
    (lambda c: c["retired_cores"][0].update(control="control_a"),
     ["'control_a' is in control_keys, not retired_keys"]),
])
def test_retired_core_errors(pinned, mutate, fragments):
    mutate(pinned)
    refused(pinned, *fragments)


def test_retired_cores_without_pinning_warn_that_they_are_ignored(pinned):
    del pinned["pinning"]
    for core in pinned["cores"]:
        core.pop("control")
    cfg = parse_config(pinned)
    assert "retired_cores is ignored, because the system does not set pinning" in cfg.warnings


def test_misspelled_retired_core_fields_warn(pinned):
    pinned["retired_cores"][0]["master"] = ["old_master"]
    assert "retired core 'Original cores': unknown field 'master' is ignored (misspelled?)" \
        in parse_config(pinned).warnings


@pytest.mark.parametrize("change, covers", [
    ("unit:*", True), (["unit:*"], True), (["old_area", "unit:1*"], True),
    ("unit:101", False), ("old_area", False), ("flat:*", False), (["unit:101", "old_area"], False),
])
def test_a_retired_core_covers_unit_keys_when_a_wildcard_starts_with_the_unit_prefix(
        pinned, change, covers):
    pinned["retired_cores"][0]["change"] = change
    assert parse_config(pinned).retired_cores[0]["covers_units"] is covers


def test_any_number_of_retired_cores_covering_units_is_accepted_by_the_loader(pinned):
    template = pinned["retired_cores"][0]
    pinned["retired_cores"] = [{**template, "name": f"Old {n}"} for n in range(8)]
    cfg = parse_config(pinned)         # the checker, not the loader, limits what it combines
    assert len(cfg.retired_cores) == 8 and all(c["covers_units"] for c in cfg.retired_cores)
