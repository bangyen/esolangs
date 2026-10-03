import importlib

from tests.interpreters.contract import CycleContract, SnapshotContract
from tests.interpreters.runner import run_program

sixfive = importlib.import_module("esolangs.interpreters.tape_based.six_five")


def run_and_capture(code: str, inputs: list[str] | None = None) -> str:
    return run_program(sixfive.run, code, "".join(f"{line}\n" for line in inputs or []))


HELLO_WORLD = "\n".join(
    [
        "666666666666A C",
        "66665A C",
        "662AA C",
        "626262A C",
        "9999999999995A C",
        "99A C",
        "55555555555A C",
        "6666A C",
        "626262A C",
        "9A C",
        "95959A C",
    ]
)


class TestSixFive:
    def test_hello_world(self) -> None:
        assert run_and_capture(HELLO_WORLD) == "Hello, World"

    def test_the_marker_index_is_the_scan_taken_once(self) -> None:
        """``8n`` lands where a scan for the n-th ``4`` would, from the index.

        The machine builds the index at construction, and a transition
        handed no index scans for itself -- both paths must agree.
        """
        from esolangs.interpreters.io import ScriptedIO

        machine = sixfive._Machine("4A82A40", ScriptedIO(""))  # noqa: SLF001
        assert machine.markers == (0, 4)
        toks = machine.toks
        jumped = sixfive._advance((2, 0, (0,)), toks)  # noqa: SLF001
        assert jumped == sixfive._advance((2, 0, (0,)), toks, None, machine.markers)  # noqa: SLF001
        assert jumped[0] == 5
        assert sixfive._marker(machine.markers, 3) is None  # noqa: SLF001
        assert sixfive._marker(machine.markers, 0) is None  # noqa: SLF001


class TestComments:
    """The leading-comment regression."""

    def test_a_comment_on_the_first_line(self) -> None:
        """The ``C`` may be the program's first character.

        The old pattern captured the character before ``C``, so it needed
        one and a leading comment survived as source.
        """
        from esolangs.interpreters.tape_based.six_five import _tokens

        assert _tokens("C hidden") == []
        assert run_and_capture("C66666666A0\n66666666A0") == "0"


def _machine(code: object) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.six_five import _Machine

    return _Machine(code, ScriptedIO())


class TestContract(SnapshotContract, CycleContract):
    """The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    stepping_program = "55A"
    halting_program = "55A"
    looping_program = "481"
