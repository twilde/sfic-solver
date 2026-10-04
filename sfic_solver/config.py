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

SECTIONS = ("keys", "retired_keys", "control_keys")
TOP_LEVEL_FIELDS = {"pins", "pattern", "max_step", "min_diff", "unit_prefix", "unit_count",
                    "close_check_units", "cores", *SECTIONS}
CORE_FIELDS = {"name", "change", "masters"}


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
    cores: List[dict]                           # {name, changes, masters, is_unit}
    warnings: List[str] = field(default_factory=list)


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
    unit_prefix = raw.get("unit_prefix", "unit:")
    if not isinstance(unit_prefix, str) or not unit_prefix:
        raise ConfigError(f"unit_prefix must be a non-empty string, got {unit_prefix!r}")
    unit_count = raw.get("unit_count")
    if unit_count is not None:
        unit_count = _whole_number(raw, "unit_count", None, 0)
    close_check_units = raw.get("close_check_units", False)
    if not isinstance(close_check_units, bool):
        raise ConfigError(f"close_check_units must be true or false, got {close_check_units!r}")

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

    def resolve_changes(where, change_specs):
        """The key names a core's `change` entry (a name, a wildcard or a list) selects."""
        if isinstance(change_specs, str):
            change_specs = [change_specs]
        if not change_specs:
            raise ConfigError(f"{where}: needs 'change' (a key name, a wildcard such as "
                              f"'{unit_prefix}*', or a list of those)")
        _string_list(change_specs, f"{where}: change")
        changes = []
        for pat in change_specs:
            matches = [n for n in keys if fnmatch.fnmatchcase(n, pat)]
            if not matches:
                raise ConfigError(f"{where}: change {pat!r} matches no key in keys{hint(pat)}")
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
        cores.append({
            "name": name,
            "changes": changes,
            "masters": masters,
            "is_unit": any(c.startswith(unit_prefix) for c in changes),
        })

    return Config(raw=raw, space=space, min_diff=min_diff, unit_prefix=unit_prefix,
                  unit_count=unit_count, close_check_units=close_check_units, keys=keys,
                  retired_keys=groups["retired_keys"], control_keys=groups["control_keys"],
                  cores=cores, warnings=warnings)


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
