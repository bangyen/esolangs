r"""Contract tests every boolean generator must satisfy."""

import contextlib
import hashlib
import importlib
import re
from collections.abc import Callable

import pytest

import esolangs
import esolangs.tools.boolean as boolean
from esolangs.interpreters.io import ScriptedIO
from esolangs.registry import BY_BOOLEAN, LANGUAGES
from esolangs.tools.boolean.helpers import essential_inputs
from esolangs.vm import run_until_halt_or_cycle

# Every sweep here runs an.
# file is the execution gate --.
# leaves it out.
# per-param `slow` marks below.
pytestmark = pytest.mark.medium

# One constant table against.
# by *folding*, so the.
# that folds not at all;.
# counts but never catch a.
# interpreter on every table on.
# cost without adding detection.
# ``11111110`` were dropped for.
# .
# ``01101001`` is parity, the.
# single row, so nothing about.
_TABLES = ["00000000", "01101001"]


# Generators marked ``slow``.
# the construction ought to.
# in this sweep.
# acceptable, so an entry.
# it stops being noticed.
# .
# The set is empty.
# sweep's 18.0s, and left on.
# its straight runs one.
# against the one-second budget.
# full ledger of what entered.
# behind each.
_SEARCHING_GENERATORS_REGRESSED: frozenset[str] = frozenset()

# Naming the languages rather.
# deliberate: a wall-clock.
# the selected test set depend.
# silently cover less than the.
# a generator's cost changes.
_SEARCHING_GENERATORS: frozenset[str] = frozenset()

# The same one-second rule,.
# the ``_*_ordered`` builder.
# inputs, so a generator that.
# .
# ``ztoalc_l`` was this set's.
# test_reordering_never_grows_a_.
# above.
# lookup whose length is.
# and this set.
# under budget, which is why.
# .
# A generator can be cheap in.
# set is maintained.
_SLOW_REORDERING_GENERATORS: frozenset[str] = frozenset()


def _input_reading_generators() -> list[object]:
    r"""Every boolean generator whose language actually reads input."""
    found = []
    for name in sorted(boolean.__all__):
        fn = getattr(boolean, name, None)
        lang = BY_BOOLEAN.get(name)
        if not callable(fn) or lang is None or lang.interpreter is None:
            continue
        try:
            run = importlib.import_module(
                f"esolangs.interpreters.{lang.interpreter}"
            ).run
        except Exception:  # pragma: no cover - interpreter lives outside the pkg
            continue
        if name in _SEARCHING_GENERATORS | _SEARCHING_GENERATORS_REGRESSED:
            found.append(pytest.param(name, (fn, lang, run), marks=pytest.mark.slow))
        else:
            found.append((name, (fn, lang, run)))
    return found


def _reads(entry: tuple, table: str) -> int:
    r"""Run the generated program and report how many inputs it consumed."""
    fn, lang, _run = entry
    try:
        program = str(fn(table))
    except ValueError:
        # A generator that does not.
        # program that does not exist.
        # caller into its "does not.
        # coverage gap, which is not.
        # case in hand: it derives.
        # parity table has three.
        return 0
    io = ScriptedIO("0\n" * 8)
    source = program.splitlines() if lang.split else program
    module = importlib.import_module("esolangs.interpreters." + lang.interpreter)
    machine_cls = getattr(module, "_Machine")  # noqa: B009
    # Every interpreter names its.
    # the same count for every.
    # for the three that spelled.
    # run rather than a stepped.
    # A program may halt through.
    # read count up to that point.
    with contextlib.suppress(Exception, SystemExit):
        of = getattr(machine_cls, "of", None)
        build = of if callable(of) else machine_cls
        run_until_halt_or_cycle(build(source, io))
    return io.position()


