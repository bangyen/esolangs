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

Three languages answer with their *termination* instead of their output.
ArrowQueue, Point Break and 123 have no output instruction at all: each
halts for a 0 and loops forever for a 1, so the committed program is the
halting branch and its expected output is empty.  The looping branch is not
executed, and the convention is the whole answer -- 123's ``1,0`` row halts
too but prints a stray ``0x80`` on the way out, so the committed row is one
whose halt is silent.

Fargo takes its inputs differently from every other reader here.  It reads
a single *number* before the program starts and ``@ k`` indexes that
number's bits, so the committed input is the row index -- one line, ``1``
for the ``0,1`` row of a two-input table -- rather than a line per bit.

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

# The committed programs all witness the same two-input function and row:
# AND2 evaluated on 0,1.  The generator suites cover the other tables and
# rows; keeping this corpus uniform makes the files directly comparable.
AND2 = "0001"


@dataclass(frozen=True)
class BooleanExample:
    """How one committed ``examples/boolean`` program is built and run.

    ``generator`` is called with ``table`` to produce the program (or, when
    ``fill`` is set, the template that ``fill`` instantiates with ``bits``).
    ``interpreter`` is the dotted module under ``esolangs.interpreters``,
    ``split`` passes the program as lines rather than one string, and
    ``kwargs`` holds extra ``run()`` arguments.  Those are ints, so a
    language needing a *source of chance* pinned -- LaserFuck, whose
    initial heading is drawn -- names ``seed`` and the runner turns it into
    a ``Seeded``; there is no way to spell an object in this field, and a
    seed is the reproducible thing worth committing anyway.  ``inputs`` are
    the stdin lines (empty for the parameterized languages, whose bits are
    embedded).
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
    )


def _fill_nocomment(template: str, bits: list[int]) -> str:
    return instantiate(
        template,
        bits,
        lambda _i, b: "c" if b == 0 else "i",
    )


def _fill_lamfunc(template: str, bits: list[int]) -> str:
    # each {Xi} fills a `vs v{i}` store with the binary literal
    return instantiate(
        template,
        bits,
        lambda _i, b: "0b" + str(b),
    )


def _fill_bitdeque(template: str, bits: list[int]) -> str:
    # The register flips after every load block, and the load pushes the
    # inputs in name order, so bit i is pushed at load position i with the
    # incoming register at i % 2.
    return instantiate(
        template,
        bits,
        lambda i, b: "PUSH INVERT" if b == i % 2 else "INVERT PUSH",
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
    )


def _fill_back(template: str, bits: list[int]) -> str:
    """Finish each input cell: ``+`` leaves the one, ``-`` flips it to zero.

    The beam reads one cell per row as it runs up column 0, so setting a
    cell takes two rows.  The template writes the first as a constant ``-``
    that primes the cell to 1 whatever the bit is, and this fill supplies
    the second, which finishes the job against a cell already holding 1: a
    one bit embeds ``+``, inert on a set cell, and a zero bit embeds ``-``,
    flipping it back down.  So the pointer is on input cell ``i`` throughout
    -- never the answer cell, which the tree reaches only later.

    Priming first is what makes both rows *execute*.  ``+`` steps the beam
    an extra cell when the current cell is zero, so the older ``{Xi}`` +
    ``+`` order had a zero bit's ``+`` setter fire on the still-zero cell
    and skip its own pad row; the pair cost two rows but only ever ran one
    of them, and which one depended on the bit.  Against a primed cell no
    ``+`` ever fires, so both rows run for either bit and the ``>`` past
    them is reached the same way.

    A zero used to embed as a blank, which the beam ignores just as happily
    -- but the fill rstrips, so that row vanished and the program's size
    carried the input: at ``n == 2`` the four instantiations were 41, 42,
    and 43 characters over six or seven rows, where they are now all 47
    over nine.  Contrast :func:`_fill_cod`, whose blank is a grid cell that
    cannot be stripped and so leaks nothing.
    """
    return instantiate(
        template,
        bits,
        lambda _i, b: "+" if b else "-",
    )


def _fill_minsky_swap(template: str, bits: list[int]) -> str:
    """Set each input register by counting ``+`` against a ``*`` pad.

    Minsky Swap has no input instruction, so a bit is embedded as a run of
    ``+`` adding its binary weight to ``reg[0]``, padded with ``*`` to a
    length the template counted on when it computed its jump targets.  Both
    runs are even because ``*`` swaps the register pointer: an odd pad would
    leave every later command addressing the wrong register.

    The LSB is the exception, and not merely a shorter one.  Its block is
    ``+*+*``, which adds its weight of one to ``reg[0]`` and then, across
    the swap, leaves ``reg[1]`` holding the LSB as well -- the leaves flip
    that copy into the answer, so the dump reads ``0 {answer}``.  Writing it
    as the general rule would give ``+`` and an odd pad, which both loses
    the ``reg[1]`` copy and strands the pointer.  A zero LSB is ``****``,
    the same four commands doing nothing.
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

    return instantiate(template, bits, set_bit)


