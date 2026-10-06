"""The counting maths, checked against brute-force enumeration."""
import itertools
import random
from fractions import Fraction

import pytest

from sfic_solver import model


def macs(cuts, max_step):
    """Independent MACS check, so the tests don't lean on the code under test."""
    return all(abs(a - b) <= max_step for a, b in zip(cuts, cuts[1:]))


def parity_digits(pattern):
    return [[d for d in range(10) if d % 2 == (0 if c == "E" else 1)] for c in pattern]


def all_valid(pattern, max_step):
    """Every bitting with the right parity and MACS, by enumeration."""
    return [k for k in itertools.product(*parity_digits(pattern)) if macs(k, max_step)]


def test_total_valid_known_value():
    assert model.KeySpace(7, "OOEOEOE", 5).total_valid == 28_384


@pytest.mark.parametrize("pins", [1, 2, 3, 4, 5])
def test_total_valid_matches_brute_force(pins):
    rng = random.Random(1)
    for _ in range(30):
        pattern = "".join(rng.choice("EO") for _ in range(pins))
        max_step = rng.randint(1, 9)
        space = model.KeySpace(pins, pattern, max_step)
        assert space.total_valid == len(all_valid(pattern, max_step))


def test_total_valid_without_pattern_matches_brute_force():
    for max_step in (1, 3, 5, 9):
        brute = sum(1 for k in itertools.product(range(10), repeat=4) if macs(k, max_step))
        assert model.KeySpace(4, None, max_step).total_valid == brute


def test_operating_set_size_matches_brute_force():
    rng = random.Random(2)
    for i in range(150):
        # 1-3 options per pin (up to 3**7 combinations), a few cases with 4.
        top = 4 if i % 25 == 0 else 3
        options = [sorted(rng.sample(range(10), rng.randint(1, top))) for _ in range(7)]
        max_step = rng.randint(1, 9)
        brute = sum(1 for cuts in itertools.product(*options) if macs(cuts, max_step))
        assert model.KeySpace(max_step=max_step).operating_set_size(options) == brute, \
            (options, max_step)


def test_options_for_collects_distinct_cuts_per_pin():
    change = (1, 2, 3, 4, 5, 6, 7)
    master = (1, 9, 3, 0, 5, 0, 7)
    assert model.options_for(change, [master]) == [
        [1], [2, 9], [3], [0, 4], [5], [0, 6], [7]]


def test_operates_requires_every_pin_to_match_an_option():
    options = [[1], [2, 9], [3], [0, 4], [5], [0, 6], [7]]
    assert model.operates((1, 9, 3, 0, 5, 6, 7), options)
    assert not model.operates((1, 9, 3, 0, 5, 6, 8), options)


@pytest.mark.parametrize("pins, cases", [(3, 40), (4, 8)])
def test_pair_conflict_probability_matches_brute_force(pins, cases):
    rng = random.Random(3 + pins)
    for _ in range(cases):
        pattern = "".join(rng.choice("EO") for _ in range(pins))
        max_step = rng.randint(1, 9)
        space = model.KeySpace(pins, pattern, max_step)
        valid = all_valid(pattern, max_step)
        total = space.total_valid
        assert total == len(valid)
        masters = [rng.choice(valid) for _ in range(rng.randint(0, 3))]

        # B operates the core of A when each of B's cuts is A's cut or a master's.
        hits = sum(1 for a in valid for b in valid
                   if all(b[p] == a[p] or any(b[p] == m[p] for m in masters)
                          for p in range(pins)))
        expected = float(Fraction(hits, total ** 2))
        assert space.pair_conflict_probability(masters) == pytest.approx(expected, rel=1e-12)


def test_pair_conflict_probability_without_masters_is_one_over_count():
    # With no masters B must equal A, so the chance is 1 / count_valid.
    for pattern, max_step in [("EOEO", 5), ("EEOE", 2), ("OOOO", 9)]:
        space = model.KeySpace(4, pattern, max_step)
        p = space.pair_conflict_probability([])
        assert p == pytest.approx(1 / space.total_valid, rel=1e-12)


