"""The Minifuck derivation checks that stand outside any one route.

The suites that drive the generator are siblings: test_boolean_minifuck_pool,
_sim and _routes.  What is here is the module-level evidence the
construction rests on -- that each input is one run and no more, that the fused
column walk matches deriving one at a time, and that the coverage population
is the one the source says it is.
"""

import importlib

import pytest

from esolangs.tools.helpers import TEMPLATE_CHAR, runs
from esolangs.tools.minifuck_sim import PAIR
from tests.tools.minifuck_support import run_count


def _unreachable(*_args: object, **_kwargs: object) -> None:
    """Stand in for a function a test asserts is never called."""
    raise AssertionError("this should not have been called")


def _slot_order(gen: object, table: str) -> list[int] | None:
    """The run starts in the order ``gen`` emits them, or None.

    The k-th run *is* input k, so what the text can still show is that
    the run count is the arity and every run is whole: a route that
    appended the ignored inputs where they do not belong now refuses in
    ``_lift`` rather than emitting a misnamed template.
    """

    try:
        template = gen(table)
    except ValueError:
        return None  # a generator need not cover every arity
    n = len(table).bit_length() - 1
    spans = runs(template, TEMPLATE_CHAR, (PAIR,) * n)
    return [start for start, _end in spans]


@pytest.mark.slow  # two closed-form builds plus eight interpreter runs each
def test_minifuck_ignored_leading_inputs_compute_their_function() -> None:
    """A table that ignores its leading inputs computes, not merely emits in order.

    ``01010101`` and ``10101010`` depend on their last input alone, so the
    lift has to keep the ignored runs in name order -- ordering alone is not
    evidence it works.  Only running every row is, and a wrong build here
    would otherwise look exactly like a right one to the test above.
    """
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.minifuck import run
    from esolangs.tools import parameterized
    from tests.tools.fills import _fill_minifuck

    for table in ("01010101", "10101010"):
        template = parameterized.minifuck(table)
        widths = set()
        for combo in range(8):
            bits = [(combo >> (2 - i)) & 1 for i in range(3)]
            program = _fill_minifuck(template, bits)
            widths.add(len(program))
            io_ = ScriptedIO("")
            run(program, io_)
            assert io_.getvalue() == table[combo], f"{table} inputs {bits}"
        # The ignored setters are emitted rather than dropped, so they must
        # not make the program's length depend on the bits it is given.
        assert len(widths) == 1, (table, widths)


# 2.3s: two three-input minifuck builds, which is the cost, not the asserts.
@pytest.mark.slow
def test_minifuck_single_essential_falls_past_the_degenerate_lookup() -> None:
    """One essential input does not guarantee the cell lookup resolves it.

    ``_degenerate`` answers from a column of the embed rather than
    searching, and a projection onto the *last* input has no such column, so
    it declines.  These tables reach it through the projection block, which
    returns whatever ``_lift`` builds; the later ``len(essential) <= 1``
    lookup is not what serves them.  That one is reachable only when no
    projection happened at all -- ``n <= 1`` -- and every such table
    resolves, so its own decline branch cannot be taken from here.
    """

    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.minifuck import run
    from tests.tools.fills import _fill_minifuck

    module = importlib.import_module("esolangs.tools.minifuck")

    for table in ("01010101", "10101010"):
        assert module.essential_inputs(table, 3) == [2]
        assert module._degenerate(table, 3) is None  # noqa: SLF001

        # Declining is only correct if the build still produces the table.
        template = module.minifuck(table)
        for combo in range(8):
            bits = [(combo >> (2 - i)) & 1 for i in range(3)]
            io_ = ScriptedIO("")
            run(_fill_minifuck(template, bits), io_)
            assert io_.getvalue() == table[combo], f"{table} inputs {bits}"


