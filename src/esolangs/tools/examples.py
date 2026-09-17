"""The committed boolean example programs, as data.

One program per language whose generator can be verified end to end;
:class:`BooleanExample` records generator, table, inputs and invocation,
and ``scripts/generate.py examples`` and ``tests/scripts/test_examples.py``
both derive from :data:`BOOLEAN_EXAMPLES`.  Parameterized generators carry
a ``fill``.  A language qualifies when its answer is recoverable from what
it prints, including a fixed position in a state dump (Minsky Swap's
second register, RAM0's ``z``, LaserFuck's tape after the inputs).
ArrowQueue, Point Break and 123 answer by termination, so the committed
row is a halting one (123's ``1,0`` row halts but prints a stray
``0x80``).  Fargo reads one number whose bits are the inputs, so its
input is the row index.  Back (answer under the head) and A Painter Ant
(invisible ant) used to fail and no longer do.

The ``_fill_*`` functions are the only place a setter is spelled: a
generator lays its template out by the filled width, and a second
spelling that drifted made an instantiated program loop and the suite hang.
"""

from collections.abc import Callable
from dataclasses import dataclass, replace

from esolangs.registry import Generator, canonical_id
from esolangs.tools.a_painter_ant import apa_setters
from esolangs.tools.arrowqueue import arrowqueue_setters
from esolangs.tools.cod import cod_setters
from esolangs.tools.crement import crement_setters
from esolangs.tools.helpers import (
    TEMPLATE_CHAR,
    Setters,
    fill_runs,
)
from esolangs.tools.nopstacle import nopstacle_setters
from esolangs.tools.wrap import DEFAULT_WIDTH, takes_width, wrap_program

# The committed programs all witness the same two-input function and row:
# AND2 evaluated on 0,1.  The generator suites cover the other tables and
# rows; keeping this corpus uniform makes the files directly comparable.
AND2 = "0001"


