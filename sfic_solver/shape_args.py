"""The command-line flags for the shape rules, shared by gen_bittings and check_bittings.

A flag that is not given leaves the rule at its default for the key space; a count flag
takes a whole number of at least 1, or `off` to turn the rule off
(docs/designs/key-shape-rules.md). The tool-specific flag that says which keys are masters
(`--master`) is not here, because the two tools mean different things by it.
"""
import argparse

from . import model


# The flag that sets each rule whose field name differs from it, for messages to the user.
FLAGS = {"master_min_span": "--master-min-span", "min_total_variation": "--min-variation"}


def count_or_off(text):
    """argparse type: a whole number of at least 1, or "off" (None) to turn a rule off."""
    if text.lower() in ("off", "none"):
        return None
    try:
        value = int(text)
    except ValueError:
        value = 0
    if value < 1:
        raise argparse.ArgumentTypeError(
            f"expected a whole number of at least 1, or 'off', got {text!r}")
    return value


def add_shape_arguments(ap):
    """Add the shape-rule flags to a parser. Flags not given are absent from the result
    (default=SUPPRESS), so `shape_rules` can tell "off" from "not given"."""
    group = ap.add_argument_group(
        "key shape rules", "each rule is on at its default unless a flag changes it; "
        "a number, or 'off' to turn the rule off")
    suppress = argparse.SUPPRESS
    group.add_argument("--max-run", type=count_or_off, metavar="N", default=suppress,
                       help=f"most equal cuts in a row (default {model.DEFAULT_MAX_RUN}: "
                            f"no equal neighbours)")
    group.add_argument("--max-same-depth", type=count_or_off, metavar="N", default=suppress,
                       help=f"most times one depth may appear in a key "
                            f"(default {model.DEFAULT_MAX_SAME_DEPTH})")
    group.add_argument("--min-variation", dest="min_total_variation", type=count_or_off,
                       metavar="N", default=suppress,
                       help="least total variation (the sum of the differences between "
                            "adjacent cuts); off by default")
    group.add_argument("--master-min-span", dest="master_min_span", type=count_or_off,
                       metavar="N", default=suppress,
                       help=f"least difference between a master's deepest and shallowest cut "
                            f"(default {model.DEFAULT_MASTER_MIN_SPAN}, or the widest a key "
                            f"can span if that is less)")
    group.add_argument("--allow-monotone", dest="forbid_monotone", action="store_false",
                       default=suppress,
                       help="allow keys whose cuts never go down, or never go up")


def shape_rules(ap, args, space):
    """The ShapeRules for the parsed flags and key space; a usage error (exit 2) if a rule
    could not be met by any key of the space."""
    fields = {name: getattr(args, name) for name in model.SHAPE_RULES if hasattr(args, name)}
    try:
        rules = model.ShapeRules.for_space(space, **fields)
    except ValueError as err:
        ap.error(str(err))
    problem = rules.unmeetable(space)
    if problem:
        for name, flag in FLAGS.items():
            problem = problem.replace(name, flag)
        ap.error(problem)
    return rules