def test_pair_conflict_probability_full_pin_count_sanity():
    space = model.KeySpace(7, "OOEOEOE", 5)
    p0 = space.pair_conflict_probability([])
    assert p0 == pytest.approx(1 / space.total_valid, rel=1e-12)
    master = (0, 1, 2, 3, 4, 5, 6)
    assert space.pair_conflict_probability([master]) > p0


def test_distance_and_macs_and_parity_helpers():
    assert model.distance((1, 2, 3), (1, 5, 6)) == 2
    space = model.KeySpace(3, None, 5)
    assert space.macs_ok((0, 5, 0)) and not space.macs_ok((0, 6, 0))
    assert space.macs_violations((0, 6, 0)) == [1, 2]
    parity = model.KeySpace(7, "EOEOEOE")
    assert parity.parity_bad((0, 1, 2, 3, 4, 5, 6)) == []
    assert parity.parity_bad((1, 1, 2, 3, 4, 5, 7)) == [1, 7]


def test_without_a_pattern_no_cut_has_the_wrong_parity():
    assert model.KeySpace(3).parity_bad((0, 1, 2)) == []


def test_key_space_defaults_are_the_standard_seven_pin_rules():
    space = model.KeySpace()
    assert (space.pins, space.pattern, space.max_step, space.depths) == (7, None, 5, 10)


def test_key_space_rejects_a_pattern_of_the_wrong_length():
    with pytest.raises(ValueError, match="pattern has 3 characters but the key space has 7"):
        model.KeySpace(7, "EOE")


@pytest.mark.parametrize("kwargs, message", [
    ({"pins": 0}, "pins must be a whole number of at least 1"),
    ({"pins": -3}, "pins must be a whole number of at least 1"),
    ({"pins": 7.0}, "pins must be a whole number of at least 1"),
    ({"pins": True}, "pins must be a whole number of at least 1"),
    ({"max_step": 0}, "max_step must be a whole number of at least 1"),
    ({"depths": 0}, "depths must be a whole number of at least 1"),
    ({"depths": 11}, "depths must be at most 10"),
    ({"pins": 3, "pattern": "EOX"}, "pattern must be E or O for each pin"),
    ({"pins": 3, "pattern": "eoe"}, "pattern must be E or O for each pin"),
    ({"pins": 3, "pattern": ["E", "O", "E"]}, "pattern must be E or O for each pin"),
])
def test_key_space_refuses_nonsense_at_construction(kwargs, message):
    with pytest.raises(ValueError, match=message):
        model.KeySpace(**kwargs)


def test_key_space_accepts_the_smallest_sensible_values():
    space = model.KeySpace(pins=1, pattern="E", max_step=1, depths=1)
    assert space.digits == ((0,),) and space.total_valid == 1


def test_key_space_is_immutable_and_hashable():
    space = model.KeySpace(7, "OOEOEOE", 5)
    with pytest.raises(AttributeError):
        space.pins = 6
    assert space == model.KeySpace(7, "OOEOEOE", 5) and hash(space) == hash(model.KeySpace(7, "OOEOEOE", 5))


def test_is_bitting_checks_length_and_digits():
    space = model.KeySpace(3)
    assert space.is_bitting("012") and space.is_bitting("999")
    assert not space.is_bitting("01") and not space.is_bitting("0123")
    assert not space.is_bitting("01x") and not space.is_bitting(12) and not space.is_bitting(None)


@pytest.mark.parametrize("depths", [2, 5, 8, 10])
def test_depth_count_limits_digits_and_counts(depths):
    space = model.KeySpace(3, None, 2, depths)
    assert space.digits == (tuple(range(depths)),) * 3
    brute = sum(1 for k in itertools.product(range(depths), repeat=3) if macs(k, 2))
    assert space.total_valid == brute
    assert space.is_bitting(str(depths - 1) * 3)
    assert depths == 10 or not space.is_bitting(str(depths) * 3)


