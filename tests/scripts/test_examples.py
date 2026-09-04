"""Run every committed example program and check its output.

``examples/`` holds only programs sampled from a *parameterized* generator:
the hello-world programs from ``esolangs.tools.text`` (which takes the text)
and the boolean programs from ``esolangs.tools.boolean`` (which takes a truth
table and an input combination).  Each committed file is one point sampled
from that space, so a companion test keeps it in sync with whatever the
generator produces today -- the check has teeth precisely because the
generator could produce something else.

Fixed programs with no such space -- cat, truth-machine, and multiply -- are
plain test fixtures rather than examples, and live inline in the matching
``tests/interpreters/test_*.py`` instead.
"""

import importlib
import io
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from esolangs import generate
from esolangs.interpreters.io import IO
from esolangs.interpreters.randomness import Seeded
from esolangs.registry import LANGUAGES, canonical_id
from esolangs.tools.boolean.examples import BOOLEAN_EXAMPLES as BOOLEAN_GENERATED
from esolangs.tools.boolean.examples import HAND_WRITTEN
from esolangs.tools.wrap import DEFAULT_WIDTH
from tests.interpreters.runner import run_program
from tests.tools.boolean_runners import one_two_three_result, point_break_result

BASE_DIR = Path(__file__).parents[2]
EXAMPLES_DIR = BASE_DIR / "examples" / "hello-world"


def _file_name(display_name: str) -> str:
    return display_name.lower().replace(" ", "-")


# example file stem -> (interpreter module, split lines), derived
# from the language registry.
EXAMPLES = {
    _file_name(lang.name): (lang.interpreter, lang.split)
    for lang in LANGUAGES.values()
    if lang.text and lang.interpreter
}

# container halts by calling sys.exit(0)
EXITS = {"container"}

# Boolean examples whose answer is their *termination* rather than their
# output: each halts for a 0 and loops forever for a 1, so the committed
# program must be the halting branch.
#
# :func:`test_boolean_example` runs a committed program to completion with no
# step cap, which is right for every other language and fatal for these
# three: a file holding the looping branch does not fail, it hangs the
# suite with no diagnostic.  Nothing about the entry forces the halting row
# -- ``bits`` is just data, and a wrong one regenerates a looping file --
# so :func:`test_halt_convention_examples_halt` checks the committed
# program terminates *before* anything runs it unbounded.
HALT_CONVENTION = {"123", "arrowqueue", "point-break"}

# Boolean generators deliberately without a committed example, by canonical
# id, each for a stated reason.  A language qualifies for an example when its
# answer is recoverable from what its program prints (see
# ``esolangs.tools.boolean.examples``); one whose answer no program can
# report belongs here rather than silently missing.
#
# Empty, and that is the claim: every boolean generator currently has one.
_NO_EXAMPLE: set[str] = set()


def run_example(name: str) -> str:
    module, splitlines = EXAMPLES[name]
    run = importlib.import_module("esolangs.interpreters." + module).run
    program = (EXAMPLES_DIR / f"{name}.txt").read_text(encoding="utf-8").rstrip("\n")
    argument = program.splitlines() if splitlines else program

    buffer = io.StringIO()
    try:
        with redirect_stdout(buffer):
            run(argument, io=IO())
    except SystemExit:
        assert name in EXITS, f"{name} exited unexpectedly"
    return buffer.getvalue()


@pytest.mark.parametrize("name", sorted(EXAMPLES))
def test_hello_world_example(name: str) -> None:
    expected = "Hello, World!"
    assert run_example(name) == expected


def test_example_files_match_generator() -> None:
    """The committed examples are exactly what the generators produce today.

    The files are committed wrapped (see ``scripts/write_examples.py``)
    and end with a single POSIX
    newline, so the comparison is against the generator's output plus that
    newline.
    """
    languages = [lang for lang in LANGUAGES.values() if lang.text and lang.interpreter]
    for lang in languages:
        assert lang.text is not None
        path = EXAMPLES_DIR / f"{_file_name(lang.name)}.txt"
        expected = (
            generate(lang.name, "Hello, World!", DEFAULT_WIDTH).rstrip("\n") + "\n"
        )
        assert path.read_text(encoding="utf-8") == expected