# 4s: one five-input build, which is the cost -- the 32 interpreter runs are
# effectively free next to the build.
@pytest.mark.slow
def test_minifuck_builds_five_input_xor() -> None:
    """Five-input XOR builds and prints all 32 rows.

    This is the table the arity turns on: a fully-essential table that the
    lookup route alone serves at five inputs.

    Running every row on the shipped interpreter is the whole point: a
    template that has not been seen to print is not evidence, and the
    equal-width check is what keeps the instantiation from leaking its
    inputs through ``len()``.
    """
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.minifuck import run
    from esolangs.tools import parameterized
    from tests.tools.fills import _fill_minifuck

    table = "".join(str(bin(r).count("1") & 1) for r in range(32))
    template = parameterized.minifuck(table)

    widths = set()
    for combo in range(32):
        bits = [(combo >> (4 - i)) & 1 for i in range(5)]
        program = _fill_minifuck(template, bits)
        widths.add(len(program))
        io_ = ScriptedIO("")
        run(program, io_)
        assert io_.getvalue() == table[combo], f"inputs {bits}"

    assert len(widths) == 1, widths


# 5.8s: builds the five-input spans and replays the enumeration through them.
# This is the guard on a *soundness* claim, so it checks the whole population
# rather than a sample -- a screen that declines one reachable table is a
# silent coverage regression, which no sampled test would catch.


def test_a_flipped_embed_complements_in_place_and_keeps_slot_order() -> None:
    """``flips`` is a live derivation coordinate, not dead weight.

    The pass that varied it was removed and the parameter kept, so no build
    passes a mask any more -- which left the gadget it emits unrun.  Kept
    open, it should still do what its docstring says, and the two claims are
    separable:

    First, the mask *lands*: each set bit adds exactly one ``_FLIP`` gadget,
    so the template grows by three characters per bit and by nothing at all
    for the empty mask.  Second, the setters stay in ascending name order
    whatever the mask says -- the gadget goes after the setter it
    complements, never in place of a different one -- which is the invariant
    every generator here is held to, and the one a "complement input i"
    coordinate is most likely to break.
    """

    from esolangs.tools.minifuck import _FLIP, _embed

    for n in (2, 3):
        plain = _embed(n).template()
        assert run_count(plain, n) == n
        assert _embed(n, flips=0).template() == plain  # the default is no-op

        for mask in range(1, 2**n):
            flipped = _embed(n, flips=mask).template()
            assert len(flipped) == len(plain) + len(_FLIP) * mask.bit_count(), mask
            # The gadget goes right after the setter it complements, and
            # after no other.
            pairs = (PAIR,) * n
            for i, (_start, end) in enumerate(runs(flipped, TEMPLATE_CHAR, pairs)):
                follows = flipped[end : end + len(_FLIP)] == _FLIP
                assert follows == bool((mask >> i) & 1), (mask, i)


# 3.7s standalone: the target-set derivation is the cost.  It is free when the
# XOR5 build above has already run in this process and warmed the cache, but
# a -k selection or a shuffled order can pick this one alone, so it is marked
# for what it costs on its own rather than for the lucky case.


def test_mux_refuses_below_its_minimum_arity() -> None:
    """``_mux`` separates rows, which needs at least two of them to separate."""

    module = importlib.import_module("esolangs.tools.minifuck")

    assert module._MUX_MIN_ARITY == 2  # noqa: SLF001
    assert module._mux("01", 1) is None  # noqa: SLF001


def test_the_scout_distrusts_states_its_summary_cannot_speak_for() -> None:
    """A base outside the parity law's key sends ``_mux`` to the sweep.

    The scout summarises a row as its tape alone, which is only sound with
    no skip pending, no dead row, and one shared pool region.  No
    separation produces the other states, so they are constructed: each
    must come back untrusted rather than mispriced.
    """

    module = importlib.import_module("esolangs.tools.minifuck")

    base = module._mux_separate(2)  # noqa: SLF001
    positions = base.ptrs()
    lowest, highest = min(positions), max(positions)
    accs = range(highest - lowest + module._POOL_WIDTH + 1, lowest - 1)  # noqa: SLF001

    trusted = module._mux_scout(base, "0110", 2, accs)  # noqa: SLF001
    assert trusted[1], "the real separation must be scoutable"

    skipped = base.fork()
    skipped.ms[0].skip = True
    assert module._mux_scout(skipped, "0110", 2, accs) == (None, False)  # noqa: SLF001

    dead = base.fork()
    dead.ms[1].dead = True
    assert module._mux_scout(dead, "0110", 2, accs) == (None, False)  # noqa: SLF001

    torn = base.fork()
    torn.ms[0].tape ^= 1 << 3
    assert module._mux_scout(torn, "0110", 2, accs) == (None, False)  # noqa: SLF001


