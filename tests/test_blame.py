"""blame: the sentences that say which known keys leave a position no pinnable cut."""
from sfic_solver.blame import blame_position, key_list
from sfic_solver.pinning import A2

KNOWN = {"a": (3, 5), "b": (4, 5), "c": (1, 8), "ctl": (0, 0)}


def test_key_list_joins_names():
    assert key_list(["a"]) == "a" and key_list(["a", "b"]) == "a and b"
    assert key_list(["a", "b", "c"]) == "a, b and c"


def test_two_known_keys_one_apart_are_named_with_their_core_and_cuts():
    constraints = [("Area cores", "a", ["a", "b", "m"], "ctl")]
    (sentence,) = blame_position(A2, ["m"], constraints, KNOWN, 0)
    assert sentence == ("core 'Area cores' (change key a): known keys a (cut 3) and b (cut 4) "
                        "are 1 apart, so the pin between them would be 1, outside 2 to 19")


def test_keys_that_share_a_cut_are_named_together():
    known = {"a": (3,), "b": (3,), "c": (4,), "ctl": (0,)}
    constraints = [("X", "a", ["a", "b", "c", "m"], "ctl")]
    (sentence,) = blame_position(A2, ["m"], constraints, known, 0)
    assert "known keys a and b (cut 3) and c (cut 4) are 1 apart" in sentence


def test_a_conflict_repeated_by_several_cores_is_said_once_for_each_core():
    constraints = [("One", "a", ["a", "b", "m"], "ctl"), ("Two", "b", ["a", "b", "m"], "ctl")]
    sentences = blame_position(A2, ["m"], constraints, KNOWN, 0)
    assert [s.split(":")[0] for s in sentences] == ["core 'One' (change key a)",
                                                    "core 'Two' (change key b)"]


def test_a_known_control_cut_that_leaves_no_control_pin_is_named():
    known = {"a": (9,), "ctl": (0,)}                    # the control boundary is 1 above 9
    constraints = [("X", "a", ["a", "m"], "ctl")]
    (sentence,) = blame_position(A2, ["m"], constraints, known, 0)
    assert "with the known keys alone (a 9; control key ctl 0)" in sentence
    assert "control boundary 1 above the highest operating cut 9" in sentence


def test_an_unknown_control_key_is_not_blamed_on_the_known_keys():
    known = {"a": (3,)}
    constraints = [("X", "a", ["a", "m"], "ctl")]
    (sentence,) = blame_position(A2, ["m", "ctl"], constraints, known, 0)
    assert sentence.startswith("no cut for m, ctl can be pinned beside")


def test_when_no_core_conflicts_alone_the_known_cuts_are_listed():
    known = {f"u{d}": (d,) for d in range(10)}
    known["ctl"] = (5,)
    constraints = [("Units", f"u{d}", [f"u{d}", "m"], "ctl") for d in range(10)]
    (sentence,) = blame_position(A2, ["m"], constraints, known, 0)
    assert sentence == ("no cut for m can be pinned beside the known keys' cuts there (u0 0, "
                        "ctl 5, u1 1, u2 2, u3 3, u4 4, u5 5, u6 6, and 3 more)")
