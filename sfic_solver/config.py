"""Loading and validating a system JSON file (format: see README and system.example.json).

All problems with the file itself are reported as ConfigError with a message
naming the offending key or core, so the command-line tools can print one
clear line instead of a traceback.
"""
import difflib
import fnmatch
import json
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from . import model
from .pinning import PinningSystem, get_system

SECTIONS = ("keys", "retired_keys", "control_keys")
TOP_LEVEL_FIELDS = {"name", "pins", "pattern", "max_step", "min_diff", "unit_prefix",
                    "unit_count", "close_check_units", "pinning", "shape", "cores",
                    "retired_cores", *SECTIONS}
CORE_FIELDS = {"name", "change", "masters", "control"}
RETIRED_CORE_FIELDS = {"name", "change", "masters", "control"}


class ConfigError(ValueError):
    """The system file is malformed or inconsistent."""


@dataclass
class Config:
    raw: dict                                   # the file as loaded (solve_system writes it back)
    space: model.KeySpace                       # pins, pattern, max_step and depths
    min_diff: int
    unit_prefix: str
    unit_count: Optional[int]
    close_check_units: bool
    keys: Dict[str, Optional[Tuple[int, ...]]]
    retired_keys: Dict[str, Optional[Tuple[int, ...]]]
    control_keys: Dict[str, Optional[Tuple[int, ...]]]
    cores: List[dict]                           # {name, changes, masters, control, is_unit}
    warnings: List[str] = field(default_factory=list)
    name: Optional[str] = None                  # the key system's name, for charts
    pinning: Optional[PinningSystem] = None     # set only if the file opts in to pinning
    retired_cores: List[dict] = field(default_factory=list)   # {name, changes, masters, control,
                                                              #  covers_units}
    shape: model.ShapeRules = field(default_factory=model.ShapeRules)   # the file's `shape`


def _no_duplicate_keys(pairs):
    seen = {}
    for key, value in pairs:
        if key in seen:
            raise ConfigError(f"duplicate entry {key!r} in one JSON object "
                              f"(the later value would silently replace the earlier one)")
        seen[key] = value
    return seen


def _whole_number(raw, name, default, minimum):
    value = raw.get(name, default)
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ConfigError(f"{name} must be a whole number of at least {minimum}, got {value!r}")
    return value


def _string_list(value, what):
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ConfigError(f"{what} must be a list of key names, got {value!r}")
    return value


def _shape_rules(raw, space):
    """The ShapeRules for a file: the defaults for its depth count, with the settings of
    its optional `shape` object on top. A rule set to null is off. Every mistake raises
    ConfigError, including a rule that no key could meet, since a solve that needs one
    would otherwise end in NOT SOLVED with nothing wrong in the file to point at. The two
    bounds ignore the parity pattern, so they never reject a rule that some key could meet
    but may accept one that none can."""
    if "shape" not in raw:
        return model.ShapeRules.for_space(space)
    settings = raw["shape"]
    if not isinstance(settings, dict):
        raise ConfigError(f"shape must be an object of rule settings, got {settings!r}")
    for name in settings:
        if name not in model.SHAPE_RULES and not name.startswith("_"):
            close = difflib.get_close_matches(name, model.SHAPE_RULES, n=1)
            hint = f" (did you mean {close[0]!r}?)" if close else ""
            raise ConfigError(f"shape: unknown rule {name!r}{hint}; the rules are "
                              f"{', '.join(model.SHAPE_RULES)}")
    fields = {name: value for name, value in settings.items() if name in model.SHAPE_RULES}
    if fields.get("forbid_monotone", True) is None:
        fields["forbid_monotone"] = False
    try:
        rules = model.ShapeRules.for_space(space, **fields)
    except ValueError as err:
        raise ConfigError(f"shape: {err}") from None
    if rules.master_min_span is not None and rules.master_min_span > space.widest_span:
        raise ConfigError(f"shape: master_min_span is {rules.master_min_span} but no key can "
                          f"span more than {space.widest_span} ({space.pins} pins, cuts 0 to "
                          f"{space.depths - 1}, max_step is {space.max_step})")
    if (rules.min_total_variation is not None
            and rules.min_total_variation > space.most_variation):
        raise ConfigError(f"shape: min_total_variation is {rules.min_total_variation} but no "
                          f"key of {space.pins} pins can vary by more than "
                          f"{space.most_variation} (max_step is {space.max_step})")
    return rules