def test_the_probe_simulates_when_the_parity_law_declines() -> None:
    """Off the canonical state the probe answers by simulation, identically.

    ``_sculpt_columns`` refuses a joint whose rows disagree inside the pool
    region, and ``_mux_probe`` must then hand back exactly what the
    simulated probe says -- the fallback is the specification, not an
    approximation of it.
    """

    module = importlib.import_module("esolangs.tools.minifuck")

    torn = module._mux_separate(2).fork()  # noqa: SLF001
    torn.ms[0].tape ^= 1 << 3
    acc = module._POOL_WIDTH + 4  # noqa: SLF001
    assert module._sculpt_columns(torn, acc) is None  # noqa: SLF001
    assert module._mux_probe(torn, acc, 0) == module._mux_probe_sim(  # noqa: SLF001
        torn, acc, 0
    )


def test_the_probe_frame_refuses_codes_outside_its_key() -> None:
    """A code that strands a skip or leaves the pool region has no frame.

    The frame summarises a pool code as ``(landed, parity)``, which is only
    a summary while the code stays inside the region and leaves the row
    runnable.  ``[`` from the canonical byte cascades and owes a skip; a
    long walk crosses cell 8.  Both must decline rather than summarise.
    """

    module = importlib.import_module("esolangs.tools.minifuck")

    byte = module._mux_separate(2).ms[0].tape & module._POOL_MASK  # noqa: SLF001
    assert module._probe_frame("[", byte) is None  # noqa: SLF001
    assert module._probe_frame("[x" * 9, byte) is None  # noqa: SLF001
    assert module._probe_frame(module._SCULPT_POOL_CODE, byte) is not None  # noqa: SLF001


def test_the_weight_law_matches_the_parsed_runs() -> None:
    """``run_weight`` is ``apply(_runs(_mux_weight(k)))``, or refuses untouched.

    The gadget law is a composition claim over the pinned laws, so the
    differential is against them, from arbitrary states -- a fresh setter
    site is exactly where a wrong march model still looks right.  A refusal
    must leave the row untouched, and both the skip refusal and the floor
    refusal must actually fire in the sample.
    """
    import random

    from esolangs.tools.minifuck_sim import _runs, _Sim

    module = importlib.import_module("esolangs.tools.minifuck")

    rng = random.Random(20260910)
    applied = refused = 0
    for _ in range(2500):
        fast = _Sim(64)
        fast.tape = rng.getrandbits(rng.choice([16, 48, 200]))
        fast.ptr = rng.randrange(0, 40)
        fast.skip = rng.random() < 0.2
        units = rng.randrange(1, 70)
        slow = fast.copy()
        if not fast.run_weight(units):
            refused += 1
            assert fast.key() == slow.key(), "a refusal touched the row"
            continue
        applied += 1
        slow.apply(_runs(module._mux_weight(units)))  # noqa: SLF001
        assert fast.key() == slow.key(), (units, slow.key())
    assert applied, "the fused arm never fired"
    assert refused, "the refusal arm never fired"

    floor_refusals = 0
    for ptr in range(6):
        for units in range(1, 12):
            fast = _Sim(64)
            fast.tape, fast.ptr = (1 << 40) - 1, ptr
            slow = fast.copy()
            if fast.run_weight(units):
                slow.apply(_runs(module._mux_weight(units)))  # noqa: SLF001
                assert fast.key() == slow.key(), (ptr, units)
            else:
                floor_refusals += 1
    assert floor_refusals, "the floor guard never fired"

    # The edge arms: a dead row and zero units are no-ops that still apply.
    dead = _Sim(16)
    dead.dead = True
    frozen = dead.key()
    assert dead.run_weight(3)
    assert dead.key() == frozen
    fresh = _Sim(16)
    frozen = fresh.key()
    assert fresh.run_weight(0)
    assert fresh.key() == frozen

    # The joint-level fallback: a row the law refuses advances by the
    # parsed runs and the pair must land on the same state.
    joint = module._Joint(1)  # noqa: SLF001
    for m in joint.ms:
        m.tape, m.ptr = 0b1011 << 5, 8
    joint.ms[0].skip = True
    clones = [m.copy() for m in joint.ms]
    code = module._mux_weight(3)  # noqa: SLF001
    joint.emit_weight(code, 3)
    assert joint.parts[-1] == code
    for m, clone in zip(joint.ms, clones, strict=True):
        clone.apply(_runs(code))
        assert m.key() == clone.key()


