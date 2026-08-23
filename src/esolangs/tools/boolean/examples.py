"""The committed boolean example programs, as data.

``examples/boolean`` holds one program per language whose boolean generator
can be verified end to end, mirroring ``examples/hello-world`` for the text
generators.  This module is the single source of truth for those files: each
:class:`BooleanExample` records the generator, the truth table, and the input
combination that produced its program, plus how the interpreter is invoked.

The example writer (``scripts/write_boolean_examples.py``) and the test that
keeps the files in sync (``tests/test_examples.py``) both derive from
:data:`BOOLEAN_EXAMPLES`, so a committed program is always exactly what its
generator produces today.

Two kinds of generator appear here:

- **Input-reading** generators return a runnable program; the harness feeds
  the input bits on stdin (``inputs``).
- **Parameterized** generators (see :mod:`esolangs.tools.boolean.parameterized`)
  return a *template* whose ``{Xi}`` placeholders must be filled with the
  language's own code for setting an input.  Those entries carry a ``fill``
  describing that substitution, and read no input at run time.

Languages whose boolean capability cannot be captured by a committed program
are absent by construction: those whose result is a machine state rather than
output (Back's cell under the head, RAM0's and Minsky Swap's register dumps,
A Painter Ant's landing cell), and those with no Python interpreter to run.
"""

from collections.abc import Callable
from dataclasses import dataclass, replace

from esolangs.registry import canonical_id
from esolangs.tools.boolean.helpers import instantiate
from esolangs.tools.boolean.parameterized import _instantiate_arrowqueue
from esolangs.tools.wrap import DEFAULT_WIDTH, takes_width, wrap_program

# Truth tables used below, named for readability.
AND2 = "0001"
XOR2 = "0110"


@dataclass(frozen=True)
class BooleanExample:
    """How one committed ``examples/boolean`` program is built and run.

    ``generator`` is called with ``table`` to produce the program (or, when
    ``fill`` is set, the template that ``fill`` instantiates with ``bits``).
    ``interpreter`` is the dotted module under ``esolangs.interpreters``,
    ``split`` passes the program as lines rather than one string, and
    ``kwargs`` holds extra ``run()`` arguments.  ``inputs`` are the stdin
    lines (empty for the parameterized languages, whose bits are embedded).
    ``expected`` is the program's whole stdout.
    """

    generator: Callable[[str], str]
    table: str
    interpreter: str
    expected: str
    inputs: tuple[str, ...] = ()
    bits: tuple[int, ...] = ()
    fill: Callable[[str, list[int]], str] | None = None
    split: bool = False
    kwargs: tuple[tuple[str, int], ...] = ()
    note: str = ""
    stem: str = ""

    def build(self, width: int | None = DEFAULT_WIDTH) -> str:
        """Return the program text this example commits.

        The committed files are wrapped to ``width`` columns so a long
        one-line program stays readable in a diff.  ``stem`` names the
        language, which is what selects the token-aware wrapper; passing
        ``width=None`` returns the generator's raw output, and a language
        with no wrapper -- the 2D ones, NoComment -- is returned unwrapped
        either way.

        A generator that lays its own program out to a width (LaserFuck
        folds its grid's straight runs) takes the width itself instead:
        :func:`~esolangs.tools.wrap.wrap_program` reflows a finished line
        and so skips a program that is already multi-line, which every such
        generator's output is.  This mirrors what :func:`esolangs.generate`
        does for the text generators.
        """
        if width is not None and takes_width(self.generator):
            program = self.generator(self.table, width)
        else:
            program = self.generator(self.table)
        if self.fill is not None:
            program = self.fill(program, list(self.bits))
        return wrap_program(program, canonical_id(self.stem.replace("-", " ")), width)


def _kw(**kwargs: int) -> tuple[tuple[str, int], ...]:
    return tuple(kwargs.items())


def _reader(
    generator: Callable[[str], str],
    interpreter: str,
    *,
    table: str = AND2,
    inputs: tuple[str, ...] = ("0", "1"),
    expected: str = "0",
    split: bool = False,
    kwargs: tuple[tuple[str, int], ...] = (),
    note: str = "",
) -> BooleanExample:
    """Build an input-reading example, whose bits are read from stdin."""
    return BooleanExample(
        generator=generator,
        table=table,
        interpreter=interpreter,
        expected=expected,
        inputs=inputs,
        split=split,
        kwargs=kwargs,
        note=note,
    )


