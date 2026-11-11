"""The committed boolean example programs, as data.

One program per language whose generator can be verified end to end;
:class:`BooleanExample` records generator, table, inputs and invocation,
deriving Boolean I/O fields from the registry.
``scripts/docs/generate.py examples`` and ``tests/tooling/test_examples.py``
both derive from :data:`BOOLEAN_EXAMPLES`.  Parameterized generators carry
a ``fill``.  A language qualifies when its answer is recoverable from what
it prints -- including a fixed position in a state dump -- or by
terminating; ``answer_mode`` and ``answer_pattern`` carry which.  A
termination answer's committed row is a halting one, so its ``expected``
bytes are a placeholder (``expected_compared`` is false).

Template bindings come from the backend declaration, shared with runtime.
"""

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any

from esolangs._bindings import TEMPLATE_CHAR, Setters, fill_runs
from esolangs.artifacts import ProgramArtifact, TemplateArtifact
from esolangs.compressed import CompressedText
from esolangs.generation.requests import GenerationRequest, Options
from esolangs.generation.template import TemplateLayout
from esolangs.generation.wrap import DEFAULT_WIDTH, wrap_program
from esolangs.raster import Raster
from esolangs.registry import LANGUAGES, Language, canonical_id, example_stems, resolve
from esolangs.registry._backend import Generator
from esolangs.registry._contracts import (
    CHAR_STREAMS,
    AnswerMode,
    BooleanContract,
    InputShape,
)
from esolangs.runtime._program import Program

# Examples use AND2 on 0,1 unless the source budget requires a smaller
# witness. Generator suites cover the other tables and rows.
AND2 = "0001"


@dataclass(frozen=True)
class BooleanExample:
    """How one committed ``examples`` program is built and run.

    ``generator(table)`` produces the program (or the template ``fill``
    instantiates with ``bits``); ``interpreter`` is the dotted module,
    ``split`` passes lines, ``kwargs`` extra ``run()`` ints (``seed`` becomes
    a ``Seeded`` where the language is random); ``inputs`` are encoded stdin
    chunks; ``expected`` is the whole stdout.
    """

    generator: Generator
    table: str
    interpreter: str
    expected: str
    inputs: tuple[str, ...] = ()
    #: Whether ``expected`` is the program's actual output.  False where the
    #: answer is the *halt* and the bytes written on the way out are junk:
    #: a termination template can pop through a location while merging and
    #: print whatever that cell holds.  ``expected`` is then a placeholder
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
    #: for every language that prints its answer and for most that dump
    #: state -- their dump happens to end on it.  The rest need a pattern:
    #: the answer sits at a fixed place in the dump, not at its end.
    answer_pattern: str = ""
    #: How this language spells a 0 and a 1 *in the answer position*, the
    #: mirror of ``alphabet`` for input.  Not always the digits: a raster
    #: answer may be a mark's character, so its answer is a letter.
    #:
    #: For an ``answer_mode`` of ``termination`` this is the *polarity*
    #: instead -- ``("halts", "diverges")`` -- because which way round it
    #: goes was prose only, so a caller reading ``answer_mode`` still had to
    #: hardcode halt-means-0 from the English.  It is the one convention a
    #: zero-per-language verifier could not get from the API.
    answer_values: tuple[str, str] = ("0", "1")
    #: How this language spells an input 0 and an input 1.  Almost always
    #: the digits, but not universally, and the exception is silent rather
    #: than loud: a generator may normalize its lines and then map zero and
    #: nonzero in the opposite sense, so a ``"0"`` line and a ``"1"`` line
    #: both read as one value and the program answers a different row
    #: instead of refusing.  The direction is the language's own, so its
    #: generator documents it; carried here so ``describe`` can tell a
    #: caller before they feed it digits.
    alphabet: tuple[str, str] = ("0", "1")
    #: Boolean input encoding: adjacent characters, numeric/string lines,
    #: a row index, or a padded character stream.
    input_shape: InputShape = "line_per_bit"
    bits: tuple[int, ...] = ()
    fill: Callable[[str, list[int]], str] | None = None
    #: The ``(zero, one)`` text per input, read off a template; ``fill`` is
    #: :func:`instantiate` with these and nothing else.
    setters: Callable[[str, int], Setters] | None = None
    #: The character the public template spells its inputs with, one run
    #: per input; outside the language's alphabet.
    char: str = TEMPLATE_CHAR
    split: bool = False
    kwargs: tuple[tuple[str, int], ...] = ()
    note: str = ""
    stem: str = ""
    scale: int = 1

    @property
    def filename(self) -> str:
        """Return the example filename in the language's source format."""
        return self.stem + LANGUAGES[resolve(self.language)].source_suffix

    @property
    def language(self) -> str:
        """Return the canonical id of the language ``stem`` names."""
        return canonical_id(self.stem.replace("-", " "))

    def build(
        self, width: int | None = DEFAULT_WIDTH, *, balance: bool = False
    ) -> ProgramArtifact[Program]:
        """Return the runnable artifact this example commits.

        Wrapped to ``width`` by the token-aware wrapper ``stem`` selects
        (``None`` returns raw output; a language with no wrapper is unwrapped).
        A generator that takes a width lays itself out, as :func:`esolangs.generate`.
        ``balance`` uses the balanced artifact pipeline instead of ``width``.
        """
        if balance:
            from esolangs import generate

            artifact = generate(
                self.language, self.table, balance=True, scale=self.scale
            )
            if self.fill is not None:
                assert isinstance(artifact, TemplateArtifact)
                artifact = artifact.fill(self.bits)
            assert isinstance(artifact, ProgramArtifact)
            return artifact
        backend = LANGUAGES[resolve(self.language)].backend
        assert backend is not None
        program = self.emit(self.table, width=width)
        if isinstance(program, CompressedText):
            return ProgramArtifact(program.wrapped(width), self.language)
        if isinstance(program, Raster):
            return ProgramArtifact(
                program.upscaled(self.scale), self.language, scale=self.scale
            )
        if self.fill is not None:
            program = self.fill(program, list(self.bits))
        return ProgramArtifact(
            wrap_program(program, self.language, width), self.language
        )

    def emit(self, table: str, *, width: int | None = None) -> Program:
        """Emit example source through the canonical backend request."""
        language = LANGUAGES[resolve(self.language)]
        backend = language.backend
        assert backend is not None
        schema = language.runtime.dialect_schema
        options = Options(tuple(schema.defaults.items())) if schema else Options()
        generated = self.generator(
            GenerationRequest(table, width if backend.layout_width else None, options)
        )
        return generated.source if isinstance(generated, TemplateLayout) else generated

    @property
    def stdin(self) -> str:
        """Return the example input with its language-specific separators."""
        if self.input_shape in CHAR_STREAMS:
            return "".join(self.inputs)
        return "".join(f"{line}\n" for line in self.inputs)


