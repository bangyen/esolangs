r"""One sweep for the claim every boolean generator makes."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

import pytest

from esolangs import encode_inputs
from esolangs.interpreters.io import ScriptedIO
from esolangs.registry import LANGUAGES, canonical_id
from esolangs.tools.boolean.examples import BOOLEAN_EXAMPLES
from tests.raises import raises_message

if TYPE_CHECKING:
    from esolangs.tools.boolean.examples import BooleanExample

# : Every table over one and.
# : shapes a tree can get.
#: AND, OR, and the two NANDs.
_TABLES: list[str] = [
    *(format(i, "02b") for i in range(4)),
    *(format(i, "04b") for i in range(16)),
    "00000000",
    "11111111",
    "00001111",
    "01010101",
    "10010110",  # parity.
    "00010111",  # majority.
    "00000001",  # AND3.
    "11111110",  # NAND3.
    "01111111",  # OR3.
]


def _arity(table: str) -> int:
    return len(table).bit_length() - 1


def _run(example: BooleanExample, program: str, stdin: str) -> str:
    r"""Run one generated program through the language's own interpreter."""
    module = importlib.import_module("esolangs.interpreters." + example.interpreter)
    io = ScriptedIO(stdin)
    argument = program.splitlines() if example.split else program
    extra = dict(example.kwargs)
    # ``seed`` is not an argument.
    # whose spec makes something.
    # must be pinned to, so it.
    if "seed" in extra:
        from esolangs.interpreters.randomness import Seeded

        extra["rng"] = Seeded(extra.pop("seed"))
    module.run(argument, io=io, **extra)
    return io.getvalue()


def _answer(example: BooleanExample, got: str) -> str:
    r"""Strip the shape the language's output convention adds."""
    suffix = example.expected[1:]
    return got[: -len(suffix)] if suffix and got.endswith(suffix) else got


def _stdin(name: str, bits: list[int]) -> str:
    r"""Spell ``bits`` the way this language's interpreter reads them."""
    return encode_inputs(_DISPLAY_NAME[name], bits)


# : Example stem -> registry.
_BY_ID = {lang.id: name for name, lang in LANGUAGES.items()}
_DISPLAY_NAME = {
    stem: _BY_ID[canonical_id(stem.replace("-", " "))] for stem in BOOLEAN_EXAMPLES
}


def _combination(
    name: str, example: BooleanExample, program: str, bits: list[int]
) -> str:
    r"""Present ``bits`` to a program the way its language takes them."""
    if example.fill is not None:
        return _run(example, example.fill(program, bits), "")
    return _run(example, program, _stdin(name, bits))


# : Languages the sweep cannot.
# : its own module instead; the.
# : names only real generators,.
_NOT_SWEPT: dict[str, str] = {
    # Its implicit loop has no.
    # language's stop -- so a plain.
    # drives the VM to the cycle.
    "a-painter-ant": "halts by cycling, not by reaching a halt state",
    # Reads until the input runs.
    # so the answer arrives through.
    "suffolk": "stops on EOF rather than halting",
    # Halts by exiting the process,.
    "container": "halts by exiting with status 0",
    # Answers by halting or looping.
    # there is no output to compare.
    "point-break": "answers by termination, not by output",
    "123": "answers by termination, not by output",
    # The dumping languages print.
    # register list, a queue, a RAM.
    # the answer is a fact about.
    # strip.
    "back": "dumps its tape, so the answer is a cell rather than the output",
    "ram0": "dumps its machine, so the answer is a register rather than the output",
    "minsky-swap": "dumps its registers, so the answer is one of them",
    "arrowqueue": "dumps its queue, so the answer is one of its cells",
    "bitdeque": "dumps its deque, so the answer is one of its cells",
}


def _sweepable() -> list[str]:
    return sorted(set(BOOLEAN_EXAMPLES) - set(_NOT_SWEPT))


@pytest.mark.parametrize("name", _sweepable())
# 9.6s over the file: runs.
@pytest.mark.medium
def test_the_generated_program_computes_its_table(name: str) -> None:
    r"""Every row of every small table comes back as the table says."""
    example = BOOLEAN_EXAMPLES[name]
    for table in _TABLES:
        n = _arity(table)
        try:
            program = example.generator(table)
        except ValueError:
            # A generator may document an.
            # refusal itself is its own.
            continue
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = _answer(example, _combination(name, example, program, bits))
            assert got == table[combo], f"{name} {table} inputs {bits} gave {got!r}"


@pytest.mark.parametrize("name", sorted(BOOLEAN_EXAMPLES))
def test_a_table_of_the_wrong_length_is_refused(name: str) -> None:
    r"""A truth table whose length is not a power of two builds nothing."""
    with raises_message(
        ValueError,
        "truth table must have a power-of-two number of entries (2**n), got 3"
        "; 3 is between 2 (1 input) and 4 (2 inputs)",
    ):
        BOOLEAN_EXAMPLES[name].generator("011")


@pytest.mark.parametrize("name", sorted(BOOLEAN_EXAMPLES))
def test_a_table_of_other_characters_is_refused(name: str) -> None:
    r"""A truth table carrying anything but ``0``/``1`` builds nothing."""
    # The message echoes the.
    # character and where it is: it.
    # a reader who typed "nonsense".
    with raises_message(
        ValueError,
        "truth table must contain only '0' and '1', got '02' -- "
        "'2' at position 1 is not one of them",
    ):
        BOOLEAN_EXAMPLES[name].generator("02")


def test_the_sweep_covers_every_registered_generator() -> None:
    r"""No generator sits outside both the sweep and its exemption."""
    assert set(_sweepable()) | set(_NOT_SWEPT) == set(BOOLEAN_EXAMPLES)


def test_every_exemption_names_a_real_generator() -> None:
    r"""An exemption whose cause is gone must not linger unnoticed."""
    assert set(_NOT_SWEPT) <= set(BOOLEAN_EXAMPLES)
