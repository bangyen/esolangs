"""One sweep for the claim every boolean generator makes.

A boolean generator's whole contract is that its program computes the
truth table it was given.  Eight test modules asserted that by hand, once
per language, with the same six lines each -- build the program, walk
every input combination, run it, compare against the table -- so the
comprehension that turns a row index into bits appeared ninety-seven
times and the NOT/XOR/AND/NAND3 table it was fed appeared fifty-six.

The data those copies varied over is already written down.
:data:`~esolangs.tools.boolean.examples.BOOLEAN_EXAMPLES` pairs every
generator with the interpreter that runs it, whether the program is split
into lines, what the answer looks like when it arrives, and -- for the
languages with no input command -- the ``fill`` that embeds a bit in the
template.  That table is maintained for the committed examples, so the
sweep here reads it rather than growing a second copy that could drift
from it.

What stays per module is what the copies were *also* doing: a language's
own edge tables, its arity caps, the shapes its construction folds, the
sizes it must not exceed.  This replaces the copied shape, not the
language's own coverage -- the same split
:mod:`tests.interpreters.contract` draws.

The tables swept are small on purpose.  Every generator is checked over
every table up to two inputs and a fixed set at three, which is where a
construction that mishandles a constant row, a single-variable row, or a
full tree shows it; the wider arities that cost real time stay in the
per-language modules that know which of them are worth paying for.
"""

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

#: Every table over one and two inputs, then a set at three chosen for the
#: shapes a tree can get wrong: constant, one-variable, parity, majority,
#: AND, OR, and the two NANDs.
_TABLES: list[str] = [
    *(format(i, "02b") for i in range(4)),
    *(format(i, "04b") for i in range(16)),
    "00000000",
    "11111111",
    "00001111",
    "01010101",
    "10010110",  # parity
    "00010111",  # majority
    "00000001",  # AND3
    "11111110",  # NAND3
    "01111111",  # OR3
]


def _arity(table: str) -> int:
    return len(table).bit_length() - 1


def _run(example: BooleanExample, program: str, stdin: str) -> str:
    """Run one generated program through the language's own interpreter."""
    module = importlib.import_module("esolangs.interpreters." + example.interpreter)
    io = ScriptedIO(stdin)
    argument = program.splitlines() if example.split else program
    extra = dict(example.kwargs)
    # ``seed`` is not an argument to ``run``: it names the draw a language
    # whose spec makes something random -- LaserFuck's initial heading --
    # must be pinned to, so it arrives as the randomness source itself.
    if "seed" in extra:
        from esolangs.interpreters.randomness import Seeded

        extra["rng"] = Seeded(extra.pop("seed"))
    module.run(argument, io=io, **extra)
    return io.getvalue()


def _answer(example: BooleanExample, got: str) -> str:
    """Strip the shape the language's output convention adds.

    ``expected`` is what the committed example prints for a *known* bit,
    so its trailing newline -- Inject's ``send`` terminator, APL's
    statement print -- is the convention rather than the answer.  Removing
    exactly that suffix leaves the digit the table is compared against.
    """
    suffix = example.expected[1:]
    return got[: -len(suffix)] if suffix and got.endswith(suffix) else got


def _stdin(name: str, bits: list[int]) -> str:
    """Spell ``bits`` the way this language's interpreter reads them.

    The per-language facts -- Grapheme's ``%``/``A``, Clockwise's single
    line, Fargo's row index, Taglate's ghost digit and missing trailing
    newline -- used to be four frozensets right here, and that was the
    problem: a caller of the library had no way to reach them, so each was
    rediscovered as a silently wrong answer.  They now live on the example
    entries and this delegates, which also means the sweep and the shipped
    encoder cannot disagree about what a language reads.
    """
    return encode_inputs(_DISPLAY_NAME[name], bits)


#: Example stem -> registry display name, which is what the public API takes.
_BY_ID = {lang.id: name for name, lang in LANGUAGES.items()}
_DISPLAY_NAME = {
    stem: _BY_ID[canonical_id(stem.replace("-", " "))] for stem in BOOLEAN_EXAMPLES
}