def test_digits_follow_the_parity_pattern():
    space = model.KeySpace(3, "EOE")
    assert space.digits == ((0, 2, 4, 6, 8), (1, 3, 5, 7, 9), (0, 2, 4, 6, 8))


# -- populations: sets of bittings counted exactly ----------------------------------

def random_sets(rng, pins, depths):
    return tuple(tuple(sorted(rng.sample(range(depths), rng.randint(1, depths))))
                 for _ in range(pins))


def members(sets, space):
    return {k for k in itertools.product(*sets) if space.macs_ok(k)}


@pytest.fixture
def small():
    return model.KeySpace(pins=3, pattern=None, max_step=3, depths=6)


def test_the_uniform_population_is_every_valid_bitting(small):
    uniform = small.uniform()
    assert small.population_size(uniform) == small.total_valid
    example = model.KeySpace(7, "OOEOEOE")
    assert example.population_size(example.uniform()) == 28384
    assert small.pair_conflict_probability([(1, 2, 3)], uniform) == \
        small.pair_conflict_probability([(1, 2, 3)])


def test_a_product_of_sets_is_counted_exactly(small):
    rng = random.Random(1)
    for _ in range(20):
        sets = random_sets(rng, 3, 6)
        assert small.population_size(model.Population.of_sets(sets)) == len(members(sets, small))


@pytest.mark.parametrize("count", [1, 2, 3, 5])
def test_a_union_of_products_is_counted_by_inclusion_and_exclusion(small, count):
    rng = random.Random(count)
    for _ in range(10):
        products = [random_sets(rng, 3, 6) for _ in range(count)]
        union = set().union(*(members(p, small) for p in products))
        population = model.Population.union_of(products)
        assert small.population_size(population) == len(union)
        for key in itertools.product(range(6), repeat=3):
            assert small.population_contains(population, key) == (key in union)


def test_operating_counts_are_taken_within_the_population(small):
    rng = random.Random(7)
    for _ in range(20):
        sets = random_sets(rng, 3, 6)
        options = model.options_for((1, 2, 3), [(4, 0, 5), (2, 2, 1)])
        population = model.Population.union_of([sets, random_sets(rng, 3, 6)])
        expected = sum(1 for k in itertools.product(range(6), repeat=3)
                       if small.population_contains(population, k) and model.operates(k, options))
        assert small.population_operating(population, options) == expected


def test_restricting_a_population_keeps_the_members_with_cuts_in_the_sets(small):
    rng = random.Random(3)
    population = model.Population.union_of([random_sets(rng, 3, 6), random_sets(rng, 3, 6)])
    sets = random_sets(rng, 3, 6)
    narrowed = population.restricted(sets)
    for key in itertools.product(range(6), repeat=3):
        inside = all(c in sets[i] for i, c in enumerate(key))
        assert narrowed.contains(key) == (population.contains(key) and inside)


def test_pair_conflicts_are_counted_within_the_population(small):
    rng = random.Random(11)
    masters = [(4, 0, 5), (2, 2, 1)]
    for _ in range(5):
        population = model.Population.union_of([random_sets(rng, 3, 6),
                                                random_sets(rng, 3, 6)])
        valid = [k for k in itertools.product(range(6), repeat=3)
                 if small.population_contains(population, k)]
        pairs = sum(1 for a in valid for b in valid
                    if all(b[p] == a[p] or b[p] in (m[p] for m in masters) for p in range(3)))
        assert small.pair_conflict_probability(masters, population) == \
            pytest.approx(pairs / len(valid) ** 2, abs=0, rel=1e-12)


# -- ShapeRules (docs/designs/key-shape-rules.md) ------------------------------------