def test_no_example_has_trailing_whitespace() -> None:
    """No committed example ends a line in whitespace.

    Several generators lay their program out on a fixed-width grid and used
    to emit the filler past the last glyph on a row.  It is inert -- the 2D
    interpreters pad short rows themselves -- but it is still whitespace no
    program can use, and ``.pre-commit-config.yaml`` excludes ``examples/``
    from the ``trailing-whitespace`` hook (the files must match their
    generator byte for byte, so the hook cannot be the thing that strips
    them).  The generators rstrip their rows instead, and this test is what
    holds them to it.
    """
    offenders = []
    for path in sorted((BASE_DIR / "examples").rglob("*.txt")):
        for number, line in enumerate(
            path.read_text(encoding="utf-8").split("\n"), start=1
        ):
            if line != line.rstrip():
                offenders.append(f"{path.relative_to(BASE_DIR)}:{number}")
    assert not offenders, "trailing whitespace in: " + ", ".join(offenders)


def test_no_orphan_hello_world_examples() -> None:
    """Every hello-world file belongs to a language that still has a generator.

    The other tests derive their parameters from the registry, so a file for a
    language that was removed is never collected and cannot fail.  Scanning the
    directory is what catches it.
    """
    committed = {path.stem for path in EXAMPLES_DIR.glob("*.txt")}
    assert committed - set(EXAMPLES) == set(), "example files with no generator"
    assert set(EXAMPLES) - committed == set(), "generators with no example file"


@pytest.mark.parametrize("name", sorted(BOOLEAN_GENERATED))
def test_boolean_example_matches_generator(name: str) -> None:
    """Each committed boolean program is what its generator produces today.

    The counterpart of :func:`test_example_files_match_generator` for the
    boolean examples; refresh them with
    ``python scripts/write_examples.py boolean``. The file ends with a
    single POSIX newline.
    """
    path = BASE_DIR / "examples" / "boolean" / f"{name}.txt"
    expected = BOOLEAN_GENERATED[name].build().rstrip("\n") + "\n"
    assert path.read_text(encoding="utf-8") == expected


def test_boolean_examples_cover_every_committed_file() -> None:
    """Every file in examples/boolean is accounted for, and vice versa."""
    on_disk = {p.stem for p in (BASE_DIR / "examples" / "boolean").glob("*.txt")}
    assert on_disk == set(BOOLEAN_GENERATED) | set(HAND_WRITTEN)


@pytest.mark.parametrize("name", sorted(HALT_CONVENTION))
def test_halt_convention_examples_halt(name: str) -> None:
    """The committed program of a halt-convention language terminates.

    These three answer with termination rather than output, so the
    committed file is the halting (0) branch and its expected output is
    empty.  :func:`test_boolean_example` then runs it with no step cap --
    which turns a file holding the *looping* branch into a hung suite
    rather than a failure, with nothing to say which file did it.

    The bound is state-cycle detection, not a step budget: these
    interpreters are step-capable, and a deterministic run that revisits
    its whole internal state has looped forever, so the repeated state
    proves divergence immediately instead of after an arbitrary wait.
    """
    program = (
        (BASE_DIR / "examples" / "boolean" / f"{name}.txt")
        .read_text(encoding="utf-8")
        .rstrip("\n")
    )
    assert _halts(name, program, list(BOOLEAN_GENERATED[name].inputs)), (
        f"examples/boolean/{name}.txt holds the looping branch; the committed "
        f"program must be the halting one or the suite hangs running it"
    )


def _halts(name: str, program: str, inputs: list[str]) -> bool:
    """Whether ``name``'s committed program terminates, by cycle detection.

    ``inputs`` are the example's own stdin lines: 123 and ArrowQueue embed
    their bits and read nothing, but Point Break reads its two with ``?``,
    so running it on an empty stdin raises ``EOFError`` instead of
    answering the question this test asks.
    """
    from esolangs.vm import run_until_halt_or_cycle

    if name == "arrowqueue":
        from esolangs.interpreters.grid_based.arrowqueue import _Machine as AQ

        return run_until_halt_or_cycle(AQ(program.splitlines()))
    if name == "123":
        return one_two_three_result(program) == "0"
    return point_break_result(program, inputs) == "0"