def _fill_ram0(template: str, bits: list[int]) -> str:
    """Set each input cell with ``Z A`` for a one and ``Z Z`` for a zero.

    ``Z`` resets absolutely rather than relative to the incoming register,
    so the same two-command setter works at every position.
    """
    return instantiate(
        template,
        bits,
        lambda _i, b: "Z A" if b else "Z Z",
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
    )


def _fill_wii2d(template: str, bits: list[int]) -> str:
    """Set each junction: ``v`` takes the 1-branch, ``>`` continues east.

    A junction is a single cell, so the embed is one character with no
    padding -- the placeholder's own four characters are how it is spelled,
    not how much grid it needs.  The slot used to reserve a second column
    for "the start digit beside it", but the start digit sits at column 1
    and precedes junction 0 alone; every junction's second column was blank
    travel on row 0, which the pointer crosses just as happily without.
    The 1-branch's ops do start one column past the junction, but that is
    on the detour row below, so row 0 never needed the room.
    """
    return instantiate(
        template,
        bits,
        lambda _i, b: "v" if b else ">",
    )


def _fill_minifuck(template: str, bits: list[int]) -> str:
    """Write each bit at ``ptr+1``: ``[<`` for a one, ``xx`` for a zero.

    ``[`` steps right and flips the cell it lands on, and ``<`` steps back,
    so ``[<`` leaves a one beside the pointer without moving it.  ``xx`` is
    two no-ops -- characters outside ``<.[`` are ignored -- so it leaves the
    cell zero and the pointer likewise unmoved.

    Both spellings are two characters, which is the point: an unequal embed
    would make the program's *length* a function of its inputs, leaking the
    very bits it is meant to be evaluating.  The pad is a no-op the language
    executes rather than one it merely ignores, so a cleanup pass that
    stripped dead characters could not reintroduce the leak.
    """
    return instantiate(
        template,
        bits,
        lambda _i, b: "[<" if b else "xx",
    )


def _fill_one_two_three(template: str, bits: list[int]) -> str:
    """Embed each bit as the generator's own ``ONE``/``ZERO`` command.

    123 names the two spellings itself rather than leaving them to a
    convention here, so this reads them from the generator instead of
    repeating the characters -- the pair is one edit away from changing and
    a copy would not follow it.  Both are a single command, so the
    instantiations share a length.
    """
    from esolangs.tools.boolean.one_two_three import ONE, ZERO

    return instantiate(template, bits, lambda _i, b: ONE if b else ZERO)


