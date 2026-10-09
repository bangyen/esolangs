"""RAM0 through the shared API, CLI and machinery."""

import subprocess
import sys
from pathlib import Path

import pytest

import esolangs
from esolangs._evaluate import _evaluate
from tests.stdin_check import _check_stdin


def test_bound_template_language_runs_each_input_row():
    language = esolangs.Language("RAM0")
    template = language.generate("0110", width=1)
    assert _evaluate(language.name, template, timeout=None, inputs=2) == "0110"
    for row, answer in enumerate("0110"):
        bits = tuple(map(int, format(row, "02b")))
        program = language.instantiate(template, bits, width=1, truth_table="0110")
        assert language.read_answer(language.run(program, max_steps=1000)) == answer


# waits out real stdin timeouts: drives the CLI as a subprocess.
@pytest.mark.medium
class TestStdinCannotHangTheCommandForever:
    """`run` read stdin to EOF before doing anything, and --timeout missed it."""

    def _run_with_open_stdin(self, args: list[str], wait: float) -> tuple[int, str]:
        """Start the CLI with stdin held open and never written."""
        proc = subprocess.Popen(
            [sys.executable, "-m", "esolangs", *args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            proc.wait(timeout=wait)
        except subprocess.TimeoutExpired:
            proc.kill()
            return -1, ""
        finally:
            if proc.stdin:
                proc.stdin.close()
        return proc.returncode, proc.stderr.read() if proc.stderr else ""

    @pytest.mark.slow
    def test_a_timeout_bounds_the_read(self, tmp_path: Path) -> None:
        """It bounded execution only, and the block happens before that."""
        path = tmp_path / "p.txt"
        path.write_text(esolangs.generate("brainfuck", "0110"))
        code, err = self._run_with_open_stdin(
            ["run", "--timeout", "2", "brainfuck", str(path)], 20
        )
        assert code == 124
        assert "no input arrived on stdin" in err

    @pytest.mark.slow
    def test_an_unknown_language_is_named_without_reading_stdin(
        self, tmp_path: Path
    ) -> None:
        """It blocked forever before saying the one thing it already knew."""
        path = tmp_path / "p.txt"
        path.write_text("+.")
        code, err = self._run_with_open_stdin(
            ["run", "--timeout", "30", "NotALang", str(path)], 20
        )
        assert code == 2
        assert "unknown language" in err

    @pytest.mark.slow
    def test_a_language_that_reads_no_stdin_is_told_so(self, tmp_path: Path) -> None:
        """RAM0 embeds its inputs, so the wait was for input nobody wanted."""
        path = tmp_path / "p.txt"
        path.write_text(
            esolangs.instantiate("RAM0", esolangs.generate("RAM0", "0110"), [0, 1])
        )
        code, err = self._run_with_open_stdin(
            ["run", "--timeout", "2", "RAM0", str(path)], 20
        )
        assert code == 124
        assert "read no stdin" in err


class TestDescribeHasANameableType:
    """``dict[str, object]`` was accurate and useless."""

    def test_it_is_exported(self) -> None:
        """A type you cannot name is a type you cannot annotate with."""
        assert "LanguageInfo" in esolangs.__all__
        assert esolangs.LanguageInfo.__doc__

    def test_every_key_is_declared(self) -> None:
        """The TypedDict and the dict must not drift apart."""
        declared = set(esolangs.LanguageInfo.__annotations__)
        assert declared == set(esolangs.describe("brainfuck"))

    def test_every_language_matches_the_declared_types(self) -> None:
        """Declared from a survey of every one, so it is checked against them all."""
        import typing

        hints = typing.get_type_hints(esolangs.LanguageInfo)
        for name in esolangs.list_languages():
            for key, value in esolangs.describe(name).items():
                expected = hints[key]
                if expected is str:
                    assert isinstance(value, str), (name, key)
                elif expected is bool:
                    assert isinstance(value, bool), (name, key)
                elif expected == list[str]:
                    assert isinstance(value, list), (name, key)
                    assert all(isinstance(v, str) for v in value), (name, key)
                elif expected == tuple[str, str]:
                    assert isinstance(value, tuple), (name, key)
                    assert len(value) == 2, (name, key)
                elif typing.get_origin(expected) is dict:
                    assert isinstance(value, dict), (name, key)
                    assert all(isinstance(k, str) for k in value), (name, key)
                    assert all(isinstance(v, dict) for v in value.values()), (name, key)
                elif expected == int | None:
                    assert value is None or type(value) is int, (name, key)
                else:  # the strings that may be None, never ""
                    assert value is None or (isinstance(value, str) and value), (
                        name,
                        key,
                    )
                    assert value is None or isinstance(value, str), (name, key)

    def test_the_four_machine_traits_are_still_carried(self) -> None:
        """They were merged with ``**``, which a TypedDict cannot verify."""
        facts = esolangs.describe("RAM0")
        for key in (
            "self_halts",
            "dumps_on_the_post_halt_step",
            "steppable_to_answer",
            "eof_is_a_value",
        ):
            assert isinstance(facts[key], bool), key  # type: ignore[literal-required]


@pytest.mark.medium
def test_execution_does_not_require_examples_or_docstrings(monkeypatch) -> None:
    from esolangs import _describe
    from esolangs.tools import examples

    def refuse_documentation(_language):
        raise AssertionError("execution requested documentation")

    program = esolangs.generate("brainfuck", "0110")
    monkeypatch.setattr(_describe, "_spec", refuse_documentation)
    monkeypatch.setattr(examples, "BOOLEAN_EXAMPLES", {})
    assert esolangs.encode_inputs("brainfuck", [0, 1]) == "01"
    _check_stdin("brainfuck", "01", "0110")
    assert esolangs.read_answer("RAM0", "z: 1\nn: 0") == "1"
    assert _evaluate("brainfuck", program, inputs=2) == "0110"
