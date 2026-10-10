"""Unit tests for Minsky Swap interpreter."""

import io
from contextlib import redirect_stdout

import pytest

from esolangs.interpreters.io import IO
from esolangs.interpreters.register_based.minsky_swap import run
from tests.interpreters.contract import (
    CycleContract,
    SnapshotContract,
    StateViewContract,
)
from tests.interpreters.runner import run_printing
from tests.raises import raises_message


class TestMinskySwapBasicCommands:
    @pytest.mark.parametrize(
        ("code", "expected", "code2", "expected2"),
        [
            pytest.param("+", "1 0", "++", "2 0", id="increment_command"),
            pytest.param("*+", "0 1", "+*+", "1 1", id="swap_command"),
            # ~ jumps to command 2 (the +) since the register is zero
            pytest.param("+~\n1", "0 0", "~+\n2", "1 0", id="decrement_jump_command"),
        ],
    )
    def test_command_pairs(
        self, code: str, expected: str, code2: str, expected2: str
    ) -> None:
        with redirect_stdout(io.StringIO()) as f:
            run(code, io=IO())
        assert f.getvalue().strip() == expected

        with redirect_stdout(io.StringIO()) as f:
            run(code2, io=IO())
        assert f.getvalue().strip() == expected2

    def test_jump_targets(self) -> None:
        with redirect_stdout(io.StringIO()) as f:
            run("~+~\n2 1", io=IO())
        assert f.getvalue().strip() == "0 0"

    def test_stripped_characters_do_not_shift_the_jump_targets(self) -> None:
        """Padding is removed, rather than replaced with something inert."""
        with redirect_stdout(io.StringIO()) as f:
            run(" ~++\n3", io=IO())
        assert f.getvalue().strip() == "1 0"


class TestMinskySwapReadableNotation:
    def test_swap_command_readable(self) -> None:
        f = run_printing(run, "swap();\ninc();")
        assert f.strip() == "0 1"

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

    def test_a_readable_command_contributes_exactly_one_symbol(self) -> None:
        """Each ``inc()``/``swap()`` becomes one command, not a run of them."""
        with redirect_stdout(io.StringIO()) as f:
            run("decnz(5);\ninc();\nswap();\ninc();\ninc();", io=IO())
        assert f.getvalue().strip() == "1 0"

    def test_blank_lines_between_readable_commands_are_skipped(self) -> None:
        outputs = []
        for code in ("inc();\ninc();", "inc();\n\n  \ninc();"):
            f = run_printing(run, code)
            outputs.append(f)
        assert outputs[0] == outputs[1]

    def test_a_bare_decnz_jumps_to_the_first_line(self) -> None:
        """``decnz();`` with no argument targets line 1."""
        from esolangs.interpreters.register_based.minsky_swap import _Machine

        machine = _Machine("decnz();", IO())
        machine.step()  # zero register, so the tilde jumps
        assert machine.ind == 0, "the jump returned to the first command"
        assert not machine.halted


class TestMinskySwapProgramFlow:
    def test_simple_loop(self) -> None:
        with redirect_stdout(io.StringIO()) as f:
            run("+++~\n1", io=IO())
        assert f.getvalue().strip() == "2 0"

    def test_conditional_jump(self) -> None:
        with redirect_stdout(io.StringIO()) as f:
            run("++~+~\n2 1", io=IO())
        assert f.getvalue().strip() == "1 0"


class TestMinskySwapEdgeCases:
    def test_empty_jump_line(self) -> None:
        with redirect_stdout(io.StringIO()) as f:
            run("+\n", io=IO())
        assert f.getvalue().strip() == "1 0"

    def test_invalid_jump_target(self) -> None:
        f = run_printing(run, "~\n999")
        assert f.strip() == "0 0"

    def test_tilde_without_target_rejected(self) -> None:
        """A ~ with no matching jump-line number is malformed."""
        with raises_message(ValueError, "unmatched '~' with no jump target"):
            run("~~\n1", io=IO())


class TestStepMachine:
    def test_the_register_dump_happens_once(self) -> None:
        """Stepping a halted machine again does not re-print the registers."""
        import io
        from contextlib import redirect_stdout

        from esolangs.interpreters.register_based.minsky_swap import _Machine

        machine = _Machine("+", IO())
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            while not machine.halted:
                machine.step()
            machine.step()  # the dump
            machine.step()  # once halted and dumped, a no-op
        assert buffer.getvalue().strip() == "1 0"

    def test_a_decrement_targeting_line_zero_falls_through(self) -> None:
        """A jump target of ``0`` is falsy, so ``~`` advances instead."""
        from esolangs.interpreters.register_based.minsky_swap import _Machine

        machine = _Machine("~\n0", IO())  # zero register, target line 0
        machine.step()
        assert machine.reg == (0, 0), "nothing to decrement"
        assert machine.ind == 1, "the cursor advanced rather than jumping"


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


class TestStateViewValues:
    """The named views read the slots they claim, not one another."""

    def test_ptr_is_the_register_pointer_not_the_cursor(self) -> None:
        """The swap moves the pointer once; the cursor moves every step."""
        machine = _machine("*+")
        while not machine.halted:
            machine.step()
        assert machine.ptr == 1
        assert machine.ip == 2
