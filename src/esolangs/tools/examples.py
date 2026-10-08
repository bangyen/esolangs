"""The committed boolean example programs, as data.

One program per language whose generator can be verified end to end;
:class:`BooleanExample` records generator, table, inputs and invocation,
deriving Boolean I/O fields from the registry.
``scripts/generate.py examples`` and ``tests/scripts/test_examples.py``
both derive from :data:`BOOLEAN_EXAMPLES`.  Parameterized generators carry
a ``fill``.  A language qualifies when its answer is recoverable from what
it prints, including a fixed position in a state dump (Minsky Swap's
second register, RAM0's ``z``, LaserFuck's tape after the inputs).
123, ArrowQueue, Crement and Vandevelo answer by termination, so the
committed row is a halting one (123's ``1,0`` row halts but prints a stray
``0x80``).  Fargo reads one number whose bits are the inputs, so its
input is the row index.  Back (answer under the head) and A Painter Ant
(invisible ant) used to fail and no longer do.

The ``_fill_*`` functions are the only place a setter is spelled: a
generator lays its template out by the filled width, and a second
spelling that drifted made an instantiated program loop and the suite hang.
"""

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import cast

from esolangs._program import Program
from esolangs.raster import Raster
from esolangs.registry import LANGUAGES, SourceKind, canonical_id, resolve
from esolangs.registry._contracts import AnswerMode, BooleanContract, InputShape
from esolangs.tools.a_painter_ant import PAIR as APA_PAIR
from esolangs.tools.arrowqueue import PAIR as ARROWQUEUE_PAIR
from esolangs.tools.back import PAIR as BACK_PAIR
from esolangs.tools.bfpda import BFPDA_PAIR
from esolangs.tools.bio import BIO_PAIR
from esolangs.tools.bitdeque import bitdeque_setters
from esolangs.tools.bitwise_cyclic_tag import PAIR as BCT_PAIR
from esolangs.tools.crement import crement_setters
from esolangs.tools.eval_lang import PAIR as EVAL_PAIR
from esolangs.tools.fractran import fractran_setters
from esolangs.tools.helpers import (
    TEMPLATE_CHAR,
    Setters,
    fill_runs,
)
from esolangs.tools.home_row import HOME_ROW_PAIR
from esolangs.tools.intercal import PAIR as INTERCAL_PAIR
from esolangs.tools.intercal import TEMPLATE_CHAR as INTERCAL_CHAR
from esolangs.tools.minifuck import minifuck_setters
from esolangs.tools.minsky_swap import minsky_swap_setters
from esolangs.tools.nocomment import PAIR as NOCOMMENT_PAIR
from esolangs.tools.one_two_three import PAIR as ONE_TWO_THREE_PAIR
from esolangs.tools.ram0 import PAIR as RAM0_PAIR
from esolangs.tools.smallfuck import smallfuck_setters
from esolangs.tools.underload import underload_setters
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
    a ``Seeded`` for LaserFuck); ``inputs`` are encoded stdin chunks; ``expected`` is
    the whole stdout.
    """

    generator: Callable[..., Program]
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
    #: and a proved cycle gives a 1; a timeout is undecided.  ``dump`` means the
    #: program prints its whole final state and the answer sits at a fixed
    #: place in it, which ``note`` names.  Carried as a field because the
    #: prose alone cannot be branched on: a sweep that hardcoded two of the
    #: dumps and forgot a third reported a passing language as broken.
    answer_mode: AnswerMode = "output"
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
    #: Boolean input encoding: adjacent characters, numeric/string lines,
    #: a row index, or the padded character stream Taglate requires.
    input_shape: InputShape = "line_per_bit"
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
    #: The one ``(zero, one)`` pair every input is spelled with, where the
    #: embed is uniform; ``setters`` is then derived from it.
    pair: tuple[str, str] | None = None
    #: The character the public template spells its inputs with, one run
    #: per input; outside the language's alphabet.
    char: str = TEMPLATE_CHAR
    #: Strips a header the template carries for its setters' sake -- the
    #: part of the template that is not program.
    body: Callable[[str], str] | None = None
    split: bool = False
    kwargs: tuple[tuple[str, int], ...] = ()
    note: str = ""
    stem: str = ""
    scale: int = 1

    @property
    def filename(self) -> str:
        """Return the example filename in the language's source format."""
        kind = LANGUAGES[resolve(self.stem.replace("-", " "))].source_kind
        return self.stem + (".png" if kind is SourceKind.RASTER else ".txt")

    def build(
        self, width: int | None = DEFAULT_WIDTH, *, balance: bool = False
    ) -> Program:
        """Return the source this example commits.

        Wrapped to ``width`` by the token-aware wrapper ``stem`` selects
        (``None`` returns raw output; a language with no wrapper is unwrapped).
        A generator that takes a width lays itself out, as :func:`esolangs.generate`.
        ``balance`` uses the public balanced generator instead of ``width``.
        """
        if balance:
            import esolangs

            language = canonical_id(self.stem.replace("-", " "))
            program = esolangs.generate(
                language, self.table, balance=True, scale=self.scale
            )
            if self.fill is not None:
                program = esolangs.instantiate(language, cast(str, program), self.bits)
            return program
        if width is not None and takes_width(self.generator):
            program = self.generator(self.table, width)
        else:
            program = self.generator(self.table)
        if isinstance(program, Raster):
            return program.upscaled(self.scale)
        if self.fill is not None:
            program = self.fill(program, list(self.bits))
        return wrap_program(program, canonical_id(self.stem.replace("-", " ")), width)

    @property
    def stdin(self) -> str:
        """Return the example input with its language-specific separators."""
        if self.input_shape in {
            "char_stream",
            "char_stream_padded",
            "char_stream_cyclic",
        }:
            return "".join(self.inputs)
        return "".join(f"{line}\n" for line in self.inputs)