def _embedded(
    generator: Callable[[str], str],
    interpreter: str,
    fill: Callable[[str, list[int]], str],
    *,
    table: str = AND2,
    bits: tuple[int, ...] = (0, 1),
    expected: str = "0",
    split: bool = False,
    kwargs: tuple[tuple[str, int], ...] = (),
    note: str = "",
) -> BooleanExample:
    """Build a parameterized example, whose bits are embedded in the text."""
    return BooleanExample(
        generator=generator,
        table=table,
        interpreter=interpreter,
        expected=expected,
        bits=bits,
        fill=fill,
        split=split,
        kwargs=kwargs,
        note=note,
    )


# Each ``fill`` below is the language's own way of spelling "set input i to
# this bit", the counterpart of the input read an input-capable language
# performs.  They mirror the substitutions the generator tests use.


def _fill_bio(template: str, bits: list[int]) -> str:
    n = len(bits)
    # pack each input once by its binary weight
    return instantiate(
        template,
        bits,
        lambda i, b: "0ox" * (2 ** (n - 1 - i)) if b else "",
        lambda _i, _b: "",
    )


def _fill_nocomment(template: str, bits: list[int]) -> str:
    return instantiate(
        template,
        bits,
        lambda _i, b: "c" if b == 0 else "i",
        lambda _i, b: "c" if b == 1 else "i",
    )


def _fill_lamfunc(template: str, bits: list[int]) -> str:
    # each {Xi} fills a `vs v{i}` store with the binary literal
    return instantiate(
        template,
        bits,
        lambda _i, b: "0b" + str(b),
        lambda _i, b: "0b" + str(b),
    )


def _fill_bitdeque(template: str, bits: list[int]) -> str:
    n = len(bits)
    # The register flips after every load block, so bit i is pushed at load
    # position n-1-i with incoming register (n-1-i) % 2.
    return instantiate(
        template,
        bits,
        lambda i, b: "PUSH INVERT" if b == (n - 1 - i) % 2 else "INVERT PUSH",
        lambda _i, _b: "PUSH INVERT",
    )


def _fill_bfpda(template: str, bits: list[int]) -> str:
    return instantiate(
        template,
        bits,
        lambda _i, b: "<@" if b else "<",
        lambda _i, b: "<@" if not b else "<",
    )


def _fill_home_row(template: str, bits: list[int]) -> str:
    return instantiate(
        template,
        bits,
        lambda _i, b: "a" if b else "",
        lambda _i, b: "a" if not b else "",
    )


def _fill_cod(template: str, bits: list[int]) -> str:
    # each {Xi} sets the cod's value to the bit: ')' for one, space for
    # zero, read at the start of that input's '+' fork
    return instantiate(
        template,
        bits,
        lambda _i, b: ")" if b else " ",
        lambda _i, _b: " ",
    )


def _fill_eval(template: str, bits: list[int]) -> str:
    # on the input stack (index 1), ` pushes 0 and + bumps it to 1
    return instantiate(
        template,
        bits,
        lambda _i, b: "`+" if b else "0",
        lambda _i, _b: "",
    )


def _fill_wii2d(template: str, bits: list[int]) -> str:
    return instantiate(
        template,
        bits,
        lambda _i, b: "v   " if b else ">   ",
        lambda _i, _b: "    ",
    )


def _fill_arrowqueue(template: str, bits: list[int]) -> str:
    # ArrowQueue rebuilds its whole header rather than substituting in place
    return _instantiate_arrowqueue(template, bits)


# Example file stem -> how that example is built and run.  Stems match the
# language's display name lowercased with spaces as dashes, like the
# hello-world examples.
BOOLEAN_EXAMPLES: dict[str, BooleanExample] = {}


