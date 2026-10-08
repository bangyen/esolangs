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

import re
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import cast

from esolangs._program import Program
from esolangs.raster import Raster
from esolangs.registry import LANGUAGES, Language, SourceKind, canonical_id, resolve
from esolangs.registry._contracts import AnswerMode, BooleanContract, InputShape
from esolangs.tools.helpers import (
    TEMPLATE_CHAR,
    Setters,
    fill_runs,
)
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
    for lang in LANGUAGES.values():
        if lang.interpreter == interpreter:
            return lang.contract
    raise LookupError(
        f"no registered language runs interpreter {interpreter!r}; the second "
        "argument of an example in src/esolangs/tools/examples.py is the "
        "module under esolangs.interpreters, e.g. 'tape_based.brainfuck'"
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


# Example file stem -> how that example is built and run; see ``_stem``.
BOOLEAN_EXAMPLES: dict[str, BooleanExample] = {}


def _stem(lang: Language) -> str:
    """Return the language's ``examples/`` stem: its dashed lowercase name.

    A name a filename would garble (``///``, ``CV(N)(C)``) uses its id.
    """
    stem = lang.name.lower().replace(" ", "-")
    return lang.id.replace("_", "-") if re.search(r"[/*()+]", stem) else stem


def _register() -> None:
    # Everything an example needs is in its ``LANGUAGE``: the registry facts
    # ``_reader`` takes, and ``example=`` for a template or other answer.
    for lang in LANGUAGES.values():
        if lang.boolean is None or lang.interpreter is None:
            continue
        spec = lang.example
        if spec.pair is not None or spec.setters is not None:
            example = _embedded(
                cast(Callable[[str], str], lang.boolean),
                lang.interpreter,
                pair=spec.pair,
                setters=spec.setters,
                char=spec.char or TEMPLATE_CHAR,
                expected=spec.expected,
                expected_compared=spec.expected_compared,
                split=lang.split,
                kwargs=spec.kwargs,
            )
        else:
            example = _reader(
                lang.boolean,
                lang.interpreter,
                inputs=spec.inputs,
                expected=spec.expected,
                split=lang.split,
                kwargs=spec.kwargs,
            )
        stem = _stem(lang)
        BOOLEAN_EXAMPLES[stem] = replace(example, stem=stem, scale=spec.scale)


_register()

__all__ = ["AND2", "BOOLEAN_EXAMPLES", "BooleanExample"]