def _contract_for(interpreter: str) -> BooleanContract:
    """Return the registered Boolean I/O contract for an interpreter."""
    return next(
        lang.contract for lang in LANGUAGES.values() if lang.interpreter == interpreter
    )


def _reader(
    generator: Callable[[str], Program],
    interpreter: str,
    *,
    table: str = AND2,
    inputs: tuple[str, ...] = ("0", "1"),
    expected: str = "0",
    split: bool = False,
    kwargs: tuple[tuple[str, int], ...] = (),
) -> BooleanExample:
    """Build an input-reading example, whose bits are read from stdin."""
    contract = _contract_for(interpreter)
    if contract.input_shape in {"char_stream", "char_stream_padded"}:
        inputs = ("".join(inputs),)
    return BooleanExample(
        answer_mode=contract.answer_mode,
        answer_pattern=contract.answer_pattern,
        answer_values=contract.answer_values,
        generator=generator,
        table=table,
        interpreter=interpreter,
        expected=expected,
        inputs=inputs,
        alphabet=contract.alphabet,
        input_shape=contract.input_shape,
        ghost_digit=contract.ghost_digit,
        split=split,
        kwargs=kwargs,
        note=contract.note,
    )


def _embedded(
    generator: Callable[[str], str],
    interpreter: str,
    *,
    pair: tuple[str, str] | None = None,
    setters: Callable[[str, int], Setters] | None = None,
    char: str = TEMPLATE_CHAR,
    body: Callable[[str], str] | None = None,
    table: str = AND2,
    bits: tuple[int, ...] = (0, 1),
    expected: str = "0",
    expected_compared: bool = True,
    split: bool = False,
    kwargs: tuple[tuple[str, int], ...] = (),
) -> BooleanExample:
    """Build a parameterized example, whose bits are embedded in the text.

    ``pair`` is the one pair every input is spelled with, or
    ``setters(template, n)`` names them; ``body`` strips a header first.
    """
    if (pair is None) == (setters is None):
        raise TypeError("exactly one of pair and setters")
    if setters is None:
        setters = uniform(pair)
    contract = _contract_for(interpreter)
    return BooleanExample(
        answer_mode=contract.answer_mode,
        answer_pattern=contract.answer_pattern,
        answer_values=contract.answer_values,
        alphabet=contract.alphabet,
        input_shape=contract.input_shape,
        ghost_digit=contract.ghost_digit,
        generator=generator,
        table=table,
        interpreter=interpreter,
        expected=expected,
        expected_compared=expected_compared,
        bits=bits,
        fill=_fill_from(setters, body, char),
        setters=setters,
        pair=pair,
        char=char,
        body=body,
        split=split,
        kwargs=kwargs,
        note=contract.note,
    )


def uniform(pair: tuple[str, str] | None) -> Callable[[str, int], Setters]:
    """Return the setters of a uniform embed: ``pair`` for every input."""
    if pair is None:  # pragma: no cover - _embedded checks first
        raise TypeError("a uniform embed needs its pair")

    def setters(_template: str, n: int) -> Setters:
        return (pair,) * n

    return setters


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


# Example file stem -> how that example is built and run.  Stems match the
# language's display name lowercased with spaces as dashes.
BOOLEAN_EXAMPLES: dict[str, BooleanExample] = {}