def _register() -> None:
    from esolangs.tools import boolean as b

    reading = {
        "addsubjump": _reader(
            b.addsubjump, "register_based.addsubjump", table=XOR2, expected="1"
        ),
        "basicfuck": _reader(b.basicfuck, "tape_based.basicfuck"),
        "between": _reader(b.between, "register_based.between", split=True),
        "bfstack": _reader(b.bfstack, "stack_based.bfstack", table=XOR2, expected="1"),
        "bit~": _reader(b.bit_tilde, "tape_based.bit_tilde"),
        "brainfuck": _reader(b.brainfuck, "tape_based.brainfuck"),
        "brainif": _reader(b.brainif, "tape_based.brainif", split=True),
        "circlefuck": _reader(b.circlefuck, "tape_based.circlefuck"),
        "collatz-multiverse": _reader(
            b.collatz_multiverse, "register_based.collatz_multiverse"
        ),
        "container": _reader(
            b.container,
            "other.container",
            split=True,
            note="halts by exiting with status 0",
        ),
        "decleq": _reader(b.decleq, "register_based.decleq"),
        "dig": _reader(b.dig, "grid_based.dig", table=XOR2, expected="1", split=True),
        "dimensional": _reader(b.dimensional, "tape_based.dimensional"),
        "factor": _reader(b.factor, "tape_based.factor"),
        "flowchart": _reader(b.flowchart, "grid_based.flowchart", split=True),
        "forbin": _reader(b.forbin_boolean, "other.forbin"),
        "laserfuck": _reader(
            b.laserfuck,
            "grid_based.laserfuck",
            split=True,
            expected="\x00\x010",
            kwargs=_kw(heading=3),
            note=(
                "the initial heading is random by spec, so the example pins "
                "it; byte mode prints every touched cell, so the two input "
                "cells precede the result as NUL and SOH"
            ),
        ),
        "modulous": _reader(b.modulous, "stack_based.modulous"),
        "myscript": _reader(b.myscript, "register_based.myscript"),
        "nevermind": _reader(
            b.nevermind,
            "register_based.nevermind",
            split=True,
            expected="0\n",
            note="the language's print always adds a newline",
        ),
        "painfuck": _reader(b.painfuck, "tape_based.painfuck"),
        "point-break": _reader(
            b.point_break,
            "register_based.point_break",
            expected="",
            note=(
                "Point Break has no output: the program halts for a 0 result "
                "and loops forever for a 1, so only the halting branch is "
                "committed"
            ),
        ),
        "polynomial": _reader(b.polynomial, "register_based.polynomial"),
        "qoibl": _reader(b.qoibl, "register_based.qoibl", split=True),
        "rotfuck": _reader(b.rotfuck, "tape_based.rotfuck"),
        "s*bleq": _reader(b.sbleq, "tape_based.sbleq"),
        "sophie": _reader(b.sophie, "register_based.sophie"),
        "streetcode": _reader(b.streetcode, "grid_based.streetcode", split=True),
        "suffolk": _reader(
            b.suffolk,
            "tape_based.suffolk",
            kwargs=_kw(limit=1),
            note="run with the loop count set to one",
        ),
        "suptiftam": _reader(b.suptiftam, "other.suptiftam"),
        "3d-brainfuck": _reader(b.three_d_brainfuck, "tape_based.three_d_brainfuck"),
        "6-5": _reader(b.six_five, "tape_based.six_five"),
    }

    embedded = {
        "bfpda": _embedded(b.bfpda, "stack_based.bf_pda", _fill_bfpda),
        "bio": _embedded(b.bio, "register_based.bio", _fill_bio),
        "bitdeque": _embedded(
            b.bitdeque, "queue_based.bitdeque", _fill_bitdeque, expected="0\n"
        ),
        "cod": _embedded(
            b.cod,
            "grid_based.cod",
            _fill_cod,
            table=XOR2,
            bits=(1, 1),
            expected="0\n",
            kwargs=_kw(limit=500),
            note="COD has no runtime input and no I/O but a printed number",
        ),
        "eval": _embedded(b.eval, "stack_based.eval", _fill_eval),
        "home-row": _embedded(b.home_row, "tape_based.home_row", _fill_home_row),
        "lamfunc": _embedded(b.lamfunc, "other.lamfunc", _fill_lamfunc),
        "nocomment": _embedded(b.nocomment, "tape_based.nocomment", _fill_nocomment),
        "wii2d": _embedded(
            b.wii2d,
            "grid_based.wii2d",
            _fill_wii2d,
            bits=(1, 1),
            expected="1",
            split=True,
        ),
        "arrowqueue": _embedded(
            b.arrowqueue,
            "grid_based.arrowqueue",
            _fill_arrowqueue,
            expected="",
            split=True,
            note=(
                "ArrowQueue has no output: the program halts for a 0 result and "
                "loops forever for a 1, so only the halting branch is committed"
            ),
        ),
    }

    # Stamp each example with its own stem, so ``build()`` knows which
    # language it is and can pick the matching token-aware wrapper without
    # the caller having to supply it.
    for stem, example in {**reading, **embedded}.items():
        BOOLEAN_EXAMPLES[stem] = replace(example, stem=stem)


_register()

# Committed programs that no current generator produces, so they are run as
# behaviour tests but exempt from the generator-match check.  Minifuck's
# boolean generator covered the 0-preserving two-input tables and has since
# been removed; the program is kept as a record of that construction.
HAND_WRITTEN: dict[str, tuple[str, tuple[str, ...], str, bool]] = {
    # stem -> (interpreter, inputs, expected, split)
    "minifuck": ("tape_based.minifuck", ("0", "1"), "0", False),
}

__all__ = ["AND2", "BOOLEAN_EXAMPLES", "HAND_WRITTEN", "XOR2", "BooleanExample"]
