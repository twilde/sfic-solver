# Rules for the shape of a generated key

Status: Draft

This document proposes a small set of rules about what a key's cuts look like (not
which keys can be pinned together) and a way to apply them to the keys the tools
generate: the solver's unknown keys and `gen_bittings`' output. It is written before
any code, for the maintainer to accept or change. The numbers are measured on fake
systems by throwaway scripts that are not in the repository, and are illustrations
of scale, not claims about any real system.

## Why do this

The keys the solver and the generator produce often look poor: cuts of the same depth
side by side, a master that is shallow from end to end, one depth used four times. The
tools check three things about a bitting: the cut depths, the adjacent-cut limit
(MACS) and, if the file asks, parity. They have no opinion about its shape. Two
questions follow. What do locksmiths avoid, and does it matter here? And do the
tools' own choices make the problem worse than chance would?

## What the research found

Little of it is public, and the limits matter for how much weight to put on it.

- The Master Locksmiths Association of Australasia's skill standard lists the "foundational
  rules of design" by name: highest cut, deepest cut, odd/even (these three for the top
  master only), **same cuts**, **total variation**, **descending cuts**, and MACS.
  No public source I found defines the middle three or gives their thresholds; they
  appear to live in manufacturer and keying-software documentation.
- MACS is the one rule with published numbers (usually 7; the tools default to 5).
  It already is a `KeySpace` field.
- A search summary of top-master rules (not traced to a source page, so unverified) gave
  four: include at least one deepest and one shallowest cut, avoid a straight-line key,
  avoid a declining-step key, and avoid the deepest cut at the bow.
- Hold-and-vary practice expects every change key to hold the same number of cuts from
  its master. The solver currently rewards holding more (see below).

So the rule names are the industry's and the thresholds below are ours. They are
chosen to remove what looks wrong while costing as little of the key space as possible,
and each is a field the system file can change.

## What the tools do today

Both measurements are of the solver on fake systems with the keys blanked, compared with
every valid bitting (what a uniform draw would give).

**With a parity pattern** (`OOEOEOE`, the example system; 60 seeds, 420 keys):

| | solver | uniform |
|---|---|---|
| a pair of equal adjacent cuts | 64% | 26% |
| one depth used 4 or more times | 8.1% | 1.4% |
| mean total variation | 12.1 | 15.0 |

The top master was shallow (almost all 0 or 1) with its first two cuts equal in 60 of 60
runs, and the standalone core's key did the same in 59 of 60. Part of the cause is the
objective: the expected-conflict term counts the MACS-valid bittings a core accepts, and
that count is smaller when a change key shares a cut with its master in a chamber (a
mean of 20 with two or more shared cuts, 58 with fewer) or sits far from it (88 with one
position six or more steps apart, 43 with four). Holding cuts and spreading to extremes
both shrink it, and the solver follows. The equal adjacent cuts are not explained by this
(they did not change the count in my sample); I did not find their cause.

**With pinning and no pattern** (the pinning fixture with its pattern removed and six keys
blank; 40 seeds, 240 keys):

| | solver | uniform |
|---|---|---|
| a pair of equal adjacent cuts | 62% | 54% |
| three or more equal in a row | 8.8% | 6.6% |
| one depth used 4 or more times | 6.2% | 4.4% |
| depth range under 6 (max minus min) | 34% | not measured |

The bias is milder here, but the baseline is the point: **without a pattern, more than half
of all valid bittings have a pair of equal adjacent cuts**, so a generator that does
nothing about it produces one more often than not. Parity hides the problem (with
alternating parity, neighbours can never be equal), which is why it is a pinning-mode
problem first. The unit master came out very shallow (mean cut 1.2 against about 4.4 for
the others).

## The rules

A new object of rules, `ShapeRules`, in `model.py`, beside `KeySpace` and apart from it
(see "Why not part of KeySpace"). Each is a field of an optional `shape` object in the
system file, and `null` turns a rule off.

| Field | Default | A key breaks it when | Industry name |
|---|---|---|---|
| `max_run` | 1 | more than `max_run` equal cuts in a row (1 means no equal neighbours) | same cuts |
| `max_same_depth` | 3 | any depth appears more than this many times | (ours) |
| `forbid_monotone` | true | the cuts never go down, or never go up, along the key | descending cuts |
| `master_min_span` | 6 | (master keys only) the deepest cut minus the shallowest is under this | highest and deepest cut |
| `min_total_variation` | off | the sum of the differences between neighbours is under this | total variation |

The first four are on by default; the fifth is available and off. A "master" is a key that
is in the `masters` list of any core of the file, or, for `gen_bittings`, one named with
`--master`. Control keys are not masters. `master_min_span` defaults to 6, or to the number
of depths minus one if that is smaller, so a system with few depths still has a possible key.

What each costs, as the share of valid 7-pin bittings that pass (the first column is every
key but a master, the second a master):

