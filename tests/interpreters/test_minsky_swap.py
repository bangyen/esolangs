"""Minsky Swap malformed-source and shared VM contracts."""

import pytest

from esolangs.interpreters.io import IO
from esolangs.interpreters.register_based.minsky_swap import run
from tests.interpreters.contract import (
    CycleContract,
    SnapshotContract,
    StateViewContract,
)
from tests.raises import raises_message


class TestMinskySwapReadableNotation:
    @pytest.mark.parametrize(
        "code",
        [
            "inc();swap();",
            "inc(); swap();",
            "inc(); +",
            "inc();\n+",
            "inc(1+2);\ninc();",
        ],
    )
    def test_readable_notation_requires_one_command_per_line(self, code: str) -> None:
        with raises_message(ValueError, "RMSN requires one command per line"):
            run(code, io=IO())


class TestMinskySwapEdgeCases:
    def test_tilde_without_target_rejected(self) -> None:
        """A ~ with no matching jump-line number is malformed.

        ``match=`` is a substring search, so the whole message is asserted
        here: it is the only thing a caller sees when a program is
        rejected, and nothing else pins its wording.
        """
        with raises_message(ValueError, "unmatched '~' with no jump target"):
            run("~~\n1", io=IO())


def _machine(code: object) -> object:
    from esolangs.interpreters.io import IO
    from esolangs.interpreters.register_based.minsky_swap import _Machine

    return _Machine(code, IO())


class TestContract(SnapshotContract, CycleContract, StateViewContract):
    """The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    stepping_program = "+"
    halting_program = "+"
    looping_program = "~\n1"
    # `dumped` only flips on the step *after* the halt, where this language
    # prints its registers, so the contract's run-to-halt leaves it False.
    # It is still read either side, which is what the view is here to pin;
    # `reg` and `ip` are what move.
    state_views = ("ptr", "reg", "dumped", "ip", "memory")
    # `*` swaps the register pair, so the pointer moves as well as the
    # register.  `dumped` latches on the step past the halt, which the
    # check does not take.
    viewing_program = "*+"
    constant_views = frozenset({"dumped"})
