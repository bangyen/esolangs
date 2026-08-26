"""The committed boolean example programs, as data.

``examples/boolean`` holds one program per language whose boolean generator
can be verified end to end, mirroring ``examples/hello-world`` for the text
generators.  This module is the single source of truth for those files: each
:class:`BooleanExample` records the generator, the truth table, and the input
combination that produced its program, plus how the interpreter is invoked.

The example writer (``scripts/write_examples.py``) and the test that
keeps the files in sync (``tests/scripts/test_examples.py``) both derive from
:data:`BOOLEAN_EXAMPLES`, so a committed program is always exactly what its
generator produces today.

Two kinds of generator appear here:

- **Input-reading** generators return a runnable program; the harness feeds
  the input bits on stdin (``inputs``).
- **Parameterized** generators (see :mod:`esolangs.tools.boolean.parameterized`)
  return a *template* whose ``{Xi}`` placeholders must be filled with the
  language's own code for setting an input.  Those entries carry a ``fill``
  describing that substitution, and read no input at run time.

A language qualifies for an example when its answer is *recoverable from
what the program prints*.  That is a weaker test than "prints the answer and
nothing else", and deliberately so: several languages here have no output
instruction at all and simply dump their state when they halt, so the answer
arrives surrounded by the rest of that state.  Minsky Swap dumps its
registers and the answer is the second one; RAM0 dumps its whole machine and
the answer is ``z``; LaserFuck prints every touched tape cell, so the input
cells precede the result.  Each is a fixed position in a stable dump, which
is a contract a committed file can hold, so each has an example.

Two languages used to fail that test and no longer do.  Back's answer was
the cell *under the head*, which the tape dump does not locate; the
generator now writes the result into a single answer cell, so the dump
reports it like any other.  A Painter Ant's answer is which of two painted
leaf rings the ant rests in, and the interpreter's raster drew painted cells
only, so the ant was invisible and the rings identical; ``render`` now marks
the ant's own cell, with ``o`` on black and ``@`` on white.

Every boolean generator whose answer a program can report therefore has a
committed example.
"""

from collections.abc import Callable
from dataclasses import dataclass, replace