def parse_config(raw, allow_null=False):
    """Validate an already-parsed system description and return a Config.

    allow_null: permit null bittings (keys the solver should choose). Retired
    keys must always be known.
    """
    if not isinstance(raw, dict):
        raise ConfigError("the top level must be a JSON object")
    warnings = [f"unknown top-level field {name!r} is ignored (misspelled?)"
                for name in raw if name not in TOP_LEVEL_FIELDS and not name.startswith("_")]

    pattern = raw.get("pattern")
    if "pins" in raw:
        pins = _whole_number(raw, "pins", None, 1)
    elif pattern and isinstance(pattern, str):
        pins = len(pattern)
    else:
        pins = model.DEFAULT_PINS

    if pattern:
        if not isinstance(pattern, str):
            raise ConfigError(f"pattern must be a string of {pins} E/O characters, "
                              f"got {pattern!r}")
        try:
            pattern = model.normalize_pattern(pattern, pins)
        except ValueError:
            raise ConfigError(f"pattern must be {pins} characters of E/O "
                              f"(even/odd per pin), got {pattern!r} "
                              f"({len(pattern)} characters)") from None
    else:
        pattern = None

    max_step = _whole_number(raw, "max_step", model.DEFAULT_MAX_STEP, 1)
    space = model.KeySpace(pins=pins, pattern=pattern, max_step=max_step)
    min_diff = _whole_number(raw, "min_diff", model.default_min_diff(pins), 0)
    if min_diff > pins:
        raise ConfigError(f"min_diff is {min_diff} but keys have only {pins} pins, so no two "
                          f"keys could differ in that many positions")
    shape = _shape_rules(raw, space)
    unit_prefix = raw.get("unit_prefix", "unit:")
    if not isinstance(unit_prefix, str) or not unit_prefix:
        raise ConfigError(f"unit_prefix must be a non-empty string, got {unit_prefix!r}")
    unit_count = raw.get("unit_count")
    if unit_count is not None:
        unit_count = _whole_number(raw, "unit_count", None, 0)
    close_check_units = raw.get("close_check_units", False)
    if not isinstance(close_check_units, bool):
        raise ConfigError(f"close_check_units must be true or false, got {close_check_units!r}")

    system_name = raw.get("name")
    if system_name is not None and (not isinstance(system_name, str) or not system_name.strip()):
        raise ConfigError(f"name must be a non-empty string, got {system_name!r}")
    pinning_system = None
    if "pinning" in raw:
        try:
            pinning_system = get_system(raw["pinning"])
        except ValueError as err:
            raise ConfigError(f"pinning: {err}") from None
        if pinning_system.depths != space.depths:
            raise ConfigError(f"pinning system {pinning_system.name} has "
                              f"{pinning_system.depths} cut depths but the key space has "
                              f"{space.depths}")

    groups, owner = {}, {}
    for label in SECTIONS:
        section = raw.get(label, {})
        if not isinstance(section, dict):
            raise ConfigError(f"{label} must be an object mapping key names to bittings")
        items = {}
        for name, text in section.items():
            if name in owner:
                raise ConfigError(f"key name {name!r} appears in both {owner[name]} "
                                  f"and {label}; each name may be used only once")
            owner[name] = label
            if text is None:
                if label == "retired_keys":
                    raise ConfigError(f"{label}: {name!r}: retired keys must be known "
                                      f"(null is not allowed)")
                if not allow_null:
                    raise ConfigError(f"{label}: {name!r}: bitting is unknown (null); "
                                      f"fill it in or run solve_system.py")
                items[name] = None
            elif not space.is_bitting(text):
                raise ConfigError(f"{label}: {name!r}: bitting must be {pins} digits "
                                  f"(0-9), got {text!r}")
            else:
                items[name] = tuple(int(c) for c in text)
        groups[label] = items

    keys = groups["keys"]
    if unit_count is not None:
        known_units = sum(1 for n, c in keys.items() if n.startswith(unit_prefix) and c is not None)
        if unit_count < known_units:
            raise ConfigError(f"unit_count is {unit_count} but {known_units} unit keys "
                              f"({unit_prefix!r}...) have bittings")

    def hint(name):
        if name in owner and owner[name] != "keys":
            return f" ({name!r} is in {owner[name]}; only entries in keys can be pinned into cores)"
        close = difflib.get_close_matches(name, list(keys), n=1)
        return f" (did you mean {close[0]!r}?)" if close else ""

    def hint_for(name, section):
        """Where a name that is not in `section` probably belongs (name may be any JSON)."""
        if not isinstance(name, str):
            return ""
        if name in owner and owner[name] != section:
            return f" ({name!r} is in {owner[name]}, not {section})"
        close = difflib.get_close_matches(name, list(groups[section]), n=1)
        return f" (did you mean {close[0]!r}?)" if close else ""

    def resolve_changes(where, change_specs, pool=None, empty_wildcards_ok=False):
        """The key names a core's `change` entry (a name, a wildcard or a list) selects.

        pool is the dict of keys that may be chosen, `keys` unless given;
        empty_wildcards_ok lets a wildcard match nothing (a name still may not).
        """
        label = "keys" if pool is None else "keys or retired_keys"
        pool = keys if pool is None else pool
        if isinstance(change_specs, str):
            change_specs = [change_specs]
        if not change_specs:
            raise ConfigError(f"{where}: needs 'change' (a key name, a wildcard such as "
                              f"'{unit_prefix}*', or a list of those)")
        _string_list(change_specs, f"{where}: change")
        changes = []
        for pat in change_specs:
            matches = [n for n in pool if fnmatch.fnmatchcase(n, pat)]
            if not matches and not (empty_wildcards_ok and any(c in pat for c in "*?[")):
                raise ConfigError(f"{where}: change {pat!r} matches no key in {label}{hint(pat)}")
            for match in matches:
                if match in changes:
                    raise ConfigError(f"{where}: key {match!r} is matched by more than one "
                                      f"change entry")
                changes.append(match)
        return changes

    specs = raw.get("cores", [])
    if not isinstance(specs, list):
        raise ConfigError("cores must be a list of {name, change, masters} objects")
    cores, core_names = [], set()
    for index, spec in enumerate(specs, 1):
        if not isinstance(spec, dict):
            raise ConfigError(f"cores[{index}] must be an object with name, change and masters")
        name = spec.get("name")
        if not isinstance(name, str) or not name:
            raise ConfigError(f"cores[{index}] needs a non-empty 'name'")
        where = f"core {name!r}"
        if name in core_names:
            raise ConfigError(f"{where}: core names must be unique")
        core_names.add(name)
        warnings += [f"{where}: unknown field {f!r} is ignored (misspelled?)"
                     for f in spec if f not in CORE_FIELDS and not f.startswith("_")]

        changes = resolve_changes(where, spec.get("change"))

        masters = _string_list(spec.get("masters", []), f"{where}: masters")
        for pos, master in enumerate(masters):
            if master not in keys:
                raise ConfigError(f"{where}: unknown master {master!r}{hint(master)}")
            if master in masters[:pos]:
                raise ConfigError(f"{where}: master {master!r} is listed twice")
            if master in changes:
                raise ConfigError(f"{where}: {master!r} is both a change key and a master")
        control = spec.get("control")
        if control is None:
            if pinning_system:
                raise ConfigError(f"{where}: needs 'control' (the name of one of control_keys), "
                                  f"since the system sets pinning")
        elif not isinstance(control, str) or control not in groups["control_keys"]:
            raise ConfigError(f"{where}: unknown control {control!r}"
                              f"{hint_for(control, 'control_keys')}; it must name an entry "
                              f"in control_keys")
        cores.append({
            "name": name,
            "changes": changes,
            "masters": masters,
            "control": control,
            "is_unit": any(c.startswith(unit_prefix) for c in changes),
        })

    retired_specs = raw.get("retired_cores", [])
    if not isinstance(retired_specs, list):
        raise ConfigError("retired_cores must be a list of {name, change, masters, control} "
                          "objects")
    retired_cores, retired_names = [], set()
    for index, spec in enumerate(retired_specs, 1):
        if not isinstance(spec, dict):
            raise ConfigError(f"retired_cores[{index}] must be an object with name, change, "
                              f"masters and control")
        name = spec.get("name")
        if not isinstance(name, str) or not name:
            raise ConfigError(f"retired_cores[{index}] needs a non-empty 'name'")
        where = f"retired core {name!r}"
        if name in retired_names:
            raise ConfigError(f"{where}: retired core names must be unique")
        retired_names.add(name)
        warnings += [f"{where}: unknown field {f!r} is ignored (misspelled?)"
                     for f in spec if f not in RETIRED_CORE_FIELDS and not f.startswith("_")]
        changes = resolve_changes(where, spec.get("change"),
                                  pool={**keys, **groups["retired_keys"]},
                                  empty_wildcards_ok=True)
        patterns = [spec["change"]] if isinstance(spec["change"], str) else spec["change"]
        covers_units = any(pat.startswith(unit_prefix) and any(c in pat for c in "*?[")
                           for pat in patterns)
        masters = _string_list(spec.get("masters", []), f"{where}: masters")
        for pos, master in enumerate(masters):
            if master not in groups["retired_keys"]:
                raise ConfigError(f"{where}: unknown master {master!r}"
                                  f"{hint_for(master, 'retired_keys')} "
                                  f"(retired cores are pinned with entries of retired_keys)")
            if master in masters[:pos]:
                raise ConfigError(f"{where}: master {master!r} is listed twice")
            if master in changes:
                raise ConfigError(f"{where}: {master!r} is both a change key and a master")
        control = spec.get("control")
        if not isinstance(control, str) or control not in groups["retired_keys"]:
            raise ConfigError(f"{where}: needs 'control', the name of an entry in retired_keys"
                              f"{hint_for(control, 'retired_keys')}")
        retired_cores.append({"name": name, "changes": changes, "masters": masters,
                              "control": control, "covers_units": covers_units})
    if retired_cores and not pinning_system:
        warnings.append("retired_cores is ignored, because the system does not set pinning")

    return Config(raw=raw, space=space, min_diff=min_diff, unit_prefix=unit_prefix,
                  unit_count=unit_count, close_check_units=close_check_units, keys=keys,
                  retired_keys=groups["retired_keys"], control_keys=groups["control_keys"],
                  cores=cores, warnings=warnings, name=system_name, pinning=pinning_system,
                  retired_cores=retired_cores, shape=shape)


def load_config(path, allow_null=False):
    """Read and validate a system file; raise ConfigError on any problem."""
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError as err:
        raise ConfigError(f"cannot read file: {err.strerror or err}") from None
    try:
        raw = json.loads(text, object_pairs_hook=_no_duplicate_keys)
    except json.JSONDecodeError as err:
        raise ConfigError(f"not valid JSON: {err}") from None
    return parse_config(raw, allow_null)


def load_or_exit(path, allow_null=False):
    """load_config for command-line tools: one clear error line and exit status 1."""
    try:
        cfg = load_config(path, allow_null)
    except ConfigError as err:
        sys.exit(f"error: {path}: {err}")
    for message in cfg.warnings:
        print(f"warning: {path}: {message}", file=sys.stderr)
    return cfg