| System | defaults, other keys | defaults, masters | `max_run` = 2 instead |
|---|---|---|---|
| no pattern (pinning) | 45.8% (1,387,478) | 33.1% (1,003,118) | 90.8% |
| `OOEOEOE` | 74.3% (21,083) | 53.2% (15,089) | 98.4% |
| `OEOEOEO` | 98.7% (31,027) | 71.5% (22,501) | 98.7% |

A solve needs a handful of keys, so even the strictest row leaves plenty. The first
version of the default, `max_run` = 2, was rejected because without a pattern it removes
only the 7% of bittings with three in a row and leaves the pairs, which is the complaint.

## Where they apply

- **Keys the tools generate.** Every unknown key the solver fills (keys, control keys,
  unit keys alike) and every bitting `gen_bittings` prints must pass, with the master rule
  for the keys that are masters.
- **Never silently relaxed.** If no candidate passes (a tight system, or a pinnable set
  with nothing in it that has the right shape), the tool says which rule left nothing, and
  the key stays unsolved under the existing "NOT SOLVED" line (D59). Turning a rule off is
  the system file's decision, not the tool's.
- **Keys that already exist** are not changed. `check_system` and `check_bittings` print
  the ones that break a rule as an advisory `SHAPE` line, with positions only and never
  values. It does not change the exit status or the count of warnings. Decoded unit
  keys and retired keys are left out (the vendor cut the first, and the second are history,
  as for parity and MACS in D11), and without a pattern about half of any real set breaks
  `max_run` = 1, so anything louder would be noise.

## Why not part of KeySpace

`KeySpace` is the rule set every real key must follow, and the exact counts (D4) are
dynamic programmes over it. Run lengths could be added to that programme at some cost, but
the depth count and total variation cannot: they depend on the whole key. More important,
the estimate's population is the undecoded unit keys that already exist, and those keys
were cut by someone else, not by these rules. Imposing the rules on that population would
make the residual-risk figures wrong. So the rules filter what the tools choose and leave
what the tools count alone. The risk figures are unchanged.

## What changes in each tool

- **Solver, one key at a time.** `random_candidate` and `neighbors` only produce keys that
  pass, so the search never walks through a bad key. The score is unchanged (D6).
- **Solver, pinning, keys built together** (D60). The pinnable set is built exactly and
  its draws are uniform; draws that fail the rules are thrown away and drawn again, up to a
  bound, and a set small enough to list is filtered whole. If the bound is reached with
  none, the group is reported as above.
- **`gen_bittings`.** Applies the defaults, with `--max-run`, `--max-same-depth`,
  `--min-variation` and `--master` to change them, and `--allow-monotone`.
- **`check_bittings`, `check_system`.** The advisory `SHAPE` lines.
- **System file.** `shape` is optional; a file without it gets the defaults, so seeded
  solver output changes for existing files. That is deliberate and the log entry says so (D6
  asks for a stated reason). An unknown field inside `shape` is an error, not a warning,
  since a mistyped rule name would otherwise leave the default on without anyone noticing.

Both ways of working are supported and tested: with a parity pattern, where `max_run` can
only matter between neighbours of the same parity, and with pinning and no pattern.

## Alternatives considered

- **A penalty in the score instead of a rule.** The weights are fixed (D6), and a penalty
  can be outweighed by a conflict term, which brings the bad key back. A rule is also easier
  to state and to test.
- **Fix the objective's bias instead.** The solver's liking for held and far-apart cuts is
  real and this does not remove it, only the shapes it produces. Changing what is
  scored needs its own measurement and its own decision, and the rules help it, since they
  keep any such change from surfacing as a degenerate key. I would revisit it after the
  rules are in and measured.
- **A limit on cuts held from a master.** `min_diff` already caps it (at 5 of 7 pins
  differing, two shared at most). Not added; revisit with the objective.
- **Making the rules part of the counted population.** Rejected above.
- **Thresholds from a manufacturer's manual.** Would be better and none is public; the
  fields exist so a system can set them when it has them.

## Plan

Separate commits, each with tests:

1. `ShapeRules` in `model.py`: the rules and their violations by position, tested
   against brute-force enumeration for the kept shares in the table above.
2. The `shape` field in the system file, with validation and its errors.
3. `gen_bittings` and `check_bittings`: the rules and their flags.
4. The solver, single key and joint, with a seeded test that no result breaks a rule and
   a range test (not exact figures) on the share of keys with equal neighbours, run with and
   without a pattern; and the "no candidate" report.
5. The advisory lines in `check_system`; README, `docs/design.md` and the file-format notes
   in the same commit as the behaviour they describe.

A refactor, if one is needed to share the check between the tools, is its own commit and
shows seeded output unchanged for files that turn every rule off.

## What cannot be known yet

- How many pinnable candidates survive the rules in a system with many known keys: a unit
  master that must also take a decoded unit's neighbours has a thin pinnable set already,
  and the first run on such a file will say whether `master_min_span` = 6 is too strict.
- Whether single-position moves still connect the valid keys once `max_run` = 1 applies
  without a pattern; I expect so (the share kept is 46%) and the search tests will show.
- Whether holding and spreading, the objective's bias, still produces odd keys once the
  rules are in. That is the measurement to make after step 4, with the same scripts.
