"""Inject diagnostics and public entry point."""

from typing import Any

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO, ScriptedIO
from esolangs.interpreters.other.inject import run
from tests.raises import raises_message

HELLO_WORLD = "\n".join(
    [
        "send data",
        "skip",
        "data;",
        "Hello, world!",
        "data;",
    ]
)

WIKI_TRUTH_MACHINE = "\n".join(
    [
        "readto data",
        "loop;",
        "send data",
        "skipq data 0",
        "loop;",
        "skip",
        "data;",
        "data;",
        "0;",
        "0",
        "0;",
    ]
)

# A corrected truth machine: the wiki's own is inverted (see the
# interpreter's module docstring).  Halts on "0" after printing it, loops
# forever on "1".  Defined here rather than imported from ``tests.samples``
# because that module pulls in the registry, which the mutation bundle does
# not inline -- a module-level import of it fails collection there before
# any mutant runs.  ``tests.samples`` imports this name instead.
INJECT_TRUTH_MACHINE = "\n".join(
    [
        "readto data",
        "skipq data 0",
        "loop;",
        "send data",
        "skip",
        "loop;",
        "send data",
        "skip",
        "data;",
        "data;",
        "0;",
        "0",
        "0;",
    ]
)

CAT = "\n".join(
    [
        "loop;",
        "readto data",
        "send data",
        "skipif data",
        "loop;",
        "data;",
        "data;",
    ]
)


def _run(program: str, stdin: str = "") -> str:
    """Run ``program`` and return everything it printed."""
    io = ScriptedIO(stdin)
    run(program, io)
    return io.getvalue()


class TestMalformed:
    def test_a_third_occurrence_of_a_label_is_rejected(self) -> None:
        with raises_message(ValueError, "label written more than twice: a"):
            _run("a;\na;\na;")

    def test_an_unclosed_block_is_rejected(self) -> None:
        with raises_message(ValueError, "unclosed label-block: a"):
            _run("a;\nsend a")

    def test_an_unknown_label_is_rejected(self) -> None:
        with raises_message(ValueError, "unknown label: nowhere"):
            _run("send nowhere")

    def test_skip_takes_no_argument(self) -> None:
        with raises_message(ValueError, "skip takes no argument: skip please"):
            _run("skip please")

    def test_skipq_needs_two_labels(self) -> None:
        with raises_message(ValueError, "skipq takes two labels: skipq only"):
            _run("skipq only")

    def test_inject_needs_a_regex(self) -> None:
        with raises_message(ValueError, "inject needs a label and a regex: data"):
            _run("inject data")

    def test_inject_needs_a_replacement(self) -> None:
        with raises_message(ValueError, "inject needs a replacement: data=x"):
            _run("inject data=x")

    def test_an_empty_program_halts(self) -> None:
        assert _run("") == ""


def test_main_block_runs_a_file(tmp_path: Any, capsys: Any) -> None:
    """The ``__main__`` entry point reads a program file and runs it."""
    path = tmp_path / "hello.inj"
    path.write_text(HELLO_WORLD, encoding="utf-8")
    run(path.read_text(encoding="utf-8"), IO())
    assert capsys.readouterr().out == "Hello, world!\n"


def test_invalid_regex_is_a_halt_error() -> None:
    program = "\n".join(["inject data=(/x", "send data", "skip", "data;", "a", "data;"])
    with raises_message(HaltError, "invalid regex: ("):
        _run(program)