def _combination(
    name: str, example: BooleanExample, program: str, bits: list[int]
) -> str:
    """Present ``bits`` to a program the way its language takes them."""
    if example.fill is not None:
        return _run(example, example.fill(program, bits), "")
    return _run(example, program, _stdin(name, bits))


#: Languages the sweep cannot drive, with the reason.  Each is exercised by
#: its own module instead; the completeness test below pins that this set
#: names only real generators, so an entry cannot outlive its cause.
_NOT_SWEPT: dict[str, str] = {
    # Its implicit loop has no halting state -- a repeated snapshot is the
    # language's stop -- so a plain ``run`` never returns.  Its own module
    # drives the VM to the cycle and renders the grid.
    "a-painter-ant": "halts by cycling, not by reaching a halt state",
    # Reads until the input runs out and treats the EOFError as its halt,
    # so the answer arrives through an exception rather than a return.
    "suffolk": "stops on EOF rather than halting",
    # Halts by exiting the process, which a sweep cannot catch per row.
    "container": "halts by exiting with status 0",
    # Answers by halting or looping forever rather than by printing, so
    # there is no output to compare a row against.
    "point-break": "answers by termination, not by output",
    "123": "answers by termination, not by output",
    # The dumping languages print their whole final state -- a tape, a
    # register list, a queue, a RAM map -- and which part of that dump is
    # the answer is a fact about the language, not a suffix a sweep can
    # strip.  Their own modules read the cell they wrote.
    "back": "dumps its tape, so the answer is a cell rather than the output",
    "ram0": "dumps its machine, so the answer is a register rather than the output",
    "minsky-swap": "dumps its registers, so the answer is one of them",
    "arrowqueue": "dumps its queue, so the answer is one of its cells",
    "bitdeque": "dumps its deque, so the answer is one of its cells",
}


def _sweepable() -> list[str]:
    return sorted(set(BOOLEAN_EXAMPLES) - set(_NOT_SWEPT))


@pytest.mark.parametrize("name", _sweepable())
def test_the_generated_program_computes_its_table(name: str) -> None:
    """Every row of every small table comes back as the table says.

    This is the generators' one shared claim, so a new generator is held
    to it by appearing in ``BOOLEAN_EXAMPLES`` -- there is no second list
    to remember.
    """
    example = BOOLEAN_EXAMPLES[name]
    for table in _TABLES:
        n = _arity(table)
        try:
            program = example.generator(table)
        except ValueError:
            # A generator may document an arity or shape it refuses; the
            # refusal itself is its own module's to pin.
            continue
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = _answer(example, _combination(name, example, program, bits))
            assert got == table[combo], f"{name} {table} inputs {bits} gave {got!r}"


@pytest.mark.parametrize("name", sorted(BOOLEAN_EXAMPLES))
def test_a_table_of_the_wrong_length_is_refused(name: str) -> None:
    """A truth table whose length is not a power of two builds nothing.

    Every generator validates through the same helper, so the message is
    one message; asserting it whole here is what keeps it that way, since
    a generator that grew its own wording would no longer be checking the
    shared claim.
    """
    with raises_message(
        ValueError,
        "truth table must have a power-of-two number of entries (2**n), got 3",
    ):
        BOOLEAN_EXAMPLES[name].generator("011")


@pytest.mark.parametrize("name", sorted(BOOLEAN_EXAMPLES))
def test_a_table_of_other_characters_is_refused(name: str) -> None:
    """A truth table carrying anything but ``0``/``1`` builds nothing."""
    with raises_message(
        ValueError, "truth table must contain only '0' and '1', got '2'"
    ):
        BOOLEAN_EXAMPLES[name].generator("02")


def test_the_sweep_covers_every_registered_generator() -> None:
    """No generator sits outside both the sweep and its exemption.

    A hard-coded roster silently deselects: the way this fails is a
    generator added to the examples table and never swept, which is
    invisible unless the two are compared.
    """
    assert set(_sweepable()) | set(_NOT_SWEPT) == set(BOOLEAN_EXAMPLES)


def test_every_exemption_names_a_real_generator() -> None:
    """An exemption whose cause is gone must not linger unnoticed."""
    assert set(_NOT_SWEPT) <= set(BOOLEAN_EXAMPLES)
