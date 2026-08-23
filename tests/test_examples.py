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
from contextlib import redirect_stdout, suppress
from pathlib import Path
from unittest.mock import patch

import pytest

from esolangs.interpreters.io import IO
from esolangs.registry import LANGUAGES
from esolangs.tools.boolean.examples import BOOLEAN_EXAMPLES as BOOLEAN_GENERATED
from esolangs.tools.boolean.examples import HAND_WRITTEN
from esolangs.tools.wrap import DEFAULT_WIDTH, wrap_program

BASE_DIR = Path(__file__).parent.parent
EXAMPLES_DIR = BASE_DIR / "examples" / "hello-world"


def _file_name(display_name: str) -> str:
    return display_name.lower().replace(" ", "-")


# example file stem -> (interpreter module, split lines, kwargs), derived
# from the language registry.
EXAMPLES = {
    _file_name(lang.name): (lang.interpreter, lang.split, dict(lang.kwargs))
    for lang in LANGUAGES.values()
    if lang.generator and lang.interpreter
}

# container halts by calling sys.exit(0)
EXITS = {"container"}


def run_example(name: str) -> str:
    module, splitlines, kwargs = EXAMPLES[name]
    run = importlib.import_module("esolangs.interpreters." + module).run
    program = (EXAMPLES_DIR / f"{name}.txt").read_text(encoding="utf-8").rstrip("\n")
    argument = program.splitlines() if splitlines else program

    buffer = io.StringIO()
    try:
        with redirect_stdout(buffer):
            run(argument, io=IO(), **kwargs)
    except SystemExit:
        assert name in EXITS, f"{name} exited unexpectedly"
    return buffer.getvalue()


@pytest.mark.parametrize("name", sorted(EXAMPLES))
def test_hello_world_example(name: str) -> None:
    expected = "Hello, World!\n" if name == "nevermind" else "Hello, World!"
    assert run_example(name) == expected


def test_example_files_match_generator() -> None:
    """The committed examples are exactly what the generators produce today.

    The files are committed wrapped (see
    ``scripts/write_hello_world_examples.py``), so the comparison wraps the
    generator's output the same way rather than loosening to ignore
    newlines -- a wrapped file still has to match character for character.
    """
    languages = [
        lang for lang in LANGUAGES.values() if lang.generator and lang.interpreter
    ]
    for lang in languages:
        assert lang.generator is not None
        path = EXAMPLES_DIR / f"{_file_name(lang.name)}.txt"
        expected = wrap_program(lang.generator("Hello, World!"), lang.id, DEFAULT_WIDTH)
        assert path.read_text(encoding="utf-8") == expected


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
    ``python scripts/write_boolean_examples.py``.
    """
    path = BASE_DIR / "examples" / "boolean" / f"{name}.txt"
    committed = path.read_text(encoding="utf-8").rstrip("\n")
    assert committed == BOOLEAN_GENERATED[name].build().rstrip("\n")


def test_boolean_examples_cover_every_committed_file() -> None:
    """Every file in examples/boolean is accounted for, and vice versa."""
    on_disk = {p.stem for p in (BASE_DIR / "examples" / "boolean").glob("*.txt")}
    assert on_disk == set(BOOLEAN_GENERATED) | set(HAND_WRITTEN)


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
    program = (
        (BASE_DIR / "examples" / "boolean" / f"{name}.txt")
        .read_text(encoding="utf-8")
        .rstrip("\n")
    )
    argument = program.splitlines() if splitlines else program

    buffer = io.StringIO()
    # Container halts by calling sys.exit(0), like its hello-world example.
    with (
        patch("builtins.input", side_effect=inputs),
        redirect_stdout(buffer),
        suppress(SystemExit),
    ):
        run(argument, io=IO(), **kwargs)
    assert buffer.getvalue() == expected