def _contract_fields(contract: BooleanContract) -> dict[str, Any]:
    """Return the example fields an interpreter's I/O contract fixes."""
    return {
        "answer_mode": contract.answer_mode,
        "answer_pattern": contract.answer_pattern,
        "answer_values": contract.answer_values,
        "alphabet": contract.alphabet,
        "input_shape": contract.input_shape,
        "note": contract.note,
    }


def _contract_for(interpreter: str) -> BooleanContract:
    """Return the registered Boolean I/O contract for an interpreter."""
    for lang in LANGUAGES.values():
        if lang.runtime.interpreter == interpreter:
            return lang.contract
    raise LookupError(
        f"no registered language runs interpreter {interpreter!r}; the second "
        "argument of an example in src/esolangs/generation/examples.py is the "
        "module under esolangs.runtime, e.g. 'brainfuck'"
    )


def _reader(
    generator: Generator,
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
    if contract.input_shape == "char_stream":
        inputs = ("".join(inputs),)
    return BooleanExample(
        **_contract_fields(contract),
        generator=generator,
        table=table,
        interpreter=interpreter,
        expected=expected,
        inputs=inputs,
        split=split,
        kwargs=kwargs,
    )


def _embedded(
    generator: Generator,
    interpreter: str,
    *,
    setters: Callable[[str, int], Setters],
    char: str = TEMPLATE_CHAR,
    table: str = AND2,
    bits: tuple[int, ...] = (0, 1),
    expected: str = "0",
    split: bool = False,
    kwargs: tuple[tuple[str, int], ...] = (),
) -> BooleanExample:
    """Build an example using its backend's declared input bindings."""
    return BooleanExample(
        **_contract_fields(_contract_for(interpreter)),
        generator=generator,
        table=table,
        interpreter=interpreter,
        expected=expected,
        bits=bits,
        fill=_fill_from(setters, char),
        setters=setters,
        char=char,
        split=split,
        kwargs=kwargs,
    )


def _fill_from(
    setters: Callable[[str, int], Setters],
    char: str,
) -> Callable[[str, list[int]], str]:
    """Return the substitution a ``setters`` function defines."""

    def fill(template: str, bits: list[int]) -> str:
        return fill_runs(template, char, setters(template, len(bits)), bits)

    return fill


# Example file stem -> how that example is built and run; see ``_stem``.
BOOLEAN_EXAMPLES: dict[str, BooleanExample] = {}


def _stem(lang: Language) -> str:
    """Return the stem shared with catalog metadata."""
    return example_stems()[lang.id]


def _register() -> None:
    from esolangs.operations.boolean_io import encode_inputs

    # Everything an example needs is in its ``LANGUAGE``: the registry facts
    # ``_reader`` takes, backend bindings, and the committed invocation.
    for lang in LANGUAGES.values():
        if lang.backend is None or lang.runtime.interpreter is None:
            continue
        spec = lang.example
        if lang.backend.template is not None:
            example = _embedded(
                lang.backend.entrypoint,
                lang.runtime.interpreter,
                table=spec.table,
                bits=spec.bits,
                setters=lang.backend.template.bindings,
                char=lang.backend.template.char,
                expected=spec.expected,
                split=lang.runtime.split,
                kwargs=spec.kwargs,
            )
        else:
            stdin = encode_inputs(lang.name, spec.bits, truth_table=spec.table)
            example = _reader(
                lang.backend.entrypoint,
                lang.runtime.interpreter,
                table=spec.table,
                inputs=(stdin,)
                if lang.contract.input_shape == "char_stream"
                else tuple(stdin.splitlines()),
                expected=spec.expected,
                split=lang.runtime.split,
                kwargs=spec.kwargs,
            )
        stem = _stem(lang)
        BOOLEAN_EXAMPLES[stem] = replace(
            example,
            stem=stem,
            scale=spec.scale,
            expected_compared=spec.expected_compared,
        )


_register()

__all__ = ["AND2", "BOOLEAN_EXAMPLES", "BooleanExample"]