def shape_oracle(cuts, rules, master):
    """Independent statement of each rule, by plain loops, for comparing with ShapeRules."""
    n = len(cuts)
    if rules.max_run is not None:
        run = 1
        for i in range(1, n):
            run = run + 1 if cuts[i] == cuts[i - 1] else 1
            if run > rules.max_run:
                return False
    if rules.max_same_depth is not None:
        if any(cuts.count(d) > rules.max_same_depth for d in set(cuts)):
            return False
    if rules.forbid_monotone and n >= 3:
        never_down = all(cuts[i] <= cuts[i + 1] for i in range(n - 1))
        never_up = all(cuts[i] >= cuts[i + 1] for i in range(n - 1))
        if never_down or never_up:
            return False
    if master and rules.master_min_span is not None:
        if max(cuts) - min(cuts) < rules.master_min_span:
            return False
    if rules.min_total_variation is not None:
        if sum(abs(cuts[i] - cuts[i + 1]) for i in range(n - 1)) < rules.min_total_variation:
            return False
    return True


def test_shape_defaults():
    rules = model.ShapeRules()
    assert (rules.max_run, rules.max_same_depth, rules.forbid_monotone) == (1, 3, True)
    assert (rules.master_min_span, rules.min_total_variation) == (6, None)
    assert model.SHAPE_RULES == tuple(
        f for f in model.ShapeRules.__dataclass_fields__)      # one name per field, in order


def test_a_clean_key_breaks_nothing():
    assert model.ShapeRules().violations((1, 6, 2, 8, 0, 7, 3), master=True) == []


def test_max_run_names_every_pin_of_an_over_long_run():
    rules = model.ShapeRules()
    assert rules.violations((4, 4, 1, 7, 7, 7, 2)) == [("max_run", (1, 2, 4, 5, 6))]
    assert model.ShapeRules(max_run=2).violations((4, 4, 1, 7, 7, 7, 2)) == [("max_run", (4, 5, 6))]
    assert model.ShapeRules(max_run=3).violations((4, 4, 1, 7, 7, 7, 2)) == []


def test_max_same_depth_names_the_pins_of_the_over_used_depth():
    rules = model.ShapeRules(max_run=None)
    assert rules.violations((1, 5, 1, 8, 1, 3, 1)) == [("max_same_depth", (1, 3, 5, 7))]
    assert rules.violations((1, 5, 1, 8, 1, 3, 2)) == []          # three times is allowed
    assert model.ShapeRules(max_run=None, max_same_depth=2).violations((1, 5, 1, 8, 1, 3, 2)) \
        == [("max_same_depth", (1, 3, 5))]


def test_monotone_means_never_down_or_never_up():
    rules = model.ShapeRules(max_run=None, max_same_depth=None)
    assert rules.violations((1, 3, 3, 6)) == [("forbid_monotone", ())]
    assert rules.violations((9, 7, 4, 4, 0)) == [("forbid_monotone", ())]
    assert rules.violations((5, 5, 5, 5)) == [("forbid_monotone", ())]      # flat is both
    assert rules.violations((1, 3, 2, 6)) == []


def test_monotone_needs_three_cuts():
    rules = model.ShapeRules(max_run=None, max_same_depth=None)
    assert rules.violations((2, 7)) == [] and rules.violations((4,)) == []


def test_the_span_rule_applies_to_masters_only():
    rules = model.ShapeRules(max_run=None, max_same_depth=None, forbid_monotone=False)
    narrow = (3, 5, 2, 6, 4, 3, 5)                                           # span 4
    assert rules.violations(narrow) == []
    assert rules.violations(narrow, master=True) == [("master_min_span", ())]
    assert rules.violations((0, 6, 1, 3), master=True) == []                 # span 6 is enough


def test_min_total_variation_is_off_by_default_and_counts_every_step():
    cuts = (4, 5, 4, 5, 4, 5, 4)                                             # variation 6
    rules = model.ShapeRules(max_run=None, max_same_depth=None, master_min_span=None)
    assert rules.violations(cuts) == []
    assert model.ShapeRules(max_run=None, max_same_depth=None, min_total_variation=7) \
        .violations(cuts) == [("min_total_variation", ())]
    assert model.ShapeRules(max_run=None, max_same_depth=None, min_total_variation=6) \
        .violations(cuts) == []


