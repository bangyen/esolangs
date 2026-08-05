"""Unit tests for the program generator tool."""

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
