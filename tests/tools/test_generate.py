"""Unit tests for the program generator tool."""

from unittest.mock import patch

import pytest

import esolangs.tools.generate as gen
from esolangs.interpreters.other.container import run as container_run
from esolangs.interpreters.stack_based.bfstack import run as bfstack_run
from esolangs.interpreters.tape_based.brainif import run as brainif_run


def roundtrip(interpreter, program):
    import io
    from contextlib import redirect_stdout

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        interpreter(program)
    return buffer.getvalue()


class TestGeneratorRoundTrips:
    def test_bfstack(self) -> None:
        assert roundtrip(bfstack_run, gen.bfstack("Hi")) == "Hi"

    def test_brainif(self) -> None:
        assert roundtrip(brainif_run, gen.brainif("Hi").splitlines()) == "Hi"

    def test_container(self) -> None:
        import contextlib
        import io

        import pytest

        buffer = io.StringIO()
        with pytest.raises(SystemExit):
            with contextlib.redirect_stdout(buffer):
                container_run(gen.container("Hi").splitlines())
        assert buffer.getvalue() == "Hi"


class TestGeneratorProducesOutput:
    def test_supported_languages(self) -> None:
        """Every generator produces non-empty output for non-empty text."""
        generators = [
            gen.forth,
            gen.laserfuck,
            gen.magnitude,
            gen.painfuck,
            gen.suffolk,
            gen._123,
        ]
        for gen_fn in generators:
            assert gen_fn("Hi"), gen_fn.__name__


class TestGeneratorBranches:
    def test_bfstack_large_drop(self) -> None:
        """A large drop between characters takes the reset branch."""
        output = gen.bfstack("a\x01")
        assert "[-]" in output

    def test_brainif_decreasing(self) -> None:
        """A decreasing character takes the move-right branch."""
        assert "move right" in gen.brainif("ba")

    def test_container_empty(self) -> None:
        assert gen.container("") == "EXIT=1:\n-1 EXIT>=0"

    def test_container_decreasing_char(self) -> None:
        """A character lower than the previous one takes the negative branch."""
        assert "-1 A>=" in gen.container("ba")

    def test_suffolk_empty(self) -> None:
        assert gen.suffolk("") == "\n"

    def test_123_empty(self) -> None:
        assert gen._123("") == "1"

    def test_main_prints_all(self, capsys: pytest.CaptureFixture) -> None:
        with patch("sys.argv", ["esolangs.tools.generate", "Hi"]):
            gen.main()
        out = capsys.readouterr().out
        assert "--- BFStack ---" in out
        assert "--- BrainIf ---" in out