@pytest.mark.parametrize(
    ("name", "entry"),
    _input_reading_generators(),
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_every_table_reads_the_same_number_of_inputs(name: str, entry: tuple) -> None:
    r"""A generator reads its ``n`` inputs whatever the truth table says."""
    counts = {table: _reads(entry, table) for table in _TABLES}
    baseline = counts["01101001"]
    if baseline == 0:
        pytest.skip(f"{name} does not read input in this harness")
    assert set(counts.values()) == {baseline}, (
        f"{name} reads a different number of inputs depending on the table: "
        f"{counts} -- a constant table must still consume all {baseline}"
    )


def _exported_generators() -> dict[str, str]:
    r"""Every boolean generator the package exports, mapped to its language."""
    by_id = {lang.id: name for name, lang in LANGUAGES.items()}
    squashed = {lang.id.replace("_", ""): name for name, lang in LANGUAGES.items()}
    found = {}
    for fn in boolean.__all__:
        if fn in ("BOOLEAN", "instantiate") or not callable(getattr(boolean, fn, None)):
            continue
        display = (
            by_id.get(fn)
            or squashed.get(fn.replace("_", ""))
            or (BY_BOOLEAN[fn].name if fn in BY_BOOLEAN else None)
        )
        if display is not None:
            found[fn] = display
    return found


def test_boolean_set_lists_exactly_the_exported_generators() -> None:
    r"""``BOOLEAN`` and the package's exports name the same languages."""
    exported = _exported_generators()
    missing = {d for d in exported.values() if d not in boolean.BOOLEAN}
    assert not missing, (
        f"these languages export a boolean generator but are absent from "
        f"BOOLEAN, so describe() reports boolean_generator=False for them: "
        f"{sorted(missing)} -- add them to BOOLEAN in tools/boolean/__init__.py"
    )
    stale = boolean.BOOLEAN - set(exported.values())
    assert not stale, (
        f"BOOLEAN names these languages but the package exports no generator "
        f"resolving to them: {sorted(stale)} -- remove them from BOOLEAN, or "
        f"export the generator from tools/boolean/__init__.py"
    )


# The tree generators that pick.
# builder that emits one fixed.
def _reordering_generators() -> list[object]:
    from esolangs.tools.boolean.helpers import _decision_tree_program
    from esolangs.tools.boolean.other import (
        _between_ordered,
        _forbin_ordered,
        _myscript_ordered,
        _nevermind_ordered,
    )
    from esolangs.tools.boolean.parameterized import (
        _bitdeque_ordered,
        _lamfunc_ordered,
        _ram0_ordered,
    )
    from esolangs.tools.boolean.tape import (
        _ASCII_ZERO,
        _basicfuck_ordered,
        _circlefuck_ordered,
        _jaune_ordered,
    )

    entries: list[tuple[str, object, object]] = [
        (
            "brainfuck",
            boolean.brainfuck,
            lambda t, p: _decision_tree_program(t, ">", "<", p),
        ),
        (
            "dimensional",
            boolean.dimensional,
            lambda t, p: _decision_tree_program(t, ">0", "<0", p),
        ),
        ("ram0", boolean.ram0, _ram0_ordered),
        ("between", boolean.between, _between_ordered),
        ("lamfunc", boolean.lamfunc, _lamfunc_ordered),
        ("bitdeque", boolean.bitdeque, _bitdeque_ordered),
        ("myscript", boolean.myscript, _myscript_ordered),
        ("nevermind", boolean.nevermind, _nevermind_ordered),
        ("basicfuck", boolean.basicfuck, _basicfuck_ordered),
        (
            "circlefuck",
            boolean.circlefuck,
            # The byte-valued builder.
            # so the contract's.
            # circlefuck() itself lifts it.
            lambda t, p: _circlefuck_ordered([_ASCII_ZERO + int(b) for b in t], p),
        ),
        ("forbin", boolean.forbin, _forbin_ordered),
        ("jaune", boolean.jaune, _jaune_ordered),
    ]
    return [
        (
            pytest.param(name, fn, ordered, marks=pytest.mark.slow)
            if name in _SLOW_REORDERING_GENERATORS
            else (name, fn, ordered)
        )
        for name, fn, ordered in entries
    ]


@pytest.mark.parametrize(("name", "fn", "ordered"), _reordering_generators())
def test_reordering_never_grows_a_program(
    name: str, fn: object, ordered: object
) -> None:
    r"""Choosing the input order can only shrink the emitted program."""
    for n in (1, 2, 3):
        for value in range(2 ** (2**n)):
            table = bin(value)[2:].zfill(2**n)
            baseline = ordered(table, tuple(range(n)))
            # A searching generator returns.
            # (ZTOALC L); there is no.
            # order that *did* place is an.
            if not baseline:
                continue
            assert len(fn(table)) <= len(baseline), f"{name} grew on {table}"


@pytest.mark.parametrize(("name", "fn", "ordered"), _reordering_generators())
def test_reordering_shrinks_the_tables_it_should(
    name: str, fn: object, ordered: object
) -> None:
    r"""A table only one input order folds well is emitted from that order."""
    if name == "jaune":
        pytest.skip("clobbering already makes the identity order optimal here")
    # Circlefuck splits.
    # identity order already folds;.
    # same function with its inputs.
    table = "11110000" if name == "circlefuck" else "10101010"
    assert len(fn(table)) < len(ordered(table, (0, 1, 2))), (
        f"{name} did not reorder a table that only reordering folds"
    )


def test_reorder_permutation_preserves_the_function() -> None:
    r"""Permuting the table renames the inputs without changing the."""
    from esolangs.tools.boolean.helpers import permute_truth_table

    table = "01101001"
    n = 3
    for perm in [(0, 1, 2), (2, 0, 1), (2, 1, 0)]:
        permuted = permute_truth_table(table, perm)
        for row in range(2**n):
            bits = [(row >> (n - 1 - level)) & 1 for level in range(n)]
            original = sum(bits[level] << (n - 1 - i) for level, i in enumerate(perm))
            assert permuted[row] == table[original]


def test_wide_tables_skip_the_exhaustive_search() -> None:
    r"""Above the cap the order is picked greedily, so wide tables stay."""
    from esolangs.tools.boolean.helpers import _ORDER_SEARCH_MAX, _decision_tree_program

    n = _ORDER_SEARCH_MAX + 2
    table = "0" * (2**n - 1) + "1"
    assert len(boolean.brainfuck(table)) <= len(
        _decision_tree_program(table, ">", "<", tuple(range(n)))
    )


def test_greedy_order_is_correct_when_it_is_not_the_identity() -> None:
    r"""A greedily-ordered program still computes its table."""
    from esolangs.interpreters.tape_based.brainfuck import run
    from esolangs.tools.boolean.helpers import _greedy_input_order
    from tests.interpreters.runner import run_program

    n = 7
    table = "01" * 64
    assert _greedy_input_order(table, n) != tuple(range(n)), (
        "this table must exercise a non-identity greedy order"
    )
    program = boolean.brainfuck(table)
    for combo in range(2**n):
        bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
        stdin = "".join(f"{bit}\n" for bit in bits)
        got = run_program(run, program, stdin)
        assert got == table[combo], f"inputs {bits}"


def test_the_greedy_order_is_the_documented_one() -> None:
    r"""What the heuristic picks, per table, not merely that it is valid."""
    from esolangs.tools.boolean.helpers import _greedy_input_order

    # Tables the heuristic.
    assert _greedy_input_order("00000101", 3) == (0, 2, 1)
    assert _greedy_input_order("00010001", 3) == (1, 2, 0)

    # Tables no split helps: ties.
    for table in ("00011011", "01000111", "00111100", "01101001"):
        assert _greedy_input_order(table, 3) == (0, 1, 2), table

    # And the wide table the run-it.
    assert _greedy_input_order("01" * 64, 7) == (6, 0, 1, 2, 3, 4, 5)

    reordered = sum(
        1
        for value in range(256)
        if _greedy_input_order(format(value, "08b"), 3) != (0, 1, 2)
    )
    assert reordered == 94


def test_the_tree_program_spends_its_permutation_on_the_tested_cell() -> None:
    r"""``perm`` reaches the emission in exactly one place, and it shows."""
    from itertools import permutations

    from esolangs.tools.boolean.helpers import _decision_tree_program

    lengths = {
        perm: len(_decision_tree_program("00010111", ">", "<", perm))
        for perm in permutations(range(3))
    }
    assert lengths == {
        (0, 1, 2): 299,
        (0, 2, 1): 313,
        (1, 0, 2): 309,
        (1, 2, 0): 317,
        (2, 0, 1): 313,
        (2, 1, 0): 311,
    }

    # One and two inputs, where the.
    # in the move would still land.
    assert len(_decision_tree_program("01", ">", "<", (0,))) == 115
    assert len(_decision_tree_program("0110", ">", "<", (0, 1))) == 205
    assert len(_decision_tree_program("0110", ">", "<", (1, 0))) == 211


# The shape each boolean.
# optimizations even apply to.
# reduction are tree.
# lists are measured (see the.
# so this test is what keeps.
_MINTERM_SHAPED = {
    "a_painter_ant",
    "algebraic_programming_language",
    "bfstack",
    "container",
}

# Neither model describes these.
# not a sum and not a tree.
# at all: ``jaune_multiply``.
# numbers, a fixed program),.
# .
# ``slow_acv_mammalian`` is a.
# one, so the folding.
# what read the input -- the.
# appended -- so collapsing a.
# reads and break the.
# uniform depth ``n`` and its.
# .
# ``minifuck`` is a search too,.
# whatever code it can *see*.
# no per-row structure to fold.
# table's shape.
# .
# ``ztoalc_l`` emits no tree.
# discriminator cannot see.
# inputs are folded into a.
# four-row chunks are stored as.
# selected code's bit into the.
# and the program's size tracks.
# not the table's shape.
# cost is one term per selected.
# and the emitted length is a.
# of a committed anchor's.
# count.).
# .
# ``pct_squared_minus_one``.
# ``t``, which jumps to.
# computes the answer.
# single ``l`` -- rather than.
# constants the solver happens.
# folding discriminator has.
# ``n == 3`` tables this test.
# .
# ``one_two_three`` emits no.
# answer is whether the program.
# phase the embeds leave.
# length tracks the modulo-four.
# raises on the ``n == 3``.
# has to be embedded, and every.
# answer, so the projection.
# Minterm sums that nonetheless.
# folding: they apply.
# smaller table that a.
# test would otherwise lose is.
# is simply over fewer rows.
# essential inputs, so the gain.
# collapsed structure.
# it would if they had grown a.
_REDUCING = {
    "bit_tilde",
    "cod",
    "collatz_multiverse",
    "home_row",
    "nocomment",
    "point_break",
    "qoibl",
    "rotfuck",
    "suffolk",
    "suptiftam",
    "super_snusp",
}

# ``alight`` is a branch-free.
# ``ztoalc_l``: the inputs are.
# rule and the table is a.
# there are no subtrees to.
# to exactly the same length.
# (ZTOALC L's chunked variant.
# the same reason: lookup size.
_UNSHAPED = {
    "alight",
    "wii2d",
    "minifuck",
    "ztoalc_l",
    "pct_squared_minus_one",
    "one_two_three",
    "jaune_multiply",
    "circlefuck_byte",
    "slow_acv_mammalian",
}

# Every table depending on.
# All have ones-count 4, as.
# measuring density.
_ONE_DEPENDENCY = (
    "11110000",
    "00001111",
    "11001100",
    "00110011",
    "10101010",
    "01010101",
)
_PARITY = "01101001"


@pytest.mark.parametrize(
    ("name", "fn"),
    sorted(
        (lang.id, lang.boolean)
        for lang in LANGUAGES.values()
        if lang.boolean is not None
    ),
    ids=lambda v: v if isinstance(v, str) else "",
)
@pytest.mark.parametrize("table", ["0", "1"])
def test_a_one_entry_table_is_refused(name: str, fn: object, table: str) -> None:
    r"""No generator builds a program for a nullary table."""
    assert callable(fn), name
    with pytest.raises(ValueError, match="at least one input") as caught:
        fn(table)
    assert "at least one input" in str(caught.value), f"{name} on {table!r}"


@pytest.mark.parametrize(
    ("name", "fn"),
    sorted(
        (lang.id, lang.boolean)
        for lang in LANGUAGES.values()
        if lang.boolean is not None
    ),
    ids=lambda v: v if isinstance(v, str) else "",
)
@pytest.mark.parametrize(
    ("table", "fragment"),
    [("011", "power-of-two"), ("0123", "only '0' and '1'")],
)
def test_a_malformed_table_is_refused_in_the_shared_words(
    name: str, fn: object, table: str, fragment: str
) -> None:
    r"""Every generator rejects a malformed table in the *shared*."""
    assert callable(fn), name
    with pytest.raises(ValueError, match=re.escape(fragment)) as caught:
        fn(table)
    assert "at least one input" not in str(caught.value), (
        f"{name} on {table!r} said {str(caught.value)!r}, which reports a "
        f"nullary table -- {table!r} is malformed, not nullary, and the two "
        f"are separate rejections with separate words"
    )


@pytest.mark.parametrize(
    "name",
    sorted(
        n
        for n in boolean.__all__
        if n not in ("BOOLEAN", "instantiate")
        and callable(getattr(boolean, n, None))
        and n not in _UNSHAPED
    ),
)
def test_generator_shape_is_what_the_catalogue_says(name: str) -> None:
    r"""A tree generator folds a one-dependency table; a minterm sum cannot."""
    fn = getattr(boolean, name)
    best = min(len(fn(table)) for table in _ONE_DEPENDENCY)
    parity = len(fn(_PARITY))
    folds = 1 - best / parity
    if name in _REDUCING:
        # The gain is real but is not a.
        # direction: the saving must.
        # table that depends on *every*.
        assert folds >= 0.05, (
            f"{name} is listed as applying dependency reduction but gains "
            f"only {folds:.1%} on a one-dependency table -- its reduction "
            f"has regressed"
        )
        for table in _ONE_DEPENDENCY:
            assert len(fn(table)) < parity, table
        return
    if name in _MINTERM_SHAPED:
        assert folds < 0.05, (
            f"{name} is listed as minterm-shaped but folds {folds:.1%} on a "
            f"one-dependency table -- if it grew a tree, move it to the "
            f"tree-shaped list and consider whether reordering now applies"
        )
    else:
        assert folds >= 0.05, (
            f"{name} is listed as tree-shaped but folds only {folds:.1%} -- "
            f"either its folding regressed or it is a minterm sum and belongs "
            f"in _MINTERM_SHAPED"
        )


# Every boolean generator.
# the whole registry was swept.
# generator falls short --.
# one of the 69 builds both.
# .
# Ten is here because it was.
# waved through.
# at eight: n<=10 cost 141s of.
# generators were then measured.
# .
# minifuck 42.8s -> 8.6s.
# polynomial 28.4s -> 5.5s.
# one_two_three 17.8s -> 3.7s.
# .
# plus a generic pass on the.
# is now 46.1s of CPU.
# n=10 23.8s.
# .
# n=6 costing six times n=7 is.
# is ``_ORDER_SEARCH_MAX = 6``.
# generator builds all ``n!`` =.
# shortest; at n=7 it switches.
# *bigger* table is hundreds of.
# against 0.002s at seven,.
# .
# What that 720-build search.
# with the cap at 6 and at 5:.
# 0.79s.
# the win is concentrated, not.
# search, circlefuck dense.
# 13.5%.
# .
# **Measuring that requires.
# ``streetcode``, ``stack``,.
# .helpers import.
# ``helpers`` alone leaves the.
# reports the greedy side as.
# .
# n=6 was 10.0s until the.
# search still builds every one.
# ``best_input_order``.
# going per-language -- so that.
# .
# Across everything here, 1356.
# byte-identical: the 24 that.
# refuse, minifuck's dense n=9.
# shapes, which the mark.
# .
# Ten still peaks at 637MB RSS.
# of program text.
# n <= _QUICK_ARITY runs in the.
# Both bands assert the same.
# the 69 items and ~3s it had.
_MAX_ARITY = 10
_QUICK_ARITY = 5

_ARITY_BANDS = (
    pytest.param(range(1, _QUICK_ARITY + 1), id="quick"),
    pytest.param(
        range(_QUICK_ARITY + 1, _MAX_ARITY + 1),
        id="deep",
        marks=pytest.mark.slow,
    ),
)

# The generators that do not.
# because a cap can bind on one.
# exactly that: a per-name cap.
# which it does not -- that.
# .
# wii2d refuses n=10 dense.
# the ``_WII2D_MAX_INDEX_DOMAIN.
# below, raising the constant.
# decode ratchets -- live count.
# bit length doubles every.
# 144s -- and refuses on the.
# exactly-once embed.
# .
# Two generators that used to.
# were the *construction's*.
# .
# interprogck8 capped at n=3.
# lines and the n=4 bit-0.
# express through one-line.
# .
# factor capped at n=3 on.
# at n=6 on the 16000-digit.
# policies rather than anything.
# .
# An entry needs the.
# refusal is built around --.
# accept a generator that had.
# since an encoding bug reads.
_ARITY_CAPPED: dict[tuple[str, str], tuple[int, str]] = {
    ("wii2d", "dense"): (9, "cost guard; below the bound this is a size/time"),
}


# The two table shapes every.
# pseudo-random table and.
# parity but stops at n=9.
# earlier on parity than on.
# refuses dense n=11 (2910).
# sweep reports the wrong.
# are built at every arity and.
def _dense(n: int) -> str:
    r"""A deterministic dense pseudo-random table -- the worst case to fold."""
    digest = hashlib.sha256(f"dense:{n}".encode()).digest()
    bits: list[str] = []
    block = 0
    while len(bits) < 2**n:
        digest = hashlib.sha256(digest + bytes([block & 255])).digest()
        bits.extend(str(byte & 1) for byte in digest)
        block += 1
    return "".join(bits[: 2**n])


def _parity(n: int) -> str:
    r"""Parity -- the table with no constant subtree above a single row."""
    return "".join(str(bin(row).count("1") & 1) for row in range(2**n))


_SHAPES = (("dense", _dense), ("parity", _parity))


@pytest.mark.parametrize("arities", _ARITY_BANDS)
@pytest.mark.parametrize("name", sorted(BY_BOOLEAN))
def test_every_generator_builds_up_to_ten_inputs(name: str, arities: range) -> None:
    r"""Every boolean generator builds every arity up to :data:`_MAX_ARITY`."""
    fn = getattr(boolean, name)
    for n in arities:
        for shape, make in _SHAPES:
            cap, pattern = _ARITY_CAPPED.get((name, shape), (_MAX_ARITY, ""))
            table = make(n)
            if n <= cap:
                program = str(fn(table))
                assert program, f"{name} built an empty program at n={n} ({shape})"
            else:
                with pytest.raises(ValueError, match=re.escape(pattern)):
                    fn(table)


def test_arity_caps_are_still_caps() -> None:
    r"""A capped generator that grew past its cap must leave."""
    makers = dict(_SHAPES)
    for (name, shape), (cap, pattern) in sorted(_ARITY_CAPPED.items()):
        fn = getattr(boolean, name)
        make = makers[shape]
        assert str(fn(make(cap))), (
            f"{name} no longer builds at its cap n={cap} ({shape})"
        )
        with pytest.raises(ValueError, match=re.escape(pattern)):
            fn(make(cap + 1))


# Every table of arity one, two.
# sweep above sees two tables.
# *third* shape -- an.
# essential input, a single.
# exhaustive-domain half, and n.
# thing one can afford: n=4 is.
# .
# It is the executable witness.
# entries.
# every arity; this checks the.
# reachable, which is what.
# .
# 4.7s serial across all 69, no.
# is the top, Factor 0.25s, the.
_EXHAUSTIVE_ARITY = 3


def _all_tables(arity: int) -> list[str]:
    r"""Every truth table of every arity from one up to ``arity``."""
    return [
        format(k, f"0{2**n}b") for n in range(1, arity + 1) for k in range(2 ** (2**n))
    ]


@pytest.mark.parametrize("name", sorted(BY_BOOLEAN))
def test_every_generator_is_total_on_every_small_table(name: str) -> None:
    r"""Every generator returns a program for *every* table up to three."""
    fn = getattr(boolean, name)
    for table in _all_tables(_EXHAUSTIVE_ARITY):
        program = str(fn(table))
        assert program, f"{name} built an empty program for {table!r}"


def test_cm_constants_builds_only_the_bootstrap_for_small_values() -> None:
    r"""Nothing above k2 is needed, so the plan sieve is never entered."""
    from esolangs.tools.boolean.helpers import _cm_constants

    lines = _cm_constants([1, 2])
    assert len(lines) == 4
    assert all(line.endswith("NOT PRINT.") for line in lines)
    assert _cm_constants([]) == lines


# The build sweep above proves.
# inputs.
# four inputs either.
# command characters from slot.
# emitted a program its own.
# saw a healthy non-empty.
# .
# The property that matters is.
# *essential*: a dense n=9.
# slot and sails through.
# all n of them -- its one 1.
# stays small enough to execute.
# 11.7s for an all-essential.
# test and a nightly job.
# .
# n=6 is the floor that would.
# 69: 18.6s of work in total,.
# four workers this suite runs.
# key alphabet makes this fail,.
# is high enough.
# There is deliberately no.
# finding, and if a language.
# cost beside it like.
# .
# A wider probe backs the.
# all 69 languages, both.
# kind, so Grapheme was the.
# expensive to reach and are.
_ONE_MINTERM_ARITY = 6


def _one_minterm(n: int) -> str:
    r"""A single 1, which makes every input essential at minimum size."""
    return "1" + "0" * (2**n - 1)


def _one_hot(n: int) -> str:
    r"""1 exactly where one input is set."""
    return "".join(str(int(bin(row).count("1") == 1)) for row in range(2**n))


# : The table shapes every.
_EXEC_SHAPES = (("one_minterm", _one_minterm), ("one_hot", _one_hot))


@pytest.mark.parametrize(
    "make", [make for _, make in _EXEC_SHAPES], ids=[s for s, _ in _EXEC_SHAPES]
)
@pytest.mark.parametrize("name", sorted(esolangs.list_languages()))
def test_every_generator_runs_what_it_builds(
    name: str, make: Callable[[int], str]
) -> None:
    r"""Build a table using all six inputs, execute it, and check every row."""
    table = make(_ONE_MINTERM_ARITY)
    assert esolangs.evaluate(name, table, timeout=30) == table


@pytest.mark.parametrize(
    "make", [make for _, make in _EXEC_SHAPES], ids=[s for s, _ in _EXEC_SHAPES]
)
def test_the_exec_tables_really_need_every_input(make: Callable[[int], str]) -> None:
    r"""The guards above are worthless if their tables fold."""
    table = make(_ONE_MINTERM_ARITY)
    assert len(essential_inputs(table, _ONE_MINTERM_ARITY)) == _ONE_MINTERM_ARITY


# : What.
# : ``(n=8 size, n=9 size,.
# : program's length is.
# : ratio carries a band.
# :.
# : Timings are deliberately.
# : them approximate, and.
# : is busy -- which, on a.
_DOCUMENTED_SIZES: dict[str, tuple[int, int, float]] = {
    "Circuit Diagram": (609_526, 1_609_864, 2.6),
    "COD": (942_692, 3_668_705, 3.9),
    "ROTfuck": (86_605, 194_945, 2.3),
    "Polynomial": (3_383_048, 10_896_883, 3.2),
    "SLOW ACV MAMMALIAN": (1_672_368, 3_380_418, 2.0),
    "bit~": (31_076, 69_005, 2.2),
    "123": (219_937, 752_570, 3.4),
    "Factor": (17_613, 36_339, 2.1),
}


@pytest.mark.slow
@pytest.mark.parametrize("name", sorted(_DOCUMENTED_SIZES))
def test_the_expensive_generators_grow_as_documented(name: str) -> None:
    r"""``docs/limitations.md`` tells a reader whether n=11 is affordable."""
    at_eight, at_nine, ratio = _DOCUMENTED_SIZES[name]
    assert len(esolangs.generate(name, _dense(8))) == at_eight
    assert len(esolangs.generate(name, _dense(9))) == at_nine
    assert at_nine / at_eight == pytest.approx(ratio, abs=0.35)


@pytest.mark.slow
def test_nothing_else_is_anywhere_near_that_big() -> None:
    r"""The document's "every other generator is under 600KB at n=9"."""
    biggest = max(
        (len(esolangs.generate(name, _dense(9))), name)
        for name in esolangs.list_languages()
        if name not in _DOCUMENTED_SIZES
    )
    assert biggest[0] < 600_000, biggest
    assert biggest[1] == "A Painter Ant"