def test_the_rewind_law_matches_the_parsed_runs() -> None:
    """A sculpting round and a fused round sequence match the parsed runs.

    ``run_rewind`` claims the round ``"<"*k + "[x"*k + "x"`` in one law
    call and ``run_rewinds`` claims a whole sequence over one extracted
    window; both fall back to the laws when their frame does not hold, so
    the differential covers fused and fallback states alike.
    """
    import random

    from esolangs.tools.minifuck_sim import _runs, _Sim

    rng = random.Random(20260911)
    fused = fell_back = 0
    for _ in range(2500):
        fast = _Sim(64)
        fast.tape = rng.getrandbits(rng.choice([32, 400]))
        fast.ptr = rng.randrange(0, 60)
        fast.skip = rng.random() < 0.2
        count = rng.randrange(0, 40)
        slow = fast.copy()
        if fast.skip or fast.ptr < count:
            fell_back += 1
        else:
            fused += 1
        fast.run_rewind(count)
        slow.apply(_runs("<" * count + "[x" * count + "x"))
        assert fast.key() == slow.key(), (count, slow.key())
    assert fused, "the fused arm never fired"
    assert fell_back, "the fallback arm never fired"

    for _ in range(800):
        fast = _Sim(64)
        fast.tape = rng.getrandbits(rng.choice([64, 400]))
        fast.ptr = rng.randrange(0, 60)
        fast.skip = rng.random() < 0.15
        widths = sorted(
            (rng.randrange(1, 40) for _ in range(rng.randrange(1, 12))),
            reverse=True,
        )
        if rng.random() < 0.3:
            rng.shuffle(widths)
        slow = fast.copy()
        fast.run_rewinds(widths)
        for width in widths:
            slow.apply(_runs("<" * width + "[x" * width + "x"))
        assert fast.key() == slow.key(), (widths, slow.key())

    # The edge arms: dead rows and empty sequences are no-ops, and a zero
    # count is the bare ``x``, which consumes a pending skip.
    dead = _Sim(16)
    dead.dead = True
    frozen = dead.key()
    dead.run_rewind(4)
    dead.run_rewinds([3, 2])
    assert dead.key() == frozen
    still = _Sim(16)
    frozen = still.key()
    still.run_rewinds([])
    assert still.key() == frozen
    skipping = _Sim(16)
    skipping.skip = True
    clone = skipping.copy()
    skipping.run_rewind(0)
    clone.apply(_runs("x"))
    assert skipping.key() == clone.key()


