"""Who the undecoded unit keys might be, and how many of them a core can take.

An undecoded unit key is not a uniformly random valid bitting once there is evidence
about it: the old cores of a rekeyed building had to be pinnable, so a unit key that
sat in one of them has, at every position, a cut for which that chamber could have
been pinned with the retired masters and control. This module turns the retired
cores of a system file into such a population (see model.Population) and counts, with
the pinner and nothing else, how much of a population can be pinned under a candidate
master and control key. See docs/designs/pinnable-solving.md.
"""
from .model import Population
from .pinning import PinningError, pin_chamber


def pinnable_cuts(system, cuts, others, control):
    """The cuts, out of `cuts`, that can be pinned in one chamber beside the cuts of the
    other operating keys (`others`) and the control key's cut."""
    pinnable = []
    for cut in cuts:
        try:
            pin_chamber(system, [cut, *others], control)
        except PinningError:
            continue
        pinnable.append(cut)
    return tuple(pinnable)


def pinnable_sets(system, base_sets, operating_keys, control):
    """Per position, the cuts of `base_sets` for which a further key could be pinned in a
    core of `operating_keys` and the control key `control` (bittings, as cut tuples)."""
    return tuple(pinnable_cuts(system, base_sets[p], [key[p] for key in operating_keys],
                               control[p])
                 for p in range(len(control)))


def retired_population(cfg):
    """The population of undecoded unit keys the retired cores describe, or None.

    None means no evidence: the system does not set pinning, or no retired core covers
    unit keys, and the caller keeps its uniform assumption. Several covering cores
    give the union of what each allows, since a unit key sat in one of them and which
    is not known. Raises ValueError if no bitting could have sat in any of them.
    """
    if not cfg.pinning:
        return None
    products = [pinnable_sets(cfg.pinning, cfg.space.digits,
                              [cfg.retired_keys[m] for m in core["masters"]],
                              cfg.retired_keys[core["control"]])
                for core in cfg.retired_cores if core["covers_units"]]
    if not products:
        return None
    population = Population.union_of(products)
    if cfg.space.population_size(population) == 0:
        raise ValueError("no valid bitting could have been pinned in the retired cores that "
                         "cover unit keys; the description of the old cores is wrong or "
                         "the rules are too strict")
    return population


def pinnable_fraction(space, population, system, operating_keys, control):
    """The share of the population that can be pinned in a core with these operating
    keys (a unit core's masters, perhaps none) and this control key."""
    sets = pinnable_sets(system, space.digits, operating_keys, control)
    return (space.population_size(population.restricted(sets))
            / space.population_size(population))


def false_key_share(space, population, options, intended_keys):
    """The share of the population, other than the intended keys themselves, that a core
    accepts. `options` is the per-position cuts the core accepts (model.options_for)."""
    accepted = space.population_operating(population, options)
    intended = sum(1 for key in {tuple(k) for k in intended_keys}
                   if space.population_contains(population, key))
    return max(accepted - intended, 0) / space.population_size(population)
