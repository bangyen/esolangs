"""Unit tests for the boolean-function program generators."""

import io
from contextlib import redirect_stdout
from unittest.mock import patch

import pytest

from esolangs.tools import boolean


def run_sophie(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.register_based.sophie import run

    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs), redirect_stdout(buffer):
        run(program)
    return buffer.getvalue()


class TestSophie:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("11111110", 3),  # NAND3
            ("1111111111111110", 4),  # NAND4
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.sophie(table, n)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_sophie(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_structure(self) -> None:
        """A one-input function is a single conditional pair."""
        assert boolean.sophie("10", 1) == ";@$48{#$49,&}{#$48,&}"


def run_modulous(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.stack_based.modulous import run

    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs), redirect_stdout(buffer):
        run(program)
    return buffer.getvalue()


class TestModulous:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("11111110", 3),  # NAND3
            ("1000000000000000", 4),  # AND4
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.modulous(table, n)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_modulous(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_structure(self) -> None:
        """A one-input function reads one input then branches on it."""
        assert boolean.modulous("10", 1).startswith("[INP INT]")
        assert "[JMP F 2 IF 0]" in boolean.modulous("10", 1)


def run_brainif(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.tape_based.brainif import run

    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs), redirect_stdout(buffer):
        run(program.splitlines())
    return buffer.getvalue()


def run_nevermind(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.other.nevermind import run

    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs), redirect_stdout(buffer):
        run(program.splitlines())
    return buffer.getvalue()


class TestNevermind:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("11111110", 3),  # NAND3
            ("1000000000000000", 4),  # AND4
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.nevermind(table, n)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_nevermind(program, [str(b) for b in bits])
            assert got == str(int(table[combo])) + "\n", f"inputs {bits}"

    def test_structure(self) -> None:
        """A one-input function reads one input and branches on it."""
        program = boolean.nevermind("10", 1)
        assert program.startswith("input,?")
        assert "if,$a,==,0" in program
        assert program.count("endif") == 2


class TestBrainIf:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("11111110", 3),  # NAND3
            ("1000000000000000", 4),  # AND4
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.brainif(table, n)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_brainif(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_structure(self) -> None:
        """A one-input function reads one input then branches on it."""
        program = boolean.brainif("10", 1)
        assert program.startswith("if 0 input")
        assert "if 48 goto" in program


def run_taglate(program: str, inputs: list[str]) -> str:
    import esolangs

    return esolangs.run("Taglate", program, stdin="\n".join(inputs))


class TestTaglate:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("00", 1),
            ("01", 1),
            ("10", 1),
            ("11", 1),
            ("0001", 2),  # AND
            ("0110", 2),  # XOR
            ("1110", 2),  # NAND
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.taglate(table, n)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_taglate(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_all_two_input_tables(self) -> None:
        """Every two-input truth table produces the right result."""
        for table in range(16):
            tt = format(table, "04b")
            for combo in range(4):
                bits = [(combo >> 1) & 1, combo & 1]
                got = run_taglate(boolean.taglate(tt, 2), [str(b) for b in bits])
                assert got == tt[combo], f"{tt} inputs {bits}"

    def test_only_supports_two_inputs(self) -> None:
        with pytest.raises(ValueError, match="n == 2"):
            boolean.taglate("11111110", 3)
