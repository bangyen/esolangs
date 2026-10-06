"""The Minifuck derivation checks that stand outside any one route."""

import importlib

import pytest

from esolangs.tools.helpers import TEMPLATE_CHAR, essential_inputs, runs
from esolangs.tools.minifuck.mux import (
    _MUX_MIN_ARITY,
    _MUX_PRESERVE_RIGHT,
    _SCULPT_POOL_CODE,
    _mux,
    _mux_weight,
    _probe_frame,
)
from esolangs.tools.minifuck.pool import _POOL_MASK
from esolangs.tools.minifuck.sim import PAIR, _Joint, _runs, _Sim
from tests.tools.minifuck_support import _mux_separate, run_count


def _unreachable(*_args: object, **_kwargs: object) -> None:
    """Stand in for a function a test asserts is never called."""
    raise AssertionError("this should not have been called")


def _slot_order(gen: object, table: str) -> list[int] | None:
    """The run starts in the order ``gen`` emits them, or None."""

    try:
        template = gen(table)
    except ValueError:
        return None  # a generator need not cover every arity
    n = len(table).bit_length() - 1
    spans = runs(template, TEMPLATE_CHAR, (PAIR,) * n)
    return [start for start, _end in spans]


@pytest.mark.slow  # two closed-form builds plus eight interpreter runs each
def test_minifuck_ignored_leading_inputs_compute_their_function() -> None:
    """A table that ignores its leading inputs computes, not merely emits in order."""
    from esolangs import tools as generators
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.minifuck import run
    from tests.tools.fills import _fill_minifuck

    for table in ("01010101", "10101010"):
        template = generators.minifuck(table)
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
    """One essential input does not guarantee the cell lookup resolves it."""

    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.minifuck import run
    from tests.tools.fills import _fill_minifuck

    module = importlib.import_module("esolangs.tools.minifuck")

    for table in ("01010101", "10101010"):
        assert essential_inputs(table, 3) == [2]
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
    """Five-input XOR builds and prints all 32 rows."""
    from esolangs import tools as generators
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.minifuck import run
    from tests.tools.fills import _fill_minifuck

    table = "".join(str(bin(r).count("1") & 1) for r in range(32))
    template = generators.minifuck(table)

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
    """``flips`` is a live derivation coordinate, not dead weight."""

    from esolangs.tools.minifuck.pool import _FLIP, _embed

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

    assert _MUX_MIN_ARITY == 2
    with pytest.raises(ValueError, match="at least two inputs"):
        _mux("01", 1)


def test_the_probe_frame_refuses_codes_outside_its_key() -> None:
    """A code that strands a skip or leaves the pool region has no frame."""

    byte = _mux_separate(2).ms[0].tape & _POOL_MASK
    assert _probe_frame("[", byte) is None
    assert _probe_frame("[x" * 9, byte) is None
    assert _probe_frame(_SCULPT_POOL_CODE, byte) is not None


def test_the_preserving_step_restores_arbitrary_tape() -> None:
    """The lookup's right step preserves every tested tape and advances one."""

    for ptr in (0, 7):
        for tape in range(256):
            sim = _Sim(32)
            sim.ptr = ptr
            sim.tape = tape << (ptr + 1)
            before = sim.tape
            sim.apply(_runs(_MUX_PRESERVE_RIGHT))
            assert (sim.ptr, sim.tape, sim.skip) == (ptr + 1, before, False)


@pytest.mark.slow  # two ten-input builds plus twelve interpreter rows, ~10s
def test_ten_input_builds_print_on_the_interpreter() -> None:
    """Sampled rows of both ten-input shapes answer on the real interpreter."""
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


def test_the_weight_law_matches_the_parsed_runs() -> None:
    """``run_weight`` is ``apply(_runs(_mux_weight(k)))``, or refuses untouched."""
    import random

    from esolangs.tools.minifuck.sim import _runs, _Sim

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
        slow.apply(_runs(_mux_weight(units)))
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
                slow.apply(_runs(_mux_weight(units)))
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
    joint = _Joint(1)
    for m in joint.ms:
        m.tape, m.ptr = 0b1011 << 5, 8
    joint.ms[0].skip = True
    clones = [m.copy() for m in joint.ms]
    code = _mux_weight(3)
    joint.emit_weight(code, 3)
    assert joint.parts[-1] == code
    for m, clone in zip(joint.ms, clones, strict=True):
        clone.apply(_runs(code))
        assert m.key() == clone.key()


def test_the_rewind_law_matches_the_parsed_runs() -> None:
    """A sculpting round and a fused round sequence match the parsed runs."""
    import random

    from esolangs.tools.minifuck.sim import _runs, _Sim

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
