"""The shape-rule flags shared by gen_bittings and check_bittings."""
import argparse

import pytest

from sfic_solver import model
from sfic_solver.shape_args import add_shape_arguments, count_or_off, shape_rules


def parse(*argv, space=None):
    ap = argparse.ArgumentParser(prog="tool")
    add_shape_arguments(ap)
    args = ap.parse_args(argv)
    return shape_rules(ap, args, space or model.KeySpace(pins=7))


@pytest.mark.parametrize("text, value", [("1", 1), ("3", 3), ("off", None), ("OFF", None),
                                         ("none", None)])
def test_count_or_off(text, value):
    assert count_or_off(text) == value


@pytest.mark.parametrize("bad", ["0", "-2", "1.5", "two", "", "o"])
def test_count_or_off_refuses_everything_else(bad):
    with pytest.raises(argparse.ArgumentTypeError, match="at least 1, or 'off'"):
        count_or_off(bad)


def test_no_flags_gives_the_defaults_for_the_key_space():
    assert parse() == model.ShapeRules()
    assert parse(space=model.KeySpace(pins=5, max_step=1)).master_min_span == 4


def test_each_flag_sets_its_rule_and_leaves_the_others():
    assert parse("--max-run", "2") == model.ShapeRules(max_run=2)
    assert parse("--max-same-depth", "4") == model.ShapeRules(max_same_depth=4)
    assert parse("--min-variation", "10") == model.ShapeRules(min_total_variation=10)
    assert parse("--master-min-span", "4") == model.ShapeRules(master_min_span=4)
    assert parse("--allow-monotone") == model.ShapeRules(forbid_monotone=False)


def test_off_turns_a_rule_off_and_is_not_the_same_as_not_given():
    assert parse("--max-run", "off") == model.ShapeRules(max_run=None)
    assert parse("--master-min-span", "off").master_min_span is None
    assert parse("--min-variation", "off").min_total_variation is None


def test_a_rule_no_key_could_meet_is_a_usage_error_naming_the_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        parse("--master-min-span", "12")
    assert exc.value.code == 2
    assert "--master-min-span is 12 but no key can span more than 9" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        parse("--min-variation", "31")
    assert "--min-variation is 31" in capsys.readouterr().err