from esolangs.registry import Generator, canonical_id
from esolangs.tools.boolean.a_painter_ant import _instantiate_apa
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

    generator: Generator
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
    """Pack each input into ``x`` by its binary weight, in a constant width.

    A one adds the input's weight to ``x``; a zero writes the same number of
    commands to ``z``, which the generator never reads, so both bits embed
    as the same number of characters and the program's shape no longer
    reveals its inputs.

    This used to embed a zero as nothing at all, which made the program's
    length reveal its inputs: at ``n == 2`` the four instantiations ran to
    236, 240, 244, and 248 characters.  Padding with spaces instead of
    ``0oz;`` also works -- :func:`~esolangs.interpreters.register_based.bio.parse`
    discards whitespace before checking that nothing but commands is left --
    but it pads with characters the language ignores, which is what the
    bf-pda separators were.  ``y`` is not available for the padding: it
    carries the running result.
    """
    n = len(bits)
    return instantiate(
        template,
        bits,
        lambda i, b: ("0ox;" if b else "0oz;") * (2 ** (n - 1 - i)),
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
    """Push the bit, in a constant width.

    ``<`` pushes a zero and ``@`` flips the top, so a one is a flip more
    than a zero.  Padding to a common width takes four characters, the
    shortest length at which both bits can be written: ``<@@@`` flips three
    times to a one, and ``<[@]`` skips its own body, since ``[`` peeks the
    zero just pushed and jumps past the matching ``]``.

    This used to spell a zero as ``<`` and a one as ``<@``, which made the
    program's length reveal its inputs.  Four is minimal: an exhaustive
    search over ``<>@[]`` for runs that push exactly one value finds only a
    zero at one character, only a one at two, and only zeros at three.
    Padding with a comment character would be shorter, but every character
    outside ``@.<>[]`` is a comment here, so that is the padding the
    separators removed from this generator already were.
    """
    return instantiate(
        template,
        bits,
        lambda _i, b: "<@@@" if b else "<[@]",
        lambda _i, b: "<@@@" if not b else "<[@]",
    )


def _fill_back(template: str, bits: list[int]) -> str:
    """Set each input cell: ``-`` flips it to one, ``+`` leaves it zero.

    The beam reads one cell per row as it runs up column 0, so a setter is
    one command and the template gives each input a second row for the
    ``+`` that pads it.  ``+`` steps the beam only when the current cell is
    zero, and here that cell is the answer cell the tree has yet to reach,
    so the step is inert whichever bit was set.  A zero used to embed as a
    blank, which the beam ignores just as happily -- but the fill rstrips,
    so that row vanished and the program's size carried the input: at
    ``n == 2`` the four instantiations were 41, 42, and 43 characters over
    six or seven rows, where they are now all 47 over nine.  Contrast
    :func:`_fill_cod`, whose blank is a grid cell that cannot be stripped
    and so leaks nothing.
    """
    return instantiate(
        template,
        bits,
        lambda _i, b: "-" if b else "+",
        lambda _i, b: "-" if b else "+",
    )


def _fill_minsky_swap(template: str, bits: list[int]) -> str:
    """Set each input register by counting ``+`` against a ``*`` pad.

    Minsky Swap has no input instruction, so a bit is embedded as the
    register's starting value.  Every setter is padded to the same width
    (``2**n``, or four for the LSB, which needs no ``~``) so the jump
    targets the template computed stay correct whatever the bits are.
    """
    n = len(bits)
    size: int = 2**n

    def set_bit(i: int, bit: int) -> str:
        if i == n - 1:  # LSB: length-4 block, no "~"
            return "+*+*" if bit else "****"
        weight: int = 2 ** (n - 1 - i)
        if bit:
            return "+" * weight + "*" * (size - weight)
        return "*" * size

    return instantiate(template, bits, set_bit, lambda _i, _b: "*" * size)


def _fill_ram0(template: str, bits: list[int]) -> str:
    """Set each input cell with ``Z A`` for a one and ``Z Z`` for a zero.

    ``Z`` resets absolutely rather than relative to the incoming register,
    so the same two-command setter works at every position.
    """
    return instantiate(
        template,
        bits,
        lambda _i, b: "Z A" if b else "Z Z",
        lambda _i, _b: "Z Z",
    )


def _fill_home_row(template: str, bits: list[int]) -> str:
    """Set the bit cell, in a constant width.

    The cell is zero when a ``{Xi}`` is reached, so ``a`` raises it to one
    and the second character settles it without moving the pointer: ``s``
    puts it back to zero, while ``j`` only skips the instruction after it
    when the cell is zero -- which it is not, having just been raised -- so
    ``aj`` leaves a one.  Both bits are therefore two characters, and the
    program's shape no longer reveals its inputs.

    This used to spell a one as ``a`` and a zero as nothing at all, which
    made the program's length reveal its inputs.  The padding has to leave
    the cell's value alone *and* the pointer where it was: ``{Xi}`` sits
    directly before a gate that tests this cell, so a pad that moves the
    pointer (``d``/``f``) or changes the count (a second ``a``) misroutes
    the gate rather than being inert.  Padding with spaces (``a`` against
    two blanks) works, since the interpreter ignores whitespace, but it
    pads with characters the language does not read.
    """
    return instantiate(
        template,
        bits,
        lambda _i, b: "aj" if b else "as",
        lambda _i, b: "aj" if not b else "as",
    )


def _fill_cod(template: str, bits: list[int]) -> str:
    """Set the cod's value to the bit at that input's ``+`` fork.

    ``)`` increments, so a one is ``)`` and a zero is a space -- which is
    water, an open grid cell the cod passes through, not the inert filler a
    space is in a language that ignores unknown characters.  Both bits are
    one cell, so the programs are already all the same size and differ in
    exactly one character per input, at a fixed column: 89 characters at
    ``n == 1``, 350 at ``n == 2``, 1495 at ``n == 3``, whatever the inputs.

    Spelling the zero as a command instead (``)(`` against ``)<``) works --
    it needs the fork box widened by a column and one more of the cascade's
    leading blanks -- but it buys nothing here and costs size: 350 goes to
    359 and 1495 to 1529.  The blank is the grid's own zero, not padding.
    """
    return instantiate(
        template,
        bits,
        lambda _i, b: ")" if b else " ",
        lambda _i, _b: " ",
    )


def _fill_eval(template: str, bits: list[int]) -> str:
    """Stage the bit on the tree stack, then move it to the input stack.

    The backtick pushes ``1 - ptr``, so on stack 0 it pushes a one where
    ``0`` pushes a zero -- a one-character setter either way.  ``=`` then
    moves it to the input stack the nodes read, so both bits embed as two
    characters and the program's shape does not reveal its inputs.

    This used to push straight onto the input stack, where the backtick
    yields a zero, so a one needed a second character (``` `+ ```) and a
    zero only one.  Staging on the tree stack is what makes both bits one
    character before the shared ``=``.  Padding the old zero to ``0 ``
    also works, since the interpreter skips anything outside its command
    set, but it pads with a character the language ignores.  An all-command
    pad is not available: every ``{Xi}`` must push exactly one value, and a
    spare ``0`` leaves a residue that a later node reads as a bit.
    """
    return instantiate(
        template,
        bits,
        lambda _i, b: "`=" if b else "0=",
        lambda _i, _b: "",
    )


def _fill_wii2d(template: str, bits: list[int]) -> str:
    """Set each junction: ``v`` takes the 1-branch, ``>`` continues east.

    The junction is one cell and the start digit beside it is one more, so
    the slot is two columns wide -- the placeholder's own four characters
    are how it is spelled, not how much grid it needs.
    """
    return instantiate(
        template,
        bits,
        lambda _i, b: "v " if b else "> ",
        lambda _i, _b: "  ",
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
        "circuit_diagram": _reader(
            b.circuit_diagram,
            "grid_based.circuit_diagram",
            split=True,
        ),
        "clockwise": _reader(
            b.clockwise,
            "grid_based.clockwise",
            split=True,
        ),
        "decleq": _reader(b.decleq, "register_based.decleq"),
        "dig": _reader(b.dig, "grid_based.dig", table=XOR2, expected="1", split=True),
        "dimensional": _reader(b.dimensional, "tape_based.dimensional"),
        "factor": _reader(b.factor, "tape_based.factor"),
        "flowchart": _reader(b.flowchart, "grid_based.flowchart", split=True),
        "forbin": _reader(b.forbin_boolean, "other.forbin"),
        "forþ": _reader(b.forth, "stack_based.forth"),
        "grapheme": _reader(b.grapheme, "stack_based.grapheme"),
        "jaune": _reader(b.jaune, "tape_based.jaune"),
        "laserfuck": _reader(
            b.laserfuck,
            "grid_based.laserfuck",
            split=True,
            expected="0",
            kwargs=_kw(heading=3),
            note="the initial heading is random by spec, so the example pins it",
        ),
        "modulous": _reader(b.modulous, "stack_based.modulous"),
        "myscript": _reader(b.myscript, "register_based.myscript"),
        "nevermind": _reader(
            b.nevermind,
            "register_based.nevermind",
            split=True,
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
        "taglate": _reader(b.taglate, "queue_based.taglate", split=True),
        "unsquare": _reader(b.unsquare, "stack_based.unsquare"),
        "ztoalc-l": _reader(b.ztoalc_l_boolean, "other.ztoalc_l", split=True),
        "3d-brainfuck": _reader(b.three_d_brainfuck, "tape_based.three_d_brainfuck"),
        "3x": _reader(b.three_x, "stack_based.three_x"),
        "6-5": _reader(b.six_five, "tape_based.six_five"),
    }

    embedded = {
        "a-painter-ant": _embedded(
            b.a_painter_ant,
            "grid_based.a_painter_ant",
            _instantiate_apa,
            expected=(
                "..#......\n.........\n.........\n.........\n.........\n"
                ".........\n..#...#..\n.###.###.\n##o###.##\n.###.###.\n"
                "..#...#.."
            ),
            note=(
                "A Painter Ant has no output: it paints a grid and the answer "
                "is which of the two leaf rings the ant rests in, shown by "
                "'o' (on black, a zero) or '@' (on white, a one)"
            ),
        ),
        "back": _embedded(
            b.back,
            "tape_based.back",
            _fill_back,
            split=True,
            expected="0 1 0",
            note=(
                "Back has no output instruction and dumps its tape at halt; "
                "the answer is cell n, past the n input cells"
            ),
        ),
        "bf-pda": _embedded(b.bfpda, "stack_based.bf_pda", _fill_bfpda),
        "bio": _embedded(b.bio, "register_based.bio", _fill_bio),
        "bitdeque": _embedded(b.bitdeque, "queue_based.bitdeque", _fill_bitdeque),
        "cod": _embedded(
            b.cod,
            "grid_based.cod",
            _fill_cod,
            table=XOR2,
            bits=(1, 1),
            kwargs=_kw(limit=500),
            note="COD has no runtime input and no I/O but a printed number",
        ),
        "eval": _embedded(b.eval, "stack_based.eval", _fill_eval),
        "home-row": _embedded(b.home_row, "tape_based.home_row", _fill_home_row),
        "lamfunc": _embedded(b.lamfunc, "other.lamfunc", _fill_lamfunc),
        "minsky-swap": _embedded(
            b.minsky_swap,
            "register_based.minsky_swap",
            _fill_minsky_swap,
            expected="0 0",
            note=(
                "Minsky Swap has no output instruction and dumps its "
                "registers at halt; the answer is the second one"
            ),
        ),
        "nocomment": _embedded(b.nocomment, "tape_based.nocomment", _fill_nocomment),
        "ram0": _embedded(
            b.ram0,
            "register_based.ram0",
            _fill_ram0,
            expected="z: 0\nn: 1\nram: {\n    0: 0,\n    1: 1\n}",
            note=(
                "RAM0 has no output instruction and dumps its whole state "
                "at halt; the answer is the 'z' register"
            ),
        ),
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