def test_violations_come_in_the_order_of_shape_rules():
    rules = model.ShapeRules(min_total_variation=99)
    names = [name for name, _ in rules.violations((2, 2, 2, 5, 5, 5, 5), master=True)]
    assert names == list(model.SHAPE_RULES)


def test_none_turns_each_rule_off():
    off = model.ShapeRules(max_run=None, max_same_depth=None, forbid_monotone=False,
                           master_min_span=None)
    assert off.violations((5, 5, 5, 5, 5, 5, 5), master=True) == []


def test_ok_agrees_with_violations():
    rules = model.ShapeRules()
    assert rules.ok((1, 6, 2, 8, 0, 7, 3), master=True)
    assert not rules.ok((1, 1, 2, 8, 0, 7, 3))


@pytest.mark.parametrize("field", ["max_run", "max_same_depth", "master_min_span",
                                   "min_total_variation"])
@pytest.mark.parametrize("bad", [0, -1, 1.5, "2", True])
def test_shape_counts_must_be_whole_numbers_of_at_least_one(field, bad):
    with pytest.raises(ValueError, match=field):
        model.ShapeRules(**{field: bad})


@pytest.mark.parametrize("bad", [None, 1, "yes"])
def test_forbid_monotone_must_be_a_boolean(bad):
    with pytest.raises(ValueError, match="forbid_monotone"):
        model.ShapeRules(forbid_monotone=bad)


def test_for_depths_caps_the_default_span_and_drops_it_when_there_is_none():
    assert model.ShapeRules.for_depths(10).master_min_span == 6
    assert model.ShapeRules.for_depths(7).master_min_span == 6
    assert model.ShapeRules.for_depths(5).master_min_span == 4
    assert model.ShapeRules.for_depths(1).master_min_span is None
    assert model.ShapeRules.for_depths(10, master_min_span=3).master_min_span == 3
    assert model.ShapeRules.for_depths(10, max_run=None).max_run is None


@pytest.mark.parametrize("rules", [
    model.ShapeRules(),
    model.ShapeRules(max_run=2, max_same_depth=2, min_total_variation=6),
    model.ShapeRules(max_run=None, max_same_depth=None, forbid_monotone=False,
                     master_min_span=4, min_total_variation=3),
])
def test_shape_rules_match_an_independent_check_on_every_five_cut_key(rules):
    for cuts in itertools.product(range(10), repeat=5):
        assert rules.ok(cuts) == shape_oracle(cuts, rules, False), cuts
    for cuts in itertools.islice(itertools.product(range(10), repeat=5), 0, None, 7):
        assert rules.ok(cuts, master=True) == shape_oracle(cuts, rules, True), cuts


def kept(pattern, rules, master):
    """How many MACS-valid 7-pin bittings of the pattern pass the shape rules."""
    return sum(rules.ok(k, master) for k in all_valid(pattern, 5))


@pytest.mark.parametrize("pattern, other_keys, masters, run_two", [
    ("OOEOEOE", 21_083, 15_089, 27_935),
    ("OEOEOEO", 31_027, 22_501, 31_027),
])
def test_shape_rules_keep_the_shares_the_design_document_gives(pattern, other_keys, masters,
                                                               run_two):
    total = len(all_valid(pattern, 5))
    assert kept(pattern, model.ShapeRules(), False) == other_keys
    assert kept(pattern, model.ShapeRules(), True) == masters
    assert kept(pattern, model.ShapeRules(max_run=2), False) == run_two
    assert round(100 * other_keys / total, 1) == {"OOEOEOE": 74.3, "OEOEOEO": 98.7}[pattern]


def test_shape_rules_without_a_pattern_match_the_oracle_on_a_sample():
    rng = random.Random(5)
    rules = model.ShapeRules(min_total_variation=10)
    for _ in range(20_000):
        cuts = tuple(rng.randrange(10) for _ in range(7))
        master = rng.random() < 0.5
        assert rules.ok(cuts, master) == shape_oracle(cuts, rules, master), cuts