def _register() -> None:
    from esolangs import tools as b

    reading = {
        "addsubjump": _reader(
            b.addsubjump,
            "register_based.addsubjump",
        ),
        # An executed line prints its result and nothing else, so the
        # answer arrives with the newline that ends that line.
        "algebraic-programming-language": _reader(
            b.algebraic_programming_language,
            "other.algebraic_programming_language",
            expected="0\n",
        ),
        "alight": _reader(
            b.alight,
            "grid_based.alight",
            split=True,
        ),
        "b-tapemark": _reader(
            b.b_tapemark,
            "grid_based.b_tapemark",
        ),
        # ``.`` writes the digit and a trailing space, so the committed
        # answer carries it and the sweep strips it.
        "befunge": _reader(
            b.befunge,
            "grid_based.befunge",
            expected="0 ",
            split=True,
        ),
        "bfstack": _reader(
            b.bfstack,
            "stack_based.bfstack",
        ),
        "sstack": _reader(
            b.sstack,
            "stack_based.sstack",
        ),
        "bit~": _reader(
            b.bit_tilde,
            "tape_based.bit_tilde",
        ),
        "brainfuck": _reader(
            b.brainfuck,
            "tape_based.brainfuck",
        ),
        "brainif": _reader(
            b.brainif,
            "tape_based.brainif",
            split=True,
        ),
        "circlefuck": _reader(
            b.circlefuck,
            "tape_based.circlefuck",
        ),
        "collatz-multiverse": _reader(
            b.collatz_multiverse, "register_based.collatz_multiverse"
        ),
        "container": _reader(
            b.container,
            "other.container",
            split=True,
        ),
        # ``send`` terminates every line it writes, so the answer arrives
        # with a newline after it -- there is no other output command.
        "inject": _reader(
            b.inject,
            "other.inject",
            expected="0\n",
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
            split=True,
        ),
        "cvnc": _reader(b.cvnc, "other.cvnc"),
        "decleq": _reader(
            b.decleq,
            "register_based.decleq",
        ),
        "dig": _reader(b.dig, "grid_based.dig", split=True),
        "dimensional": _reader(b.dimensional, "tape_based.dimensional"),
        "egl": _reader(
            b.egl,
            "grid_based.egl",
        ),
        "factor": _reader(
            b.factor,
            "tape_based.factor",
        ),
        "false": _reader(
            b.false,
            "stack_based.false",
        ),
        "fish": _reader(
            b.fish,
            "grid_based.fish",
            split=True,
        ),
        "thisthat": _reader(
            b.thisthat,
            "grid_based.thisthat",
            split=True,
        ),
        # Fargo reads one *number* before the program starts, not a bit per
        # line, and ``@ k`` indexes that number's bits.  The boolean
        # convention is therefore to feed the row index: the inputs
        # most-significant-first are its binary digits, so the 0,1 row of a
        # two-input table is the single line "1".
        "fargo": _reader(
            b.fargo,
            "other.fargo",
            inputs=("1",),
        ),
        "flowchart": _reader(
            b.flowchart,
            "grid_based.flowchart",
            split=True,
        ),
        "forbin": _reader(
            b.forbin,
            "other.forbin",
        ),
        "forþ": _reader(b.forth, "stack_based.forth"),
        "grapheme": _reader(
            b.grapheme,
            "stack_based.grapheme",
            inputs=("%", "A"),
        ),
        "jaune": _reader(b.jaune, "tape_based.jaune"),
        "laserfuck": _reader(
            b.laserfuck,
            "grid_based.laserfuck",
            split=True,
            expected="0",
            kwargs=(("seed", 0),),
        ),
        "malbolge": _reader(
            b.malbolge,
            "other.malbolge",
        ),
        "modulous": _reader(b.modulous, "stack_based.modulous"),
        "packlang": _reader(
            b.packlang,
            "other.packlang",
        ),
        "painfuck": _reader(b.painfuck, "tape_based.painfuck"),
        "polynomial": _reader(
            b.polynomial,
            "register_based.polynomial",
        ),
        "qoibl": _reader(
            b.qoibl,
            "register_based.qoibl",
            split=True,
        ),
        "rotfuck": _reader(
            b.rotfuck,
            "tape_based.rotfuck",
        ),
        "boolfuck": _reader(
            b.boolfuck,
            "tape_based.boolfuck",
        ),
        "subleq": _reader(
            b.subleq,
            "tape_based.subleq",
        ),
        "sbleq": _reader(
            b.sbleq,
            "tape_based.sbleq",
        ),
        "slow-acv-mammalian": _reader(
            b.slow_acv_mammalian,
            "tape_based.slow_acv_mammalian",
        ),
        "smu": _reader(
            b.smu,
            "stack_based.smu",
        ),
        "sophie": _reader(
            b.sophie,
            "register_based.sophie",
        ),
        "streetcode": _reader(
            b.streetcode,
            "grid_based.streetcode",
            split=True,
        ),
        "super-snusp": _reader(
            b.super_snusp,
            "grid_based.super_snusp",
            split=True,
        ),
        "suffolk": _reader(
            b.suffolk,
            "tape_based.suffolk",
        ),
        "taglate": _reader(
            b.taglate,
            "queue_based.taglate",
            split=True,
        ),
        "thue": _reader(
            b.thue,
            "other.thue",
        ),
        "unlambda": _reader(
            b.unlambda,
            "other.unlambda",
        ),
        "unsquare": _reader(
            b.unsquare,
            "stack_based.unsquare",
        ),
        "vandevelo": _reader(
            b.vandevelo,
            "other.vandevelo",
            expected="",
        ),
        "3x": _reader(b.three_x, "stack_based.three_x"),
        "6-5": _reader(
            b.six_five,
            "tape_based.six_five",
        ),
    }

    embedded = {
        "a-painter-ant": _embedded(
            b.a_painter_ant,
            "grid_based.a_painter_ant",
            pair=APA_PAIR,
            expected="....\n####\n.o.#",
        ),
        "back": _embedded(
            b.back,
            "tape_based.back",
            pair=BACK_PAIR,
            split=True,
            expected="0 1 0",
        ),
        "bf-pda": _embedded(b.bfpda, "stack_based.bf_pda", pair=BFPDA_PAIR),
        "bio": _embedded(b.bio, "register_based.bio", pair=BIO_PAIR),
        "bitdeque": _embedded(
            b.bitdeque,
            "queue_based.bitdeque",
            setters=bitdeque_setters,
        ),
        "slashes": _embedded(
            b.slashes,
            "other.slashes",
            pair=("a", "b"),
        ),
        "cyclic-tag": _embedded(
            b.cyclic_tag,
            "queue_based.cyclic_tag",
            pair=BCT_PAIR,
        ),
        "bitwise-cyclic-tag": _embedded(
            b.bitwise_cyclic_tag,
            "queue_based.bitwise_cyclic_tag",
            pair=BCT_PAIR,
        ),
        "eval": _embedded(b.eval, "stack_based.eval", pair=EVAL_PAIR),
        "fractran": _embedded(
            b.fractran,
            "other.fractran",
            setters=fractran_setters,
            expected="1",
        ),
        "home-row": _embedded(b.home_row, "tape_based.home_row", pair=HOME_ROW_PAIR),
        "intercal": _embedded(
            b.intercal,
            "other.intercal",
            pair=INTERCAL_PAIR,
            char=INTERCAL_CHAR,
            expected="_\n\n",
        ),
        "minifuck": _embedded(
            b.minifuck, "tape_based.minifuck", setters=minifuck_setters
        ),
        "minsky-swap": _embedded(
            b.minsky_swap,
            "register_based.minsky_swap",
            setters=minsky_swap_setters,
            expected="1 0",
        ),
        "nocomment": _embedded(
            b.nocomment, "tape_based.nocomment", pair=NOCOMMENT_PAIR
        ),
        "ram0": _embedded(
            b.ram0,
            "register_based.ram0",
            pair=RAM0_PAIR,
            expected="z: 0\nn: 0\nram: {\n    1: 0,\n    0: 1\n}",
        ),
        "smallfuck": _embedded(
            b.smallfuck,
            "tape_based.smallfuck",
            setters=smallfuck_setters,
        ),
        "underload": _embedded(
            b.underload,
            "stack_based.underload",
            setters=underload_setters,
        ),
        # 123 answers with the termination convention, as ArrowQueue does, so
        # only the halting (0) branch is committed.  The constructed template
        # pops through location -2 while merging, which prints junk bytes on
        # every row; ``test_boolean_example`` asserts the halt and ignores
        # them, so ``expected`` is vestigial here.
        "123": _embedded(
            b.one_two_three,
            "tape_based.one_two_three",
            pair=ONE_TWO_THREE_PAIR,
            expected="",
            expected_compared=False,
        ),
        "arrowqueue": _embedded(
            b.arrowqueue,
            "grid_based.arrowqueue",
            pair=ARROWQUEUE_PAIR,
            expected="1 0 0 1 2 3",
            split=True,
        ),
        "crement": _embedded(
            b.crement,
            "other.crement",
            setters=crement_setters,
            expected="",
        ),
    }

    # Stamp each example with its own stem, so ``build()`` knows which
    # language it is and can pick the matching token-aware wrapper without
    # the caller having to supply it.
    from esolangs.tools.line import line
    from esolangs.tools.piet import piet

    reading["line"] = _reader(line, "tape_based.line")
    reading["piet"] = replace(
        _reader(piet, "stack_based.piet"),
        scale=80,
    )
    reading["piet-plus-plus"] = _reader(b.piet_plus_plus, "stack_based.piet_plus_plus")
    for stem, example in {**reading, **embedded}.items():
        BOOLEAN_EXAMPLES[stem] = replace(example, stem=stem)


_register()

__all__ = ["AND2", "BOOLEAN_EXAMPLES", "BooleanExample"]