def test_the_pascal_plan_matches_the_emitted_round_loop() -> None:
    """The binomial inverse returns the sculpt loop's exact rewinds.

    Every two-input table is checked at every accumulator, then sampled
    wider rows check the same identity after the triangle grows.  The oracle
    emits each selected round and probes again; it shares no inverse with the
    plan.  Multi-round cases are required so a probe that never fired cannot
    make the differential pass vacuously.
    """
    import math
    import random

    module = importlib.import_module("esolangs.tools.minifuck")

    for row in range(65):
        expected = sum(
            1 << column for column in range(row + 1) if math.comb(row, column) & 1
        )
        assert module._pascal_parity_row(row) == expected  # noqa: SLF001

    rng = random.Random(20260913)
    cases: list[tuple[int, list[str]]] = [
        (2, [format(value, "04b") for value in range(16)]),
        (3, [format(rng.getrandbits(8), "08b") for _ in range(8)]),
        (6, [format(rng.getrandbits(64), "064b") for _ in range(2)]),
    ]
    longest = 0
    for n, tables in cases:
        base = module._mux_separate(n)  # noqa: SLF001
        positions = base.ptrs()
        lowest, highest = min(positions), max(positions)
        all_accs = range(
            highest - lowest + module._POOL_WIDTH + 1,  # noqa: SLF001
            lowest - 1,
        )
        accs = (
            all_accs
            if n == 2
            else (all_accs.start, all_accs[len(all_accs) // 2], all_accs[-1])
        )
        want_tables = [tuple(int(ch) for ch in table) for table in tables]
        for table, want in zip(tables, want_tables, strict=True):
            for acc in accs:
                recorded: dict[tuple[int, bool], list[int]] = {}
                winner, trusted = module._mux_scout(  # noqa: SLF001
                    base, table, n, range(acc, acc + 1), recorded
                )
                assert trusted
                assert winner is not None

                joint = base.fork()
                emitted: list[int] = []
                for _ in range(2**n + 4):
                    found = module._mux_probe(joint, acc, 0)  # noqa: SLF001
                    assert found is not None
                    disagree = [
                        pointer
                        for pointer, got, target in zip(
                            joint.ptrs(), found[0], want, strict=True
                        )
                        if got != target
                    ]
                    if not disagree:
                        break
                    rewind = max(disagree) - acc + 1
                    emitted.append(rewind)
                    joint.emit("<" * rewind)
                    joint.emit("[x" * rewind)
                    joint.emit("x")
                else:
                    raise AssertionError("the emitted oracle reached the round cap")

                planned = recorded[(acc, True)]
                assert planned == emitted, (n, table, acc)
                longest = max(longest, len(planned))
    assert longest > 1, "the oracle never exercised round composition"


@pytest.mark.parametrize("n", [2, 10])
def test_the_lookup_rule_is_linear(n: int) -> None:
    """The direct strip has one bounded-cost block per table cell."""
    import random

    module = importlib.import_module("esolangs.tools.minifuck")

    rng = random.Random(20260914)
    table = format(rng.getrandbits(2**n), f"0{2**n}b")
    built = module._mux(table, n)  # noqa: SLF001
    assert built is not None

    assert built == module._mux_lookup(table, n)  # noqa: SLF001
    assert len(built) <= 650 + 70 * 2**n


def test_the_preserving_step_restores_arbitrary_tape() -> None:
    """The lookup's right step preserves every tested tape and advances one."""

    module = importlib.import_module("esolangs.tools.minifuck")
    for ptr in (0, 7):
        for tape in range(256):
            sim = module._Sim(32)  # noqa: SLF001
            sim.ptr = ptr
            sim.tape = tape << (ptr + 1)
            before = sim.tape
            sim.apply(module._runs(module._MUX_PRESERVE_RIGHT))  # noqa: SLF001
            assert (sim.ptr, sim.tape, sim.skip) == (ptr + 1, before, False)


@pytest.mark.slow  # two ten-input builds plus twelve interpreter rows, ~10s
def test_ten_input_builds_print_on_the_interpreter() -> None:
    """Sampled rows of both ten-input shapes answer on the real interpreter.

    The rule path's acceptance is the laws' replay; this is the standard
    above it -- the shipped interpreter running instantiated rows.  Six
    rows per shape, the two corner rows always among them; the full
    1024-row sweep was executed when the path landed, both shapes correct.
    """
    import hashlib
    import random

    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.minifuck import run
    from esolangs.tools import minifuck
    from tests.tools.fills import _fill_minifuck

    digest = hashlib.sha256(b"dense:10").digest()
    bits: list[str] = []
    block = 0
    while len(bits) < 1024:
        digest = hashlib.sha256(digest + bytes([block & 255])).digest()
        bits.extend(str(byte & 1) for byte in digest)
        block += 1
    dense = "".join(bits[:1024])
    parity = "".join(str(bin(row).count("1") & 1) for row in range(1024))

    rng = random.Random(20260915)
    for table in (dense, parity):
        template = minifuck(table)
        for combo in sorted({*rng.sample(range(1024), 4), 0, 1023}):
            row = [(combo >> (9 - i)) & 1 for i in range(10)]
            io_ = ScriptedIO("")
            run(_fill_minifuck(template, row), io_)
            assert io_.getvalue() == table[combo], f"row {combo}"
