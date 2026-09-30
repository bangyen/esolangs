"""Executed controls for the additional research tracks."""

import itertools
from collections import Counter

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.fractran import run
from esolangs.interpreters.tape_based.brainfuck import _Machine
from esolangs.tools.circuit_diagram import _LATTICE, _h_size


def test_h_side_closed_form() -> None:
    for k in range(64):
        assert _h_size(2 * k) == _LATTICE * (12 * 2**k - 4 * k - 10)
        assert _h_size(2 * k + 1) == _LATTICE * (14 * 2**k - 4 * k - 12)
        assert _h_size(2 * k) ** 2 < 144 * _LATTICE**2 * 2 ** (2 * k)
        assert _h_size(2 * k + 1) ** 2 < 144 * _LATTICE**2 * 2 ** (2 * k + 1)


@pytest.mark.medium
def test_fraction_order_encodes_four_independent_answers() -> None:
    primes = (3, 5, 7, 11)
    vocabulary = Counter(f"{answer}/{p}" for p in primes for answer in (1, 2))
    for table in itertools.product("01", repeat=4):
        fractions = []
        for p, bit in zip(primes, table, strict=True):
            pair = [f"1/{p}", f"2/{p}"]
            fractions.extend(pair if bit == "0" else pair[::-1])
        assert Counter(fractions) == vocabulary
        for p, bit in zip(primes, table, strict=True):
            io = ScriptedIO("")
            run(str(p) + " " + " ".join(fractions), io)
            assert io.getvalue().strip() == str(1 + int(bit))
    # Neither rule is applicable outside the selected row vocabulary.
    io = ScriptedIO("")
    run("13 " + " ".join(fractions), io)
    assert io.getvalue().strip() == "13"


@pytest.mark.medium
def test_ordered_reads_retain_four_stores_at_one_cursor() -> None:
    states = []
    for prefix in itertools.product("01", repeat=2):
        io = ScriptedIO("\n".join((*prefix, "0")))
        machine = _Machine(",>,>,<<.", io)
        while io.reads < 2:
            machine.step()
        states.append(machine.snapshot())
        while not machine.halted:
            machine.step()
        assert io.getvalue() == prefix[0]
    assert len(set(states)) == 4
    assert len({state[0] for state in states}) == 1


@pytest.mark.medium
def test_bounded_input_census_distinguishes_read_observations() -> None:
    inputs = [bits for n in range(3) for bits in itertools.product((0, 1), repeat=n)]
    seen: list[set[tuple[object, ...]]] = [set(), set(), set()]
    for length in range(4):
        for commands in itertools.product("><+-.,", repeat=length):
            behavior = []
            for bits in inputs:
                io = ScriptedIO("\n".join(chr(bit) for bit in bits))
                machine = _Machine("".join(commands), io)
                try:
                    while not machine.halted:
                        machine.step()
                    behavior.append(("halt", io.getvalue()))
                except EOFError:
                    behavior.append(("EOF",))
            for m in range(3):
                seen[m].add(tuple(behavior[: 2 ** (m + 1) - 1]))
    assert [len(values) for values in seen] == [13, 23, 27]