@dataclass(frozen=True)
class BooleanExample:
    """How one committed ``examples`` program is built and run.

    ``generator(table)`` produces the program (or the template ``fill``
    instantiates with ``bits``); ``interpreter`` is the dotted module,
    ``split`` passes lines, ``kwargs`` extra ``run()`` ints (``seed`` becomes
    a ``Seeded`` for LaserFuck); ``inputs`` are stdin lines; ``expected`` is
    the whole stdout.
    """

    generator: Generator
    table: str
    interpreter: str
    expected: str
    inputs: tuple[str, ...] = ()
    #: Whether ``expected`` is the program's actual output.  False where the
    #: answer is the *halt* and the bytes written on the way out are junk:
    #: 123's constructed template pops through location -2 while merging and
    #: prints whatever that cell holds.  ``expected`` is then a placeholder
    #: no one should compare against -- which the manifest was presenting as
    #: "this program outputs nothing", when it prints two bytes.
    expected_compared: bool = True
    #: How the answer reaches the caller.  ``output`` is the usual: the
    #: program prints it.  ``termination`` means the program *halts* for a 0
    #: and loops forever for a 1, so a timeout is the 1.  ``dump`` means the
    #: program prints its whole final state and the answer sits at a fixed
    #: place in it, which ``note`` names.  Carried as a field because the
    #: prose alone cannot be branched on: a sweep that hardcoded two of the
    #: dumps and forgot a third reported a passing language as broken.
    answer_mode: str = "output"
    #: Where the answer sits in the output, as a regex whose first group is
    #: it.  Empty means the last non-whitespace character, which is right
    #: for every language that prints its answer and for four of the six
    #: that dump state -- their dump happens to end on it.  The other two
    #: need saying: RAM0's answer is its ``z`` register, three lines above
    #: the end, and A Painter Ant's is a mark in a painted grid.
    answer_pattern: str = ""
    #: How this language spells a 0 and a 1 *in the answer position*, the
    #: mirror of ``alphabet`` for input.  A Painter Ant marks the ant's own
    #: cell ``o`` on black and ``@`` on white, so its answer is a letter.
    #:
    #: For an ``answer_mode`` of ``termination`` this is the *polarity*
    #: instead -- ``("halts", "diverges")`` -- because which way round it
    #: goes was prose only, so a caller reading ``answer_mode`` still had to
    #: hardcode halt-means-0 from the English.  It is the one convention a
    #: zero-per-language verifier could not get from the API.
    answer_values: tuple[str, str] = ("0", "1")
    #: How this language spells an input 0 and an input 1.  Almost always
    #: the digits, but not universally, and the exception is silent rather
    #: than loud: Grapheme's generator normalizes each line with
    #: ``ord(line[0]) - 65`` and then maps zero to 1 and nonzero to 0, so
    #: ``A`` is a 1 and every other first character is a 0 -- a ``"0"``
    #: line and a ``"1"`` line both read as 0, and the program answers the
    #: all-zeros row instead of refusing.  The second half is not optional
    #: prose: ``ord('A') - 65`` is 0, so the subtraction on its own says
    #: the opposite of what the language does.
    #:
    #: This said "every non-empty string is truthy, so a ``"0"`` line reads
    #: as a 1", which is the language's general rule and not what the
    #: generator does with it.  The warning was right and its direction was
    #: backwards, which is worse than saying nothing: a reader who trusts
    #: the reason predicts all-ones and debugs the wrong thing.  Carried
    #: here so ``describe`` can tell a caller before they feed it digits.
    alphabet: tuple[str, str] = ("0", "1")
    #: How the bits are laid out on stdin.  ``line_per_bit`` is the rule
    #: everywhere else; ``one_line`` puts them all on one (Clockwise packs
    #: seven bits per character and reads the lot in one go); ``row_index``
    #: sends a single number whose bits are the inputs (Fargo reads it
    #: before the program starts and indexes it with ``@ k``);
    #: ``line_per_bit_padded`` is Taglate's: a line per bit like the
    #: majority, plus the leading zero ``ghost_digit`` describes.  It was
    #: briefly called ``char_stream``, on the strength of a comment saying
    #: Taglate "reads a character at a time" -- true of the interpreter,
    #: false of the stdin it wants, since :class:`ScriptedIO` hands over
    #: whole lines.  Feeding it literal characters (``"01"``) is an
    #: input-exhausted error; a line per bit is what works.
    input_shape: str = "line_per_bit"
    #: Whether an odd input count is padded with a leading zero the program
    #: reads like any other digit.  Taglate's slot stride has to land on a
    #: separator, so its n=3 program reads four digits; feeding three is an
    #: input-exhausted error, and padding at the *end* instead answers every
    #: MSB-set row wrongly.  One input is the exception -- that arity is an
    #: affine computation on the bit itself, and reads exactly one digit.
    ghost_digit: bool = False
    bits: tuple[int, ...] = ()
    fill: Callable[[str, list[int]], str] | None = None
    #: The ``(zero, one)`` text per input, read off a template; ``fill`` is
    #: :func:`instantiate` with these and nothing else.
    setters: Callable[[str, int], Setters] | None = None
    #: The character the public template spells its inputs with, one run
    #: per input; outside the language's alphabet.
    char: str = TEMPLATE_CHAR
    #: Strips a header the template carries for its setters' sake (%^2^-1
    #: alone) -- the part of the template that is not program.
    body: Callable[[str], str] | None = None
    split: bool = False
    kwargs: tuple[tuple[str, int], ...] = ()
    note: str = ""
    stem: str = ""

    def build(self, width: int | None = DEFAULT_WIDTH) -> str:
        """Return the program text this example commits.

        Wrapped to ``width`` by the token-aware wrapper ``stem`` selects
        (``None`` returns raw output; a language with no wrapper is unwrapped).
        A generator that takes a width lays itself out, as :func:`esolangs.generate`.
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
    alphabet: tuple[str, str] = ("0", "1"),
    input_shape: str = "line_per_bit",
    ghost_digit: bool = False,
    answer_mode: str = "output",
    answer_pattern: str = "",
    answer_values: tuple[str, str] = ("0", "1"),
) -> BooleanExample:
    """Build an input-reading example, whose bits are read from stdin."""
    return BooleanExample(
        answer_mode=answer_mode,
        answer_pattern=answer_pattern,
        answer_values=answer_values,
        generator=generator,
        table=table,
        interpreter=interpreter,
        expected=expected,
        inputs=inputs,
        alphabet=alphabet,
        input_shape=input_shape,
        ghost_digit=ghost_digit,
        split=split,
        kwargs=kwargs,
        note=note,
    )


def _embedded(
    generator: Callable[[str], str],
    interpreter: str,
    setters: Callable[[str, int], Setters],
    *,
    char: str = TEMPLATE_CHAR,
    body: Callable[[str], str] | None = None,
    table: str = AND2,
    bits: tuple[int, ...] = (0, 1),
    expected: str = "0",
    expected_compared: bool = True,
    split: bool = False,
    kwargs: tuple[tuple[str, int], ...] = (),
    note: str = "",
    answer_mode: str = "output",
    answer_pattern: str = "",
    answer_values: tuple[str, str] = ("0", "1"),
) -> BooleanExample:
    """Build a parameterized example, whose bits are embedded in the text.

    ``setters(template, n)`` names the pairs; ``body`` strips a header
    (%^2^-1 alone) first.
    """
    return BooleanExample(
        answer_mode=answer_mode,
        answer_pattern=answer_pattern,
        answer_values=answer_values,
        generator=generator,
        table=table,
        interpreter=interpreter,
        expected=expected,
        expected_compared=expected_compared,
        bits=bits,
        fill=_fill_from(setters, body, char),
        setters=setters,
        char=char,
        body=body,
        split=split,
        kwargs=kwargs,
        note=note,
    )


def _fill_from(
    setters: Callable[[str, int], Setters],
    body: Callable[[str], str] | None = None,
    char: str = TEMPLATE_CHAR,
) -> Callable[[str, list[int]], str]:
    """Return the substitution a ``setters`` function defines."""

    def fill(template: str, bits: list[int]) -> str:
        source = template if body is None else body(template)
        return fill_runs(source, char, setters(template, len(bits)), bits)

    return fill


# Each ``setters`` below is the language's own way of spelling "set input i
# to this bit", the counterpart of the input read an input-capable language
# performs: one ``(zero, one)`` pair per input, read off the template.  The
# example's ``fill`` is :func:`instantiate` with those pairs.


def _setters_bio(_template: str, n: int) -> Setters:
    """Spell every input as the same four-character unit.

    ``0ox;`` for a one, ``0oz;`` (a write nothing reads) for a zero; the
    weight is Horner doubling in the template.  A zero spelled as nothing
    made instantiations 236, 240, 244 and 248 chars at ``n == 2``.  Space
    padding also works but pads with ignored characters; ``y`` is the
    doubling's carrier.
    """
    return (("0oz;", "0ox;"),) * n


def _setters_nocomment(_template: str, n: int) -> Setters:
    return (("c", "i"),) * n


#: Bitdeque's one pair: with the register at zero, ``PUSH INVERT`` pushes a
#: zero and ``INVERT PUSH`` a one, and both leave the register at one.
_BITDEQUE_PAIR = ("PUSH INVERT", "INVERT PUSH")


def _setters_bitdeque(_template: str, n: int) -> Setters:
    """Spell every input as the same eleven-character pair on both routes.

    The tree route's register flips per unit, so odd positions push
    complemented and the table absorbs it; the linear route spends the
    weight in the discard blocks.
    """
    return (_BITDEQUE_PAIR,) * n


def _setters_bfpda(_template: str, n: int) -> Setters:
    """Push the bit, in a constant width.

    ``<@@@`` and ``<[@]`` (``[`` peeks the pushed zero and skips its body):
    four is minimal, since an exhaustive search over ``<>@[]`` finds only a
    zero at one character, only a one at two, only zeros at three.  ``<``
    vs ``<@`` leaked the inputs; comment padding is what the separators were.
    """
    return (("<[@]", "<@@@"),) * n


def _setters_back(_template: str, n: int) -> Setters:
    """Finish each input cell: ``+`` leaves the one, ``-`` flips it to zero.

    The template primes the cell to 1 on the first row so both rows execute
    (``+`` steps the beam when the cell is zero, so the old run-then-``+``
    order ran only one row).  A blank zero rstripped away, making
    instantiations 41, 42 and 43 chars over six or seven rows; now all 47 over nine.
    """
    return (("-", "+"),) * n


def _setters_minsky_swap(_template: str, n: int) -> Setters:
    """Set each input register with ``++`` for a one and ``**`` for a zero.

    The weight is the template's stage.  Both runs are even because ``*``
    swaps the pointer: a one-wide zero would move it onto the accumulator.
    """
    return (("**", "++"),) * n


def _setters_ram0(_template: str, n: int) -> Setters:
    """Set each input cell with ``Z A`` for a one and ``Z Z`` for a zero.

    ``Z`` resets absolutely, so the setter works at every position.
    """
    return (("Z Z", "Z A"),) * n


def _setters_home_row(_template: str, n: int) -> Setters:
    """Set the bit cell, in a constant width.

    ``a`` raises the zero cell; ``s`` clears it, ``j`` skips nothing (the
    cell is nonzero) and leaves it.  ``a`` vs nothing leaked the inputs; a
    pad must leave both value and pointer alone, since a gate tests this
    cell next, and spaces would be ignored characters.
    """
    return (("as", "aj"),) * n


def _setters_cod(template: str, n: int) -> Setters:
    """Set the cod's value to the bit at that input's ``+`` fork.

    The pair lives in :func:`esolangs.tools.cod.cod_setters`.
    """
    return cod_setters(template, n)


def _setters_eval(_template: str, n: int) -> Setters:
    """Stage the bit on the tree stack, then move it to the input stack.

    The backtick pushes ``1 - ptr``, a one on stack 0; ``=`` moves it.
    Pushing onto the input stack directly needed ``` `+ ``` for a one and
    leaked; a spare ``0`` pad would leave a residue a node reads.
    """
    return (("0=", "`="),) * n


def _setters_wii2d(_template: str, n: int) -> Setters:
    """Set each junction: ``v`` takes the 1-branch, ``>`` continues east.

    One cell; the reserved second column was blank travel on row 0.
    """
    return ((">", "v"),) * n


def _setters_minifuck(_template: str, n: int) -> Setters:
    """Write each bit at ``ptr+1``: ``[<`` for a one, ``xx`` for a zero.

    Two characters each; ``xx`` is a no-op the language *executes*, so a
    dead-character cleanup could not reintroduce the leak.
    """
    return (("xx", "[<"),) * n


def _setters_one_two_three(_template: str, n: int) -> Setters:
    """Embed each bit as the generator's own ``ONE``/``ZERO`` command.

    Read from the generator, since a copy would not follow a change.
    """
    from esolangs.tools.one_two_three import ONE, ZERO

    return ((ZERO, ONE),) * n


def _setters_pct_squared_minus_one(template: str, n: int) -> Setters:
    """Each bit's setter, named by the template's own header.

    %^2^-1 solves its setters per table; the header carries both branches,
    equal width, and :func:`_body_pct_squared_minus_one` strips it.
    """
    from esolangs.tools.pct_squared_minus_one import setters

    return setters(template, n)


def _body_pct_squared_minus_one(template: str) -> str:
    from esolangs.tools.pct_squared_minus_one import body

    return body(template)


def _setters_arrowqueue(template: str, n: int) -> Setters:
    # Each slot is a row of its own, so the multi-row block substitutes in place
    return arrowqueue_setters(template, n)


def _setters_nopstacle(template: str, n: int) -> Setters:
    """Return each level's run of bit cells."""
    return nopstacle_setters(template, n)


def _setters_crement(template: str, n: int) -> Setters:
    """Return the jump line whose data spells each bit."""
    return crement_setters(template, n)


# Example file stem -> how that example is built and run.  Stems match the
# language's display name lowercased with spaces as dashes.
BOOLEAN_EXAMPLES: dict[str, BooleanExample] = {}


def _register() -> None:
    from esolangs import tools as b

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
        "alight": _reader(b.alight, "grid_based.alight", split=True),
        "b-tapemark": _reader(b.b_tapemark, "grid_based.b_tapemark"),
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
            note="Container prints the answer like any other reader; it "
            "also ends by calling sys.exit(0) rather than returning, which "
            "matters to a harness driving it but not to reading the result",
        ),
        # ``send`` terminates every line it writes, so the answer arrives
        # with a newline after it -- there is no other output command.
        "inject": _reader(
            b.inject,
            "other.inject",
            expected="0\n",
            note="send terminates each line, so the answer ends in a newline",
        ),
        "interprogck8": _reader(
            b.interprogck8,
            "register_based.interprogck8",
            split=True,
        ),
        "circuit_diagram": _reader(
            b.circuit_diagram,
            "grid_based.circuit_diagram",
            split=True,
        ),
        "clockwise": _reader(
            b.clockwise,
            "grid_based.clockwise",
            inputs=("01",),
            input_shape="one_line",
            split=True,
            note="Clockwise reads all its input bits in one go, so they go "
            "on one line -- one character per bit, not a line per bit, and "
            "not seven bits packed into a character: that packing is real "
            "but is on the output side. A line per bit, or a packed one, "
            "is read as a different row and answered wrongly",
        ),
        "cvnc": _reader(b.cvnc, "other.cvnc"),
        "decleq": _reader(b.decleq, "register_based.decleq"),
        "dig": _reader(b.dig, "grid_based.dig", split=True),
        "dimensional": _reader(b.dimensional, "tape_based.dimensional"),
        "egl": _reader(b.egl, "grid_based.egl"),
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
            input_shape="row_index",
            note="Fargo reads one number whose bits are the inputs, so the "
            "committed input is the row index rather than a bit per line",
        ),
        "flowchart": _reader(b.flowchart, "grid_based.flowchart", split=True),
        "forbin": _reader(b.forbin, "other.forbin"),
        "forþ": _reader(b.forth, "stack_based.forth"),
        "grapheme": _reader(
            b.grapheme,
            "stack_based.grapheme",
            inputs=("%", "A"),
            alphabet=("%", "A"),
            note=(
                "Grapheme's generator normalizes each input line with "
                "ord(line[0]) - 65 and then maps zero to 1, so its input "
                "bits are spelled % and A: 'A' is a 1 and every other "
                "first character is a 0, which means a 0/1 line reads as 0 "
                "and the program answers the all-zeros row. The second "
                "step is not optional prose -- ord('A') - 65 is 0, so the "
                "subtraction alone says the opposite"
            ),
        ),
        "jaune": _reader(b.jaune, "tape_based.jaune"),
        "laserfuck": _reader(
            b.laserfuck,
            "grid_based.laserfuck",
            answer_mode="dump",
            split=True,
            expected="0",
            kwargs=_kw(seed=0),
            note=(
                "the initial heading is random by spec, so the example pins "
                "the source it is drawn from: seed 0 draws heading 3"
            ),
        ),
        "modulous": _reader(b.modulous, "stack_based.modulous"),
        "packlang": _reader(b.packlang, "other.packlang"),
        "painfuck": _reader(b.painfuck, "tape_based.painfuck"),
        "polynomial": _reader(b.polynomial, "register_based.polynomial"),
        "qoibl": _reader(b.qoibl, "register_based.qoibl", split=True),
        "rotfuck": _reader(b.rotfuck, "tape_based.rotfuck"),
        "s*bleq": _reader(b.sbleq, "tape_based.sbleq"),
        "slow-acv-mammalian": _reader(
            b.slow_acv_mammalian, "tape_based.slow_acv_mammalian"
        ),
        "sophie": _reader(b.sophie, "register_based.sophie"),
        "streetcode": _reader(b.streetcode, "grid_based.streetcode", split=True),
        "super-snusp": _reader(b.super_snusp, "grid_based.super_snusp", split=True),
        "suffolk": _reader(b.suffolk, "tape_based.suffolk"),
        "taglate": _reader(
            b.taglate,
            "queue_based.taglate",
            split=True,
            input_shape="line_per_bit_padded",
            ghost_digit=True,
            note="Taglate takes a line per bit like most languages, but an "
            "odd input count above 1 is padded with a leading zero it reads "
            "like any other digit: an n=3 program wants four lines. Feeding "
            "three exhausts its input; padding at the end instead answers "
            "every row whose top bit is set wrongly",
        ),
        "unsquare": _reader(b.unsquare, "stack_based.unsquare"),
        "vandevelo": _reader(
            b.vandevelo,
            "other.vandevelo",
            answer_mode="termination",
            answer_values=("halts", "diverges"),
            expected="",
            note="Vandevelo answers by terminating: nil halts and not nil loops",
        ),
        "ztoalc-l": _reader(b.ztoalc_l, "other.ztoalc_l", split=True),
        "3d-brainfuck": _reader(b.three_d_brainfuck, "tape_based.three_d_brainfuck"),
        "3x": _reader(b.three_x, "stack_based.three_x"),
        "6-5": _reader(b.six_five, "tape_based.six_five"),
    }

    embedded = {
        "a-painter-ant": _embedded(
            b.a_painter_ant,
            "grid_based.a_painter_ant",
            apa_setters,
            answer_mode="dump",
            answer_pattern=r"(?m)^[.#o@]*([o@])[.#o@]*$",
            answer_values=("o", "@"),
            expected="....\n####\n.o.#",
            note=(
                "A Painter Ant has no output: it paints a grid and the answer "
                "is the answer cell the ant rests on below its white corridor, "
                "shown by 'o' (on black, a zero) or '@' (on white, a one)"
            ),
        ),
        "back": _embedded(
            b.back,
            "tape_based.back",
            _setters_back,
            answer_mode="dump",
            split=True,
            expected="0 1 0",
            note=(
                "Back has no output instruction and dumps its tape at halt; "
                "the answer is cell n, past the n input cells"
            ),
        ),
        "bf-pda": _embedded(b.bfpda, "stack_based.bf_pda", _setters_bfpda),
        "bio": _embedded(b.bio, "register_based.bio", _setters_bio),
        "bitdeque": _embedded(
            b.bitdeque,
            "queue_based.bitdeque",
            _setters_bitdeque,
            answer_mode="dump",
            note=(
                "Bitdeque has no output instruction and dumps its deque at "
                "halt; the generator leaves exactly one bit on it, so the "
                "whole dump is the answer and there is no position to name"
            ),
        ),
        "cod": _embedded(
            b.cod,
            "grid_based.cod",
            _setters_cod,
            note="COD has no runtime input and no I/O but a printed number",
        ),
        "eval": _embedded(b.eval, "stack_based.eval", _setters_eval),
        "home-row": _embedded(b.home_row, "tape_based.home_row", _setters_home_row),
        "minifuck": _embedded(b.minifuck, "tape_based.minifuck", _setters_minifuck),
        "minsky-swap": _embedded(
            b.minsky_swap,
            "register_based.minsky_swap",
            _setters_minsky_swap,
            answer_mode="dump",
            expected="0 0",
            note=(
                "Minsky Swap has no output instruction and dumps its "
                "registers at halt; the answer is the second one"
            ),
        ),
        "nocomment": _embedded(b.nocomment, "tape_based.nocomment", _setters_nocomment),
        "ram0": _embedded(
            b.ram0,
            "register_based.ram0",
            _setters_ram0,
            answer_mode="dump",
            answer_pattern=r"z: (\d+)",
            expected="z: 0\nn: 0\nram: {\n    1: 0,\n    0: 1\n}",
            note=(
                "RAM0 has no output instruction and dumps its whole state "
                "at halt; the answer is the 'z' register"
            ),
        ),
        "wii2d": _embedded(
            b.wii2d,
            "grid_based.wii2d",
            _setters_wii2d,
            split=True,
        ),
        "pct-squared-minus-one": _embedded(
            b.pct_squared_minus_one,
            "register_based.pct_squared_minus_one",
            _setters_pct_squared_minus_one,
            body=_body_pct_squared_minus_one,
        ),
        # 123 answers with the termination convention, as ArrowQueue does, so
        # only the halting (0) branch is committed.  The constructed template
        # pops through location -2 while merging, which prints junk bytes on
        # every row; ``test_boolean_example`` asserts the halt and ignores
        # them, so ``expected`` is vestigial here.
        "123": _embedded(
            b.one_two_three,
            "tape_based.one_two_three",
            _setters_one_two_three,
            answer_mode="termination",
            answer_values=("halts", "diverges"),
            expected="",
            expected_compared=False,
            note=(
                "123 answers by terminating: it halts for a 0 result and loops "
                "forever for a 1, so only the halting branch is committed. Its "
                "output is not the answer and is not compared -- the merge pops "
                "through location -2 and prints whatever that cell holds, which "
                "for this program is the two bytes 'VO with a diaeresis'"
            ),
        ),
        "arrowqueue": _embedded(
            b.arrowqueue,
            "grid_based.arrowqueue",
            _setters_arrowqueue,
            answer_mode="termination",
            answer_values=("halts", "diverges"),
            expected="1 0 0 1 2 3",
            split=True,
            note=(
                "ArrowQueue answers by termination -- it halts for a 0 result "
                "and loops forever for a 1, so only the halting branch is "
                "committed.  The headings printed are its interpreter-only "
                "queue dump, which the verdict does not read: the answer is "
                "that the program halted at all"
            ),
        ),
        "nopstacle": _embedded(
            b.nopstacle,
            "grid_based.nopstacle",
            _setters_nopstacle,
            answer_mode="termination",
            answer_values=("halts", "diverges"),
            expected="",
            split=True,
            note=(
                "Nopstacle answers by termination: the IP falls through a "
                "decision tree of corridors, a blank bit cell passing it and "
                "a # deflecting it; a 0 leaf is a box it circles into a "
                "repeated local state, a 1 leaf drops it onto a blank row "
                "it runs along across copies forever"
            ),
        ),
        "crement": _embedded(
            b.crement,
            "other.crement",
            _setters_crement,
            answer_mode="termination",
            answer_values=("halts", "diverges"),
            expected="",
            note=(
                "Crement answers by termination: the tree's nodes patch a "
                "per-input tester's jump targets, and the row lands past the "
                "end (halts, 0) or on a self-jump (diverges, 1)"
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
# its inputs, so ``examples/minifuck.txt`` is now generated like
# every other file and the reading model survives as prose in
# ``the relevant generator tests`` rather than as a program nothing produces.
#
# The mechanism is kept rather than deleted: it costs one empty dict and is
# what a future committed-but-ungenerated program would use.
HAND_WRITTEN: dict[str, tuple[str, tuple[str, ...], str, bool]] = {}

__all__ = ["AND2", "BOOLEAN_EXAMPLES", "HAND_WRITTEN", "BooleanExample"]