def test_every_boolean_generator_has_an_example() -> None:
    """Every registered boolean generator has a committed example.

    The check above compares the files on disk against
    :data:`BOOLEAN_EXAMPLES`, which is the hand-maintained table in
    ``esolangs.tools.boolean.examples``.  A generator absent from *both* --
    no entry and so no file -- cancels out of that comparison and is
    invisible to it, which is how seven generators (%^2^-1, 123, CV(N)(C),
    Fargo, Minifuck, SLOW ACV MAMMALIAN and Super SNUSP) went uncovered.

    The registry is the only source that knows a generator exists, so it is
    what this test compares against.  A language whose answer no program can
    report belongs in :data:`_NO_EXAMPLE` with the reason, not silently
    missing -- an empty exemption set is the assertion that none exist.
    """
    registered = {
        canonical_id(lang.name) for lang in LANGUAGES.values() if lang.boolean
    }
    covered = {
        canonical_id(stem.replace("-", " "))
        for stem in set(BOOLEAN_GENERATED) | set(HAND_WRITTEN)
    }
    assert registered - covered == _NO_EXAMPLE, (
        "boolean generators with no committed example: "
        f"{sorted(registered - covered - _NO_EXAMPLE)}"
    )


def test_every_text_generator_has_an_example() -> None:
    """Every registered text generator has a committed hello-world file.

    :func:`test_no_orphan_hello_world_examples` already asserts this, but it
    does so against ``EXAMPLES``, which is *derived* from the registry by
    the same comprehension -- so the two sides move together and the
    equality holds by construction rather than by the files being there.
    This compares the registry against the directory directly, which is what
    a missing file actually violates.

    A language with a text generator but no interpreter is exempt: nothing
    can run its program, so ``EXAMPLES`` skips it and no file is written.
    """
    registered = {
        _file_name(lang.name)
        for lang in LANGUAGES.values()
        if lang.text and lang.interpreter
    }
    on_disk = {path.stem for path in EXAMPLES_DIR.glob("*.txt")}
    assert registered - on_disk == set(), (
        f"text generators with no committed example: {sorted(registered - on_disk)}"
    )


# The boolean examples demonstrate a language's boolean-function capability
# that is not an I/O truth machine (see docs/walls.md).  They are derived
# from ``esolangs.tools.boolean.examples``, which records for each committed
# program the generator, truth table, and input combination that produced it
# -- so the files stay in sync with the generators the way the hello-world
# examples do.
#
# The input-reading languages take their bits on stdin; the parameterized
# ones (see ``esolangs.tools.boolean.parameterized``) have the bits embedded
# in the program text and read no input.  ArrowQueue and Point Break have no
# output at all: their result is the halt-vs-loop convention, so only the
# terminating (`0`) branch is committed -- the `1` branch loops forever by
# definition and is not executed.
BOOLEAN_EXAMPLES = {
    stem: (ex.interpreter, list(ex.inputs), ex.expected, ex.split, dict(ex.kwargs))
    for stem, ex in BOOLEAN_GENERATED.items()
} | {
    stem: (interpreter, list(inputs), expected, split, {})
    for stem, (interpreter, inputs, expected, split) in HAND_WRITTEN.items()
}


@pytest.mark.parametrize("name", sorted(BOOLEAN_EXAMPLES))
def test_boolean_example(name: str) -> None:
    module, inputs, expected, splitlines, kwargs = BOOLEAN_EXAMPLES[name]
    run = importlib.import_module("esolangs.interpreters." + module).run
    # ``kwargs`` carries ints, so a language whose chance has to be pinned
    # names a seed and the source is built here.  LaserFuck draws its
    # initial heading, so without this the example would start in a random
    # direction and its committed output would only sometimes be right.
    if "seed" in kwargs:
        kwargs = {k: v for k, v in kwargs.items() if k != "seed"}
        kwargs["rng"] = Seeded(BOOLEAN_EXAMPLES[name][4]["seed"])
    program = (
        (BASE_DIR / "examples" / "boolean" / f"{name}.txt")
        .read_text(encoding="utf-8")
        .rstrip("\n")
    )
    argument = program.splitlines() if splitlines else program

    # Container halts by calling sys.exit(0), like its hello-world example.
    got = run_program(
        run,
        argument,
        "".join(f"{line}\n" for line in inputs),
        suppress_exit=True,
        **kwargs,
    )
    assert got == expected
