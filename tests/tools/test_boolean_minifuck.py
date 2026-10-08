"""The Minifuck derivation checks that stand outside any one route."""

import importlib

import pytest

from esolangs.tools.helpers import TEMPLATE_CHAR, essential_inputs, runs
from esolangs.tools.minifuck.mux import (
    _MUX_MIN_ARITY,
    _MUX_PRESERVE_RIGHT,
    _SCULPT_POOL_CODE,
    _mux,
    _probe_frame,
)
from esolangs.tools.minifuck.pool import _POOL_MASK
from esolangs.tools.minifuck.sim import PAIR, _runs, _Sim
from tests.tools.minifuck_support import _FLIP, _embed, _mux_separate, run_count


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