def _fill_pct_squared_minus_one(template: str, bits: list[int]) -> str:
    """Substitute each bit's setter, named by the template's own header.

    %^2^-1 solves its setters per truth table rather than fixing them by the
    language, so there is no table-independent spelling of "set input i to
    this bit" to pass to :func:`instantiate`.  The template carries the two
    branches for each input in a header, and the generator's own filler
    reads it -- the same structure-aware arrangement ArrowQueue needs.  Both
    branches are equal width, so the instantiations share a length.
    """
    from esolangs.tools.boolean.pct_squared_minus_one import fill

    return fill(template, bits)


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
        "addsubjump": _reader(b.addsubjump, "register_based.addsubjump"),
        # An executed line prints its result and nothing else, so the
        # answer arrives with the newline that ends that line.
        "algebraic-programming-language": _reader(
            b.algebraic_programming_language,
            "other.algebraic_programming_language",
            expected="0\n",
            note="an executed line prints its result, so the answer ends in a newline",
        ),
        "basicfuck": _reader(b.basicfuck, "tape_based.basicfuck"),
        "between": _reader(b.between, "register_based.between", split=True),
        "bfstack": _reader(b.bfstack, "stack_based.bfstack"),
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
        # ``send`` terminates every line it writes, so the answer arrives
        # with a newline after it -- there is no other output command.
        "inject": _reader(
            b.inject,
            "other.inject",
            expected="0\n",
            note="send terminates each line, so the answer ends in a newline",
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
        "cvnc": _reader(b.cvnc, "other.cvnc"),
        "decleq": _reader(b.decleq, "register_based.decleq"),
        "dig": _reader(b.dig, "grid_based.dig", split=True),
        "dimensional": _reader(b.dimensional, "tape_based.dimensional"),
        "factor": _reader(b.factor, "tape_based.factor"),
        # Fargo reads one *number* before the program starts, not a bit per
        # line, and ``@ k`` indexes that number's bits.  The boolean
        # convention is therefore to feed the row index: the inputs
        # most-significant-first are its binary digits, so the 0,1 row of a
        # two-input table is the single line "1".
        "fargo": _reader(
            b.fargo,
            "other.fargo",
            inputs=("1",),
            note="Fargo reads one number whose bits are the inputs, so the "
            "committed input is the row index rather than a bit per line",
        ),
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
            kwargs=_kw(seed=0),
            note=(
                "the initial heading is random by spec, so the example pins "
                "the source it is drawn from: seed 0 draws heading 3"
            ),
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
        "slow-acv-mammalian": _reader(
            b.slow_acv_mammalian_boolean, "tape_based.slow_acv_mammalian"
        ),
        "sophie": _reader(b.sophie, "register_based.sophie"),
        "streetcode": _reader(b.streetcode, "grid_based.streetcode", split=True),
        "super-snusp": _reader(b.super_snusp, "grid_based.super_snusp", split=True),
        "suffolk": _reader(b.suffolk, "tape_based.suffolk"),
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
            expected="1 0 0",
            note=(
                "Back has no output instruction and dumps its tape at halt; "
                "the answer is cell n, past the n input cells -- which the "
                "reorder may hold in either order, so only cell n is pinned"
            ),
        ),
        "bf-pda": _embedded(b.bfpda, "stack_based.bf_pda", _fill_bfpda),
        "bio": _embedded(b.bio, "register_based.bio", _fill_bio),
        "bitdeque": _embedded(b.bitdeque, "queue_based.bitdeque", _fill_bitdeque),
        "cod": _embedded(
            b.cod,
            "grid_based.cod",
            _fill_cod,
            note="COD has no runtime input and no I/O but a printed number",
        ),
        "eval": _embedded(b.eval, "stack_based.eval", _fill_eval),
        "home-row": _embedded(b.home_row, "tape_based.home_row", _fill_home_row),
        "lamfunc": _embedded(b.lamfunc, "other.lamfunc", _fill_lamfunc),
        "minifuck": _embedded(b.minifuck, "tape_based.minifuck", _fill_minifuck),
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
            split=True,
        ),
        "pct-squared-minus-one": _embedded(
            b.pct_squared_minus_one,
            "register_based.pct_squared_minus_one",
            _fill_pct_squared_minus_one,
        ),
        # 123 answers with the termination convention, as ArrowQueue does, so
        # only the halting (0) branch is committed.  The 1,0 row halts too but
        # prints a stray 0x80 on its way out; 0,1 halts silently, so it is the
        # row whose committed output is the clean empty string.
        "123": _embedded(
            b.one_two_three,
            "tape_based.one_two_three",
            _fill_one_two_three,
            expected="",
            note=(
                "123 has no output: the program halts for a 0 result and loops "
                "forever for a 1, so only the halting branch is committed"
            ),
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
# behaviour tests but exempt from the generator-match check.
#
# Empty since Minifuck's entry was retired.  That program was the last
# hand-written one: it read its inputs at runtime, the construction the old,
# removed generator used, and was kept as the only committed record of that
# reading model.  Minifuck's shipped generator is parameterized and embeds
# its inputs, so ``examples/boolean/minifuck.txt`` is now generated like
# every other file and the reading model survives as prose in
# ``docs/minifuck_generator.md`` rather than as a program nothing produces.
#
# The mechanism is kept rather than deleted: it costs one empty dict and is
# what a future committed-but-ungenerated program would use.
HAND_WRITTEN: dict[str, tuple[str, tuple[str, ...], str, bool]] = {}

__all__ = ["AND2", "BOOLEAN_EXAMPLES", "HAND_WRITTEN", "BooleanExample"]
