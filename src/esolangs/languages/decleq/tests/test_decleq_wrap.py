import pytest

from esolangs.generation.wrap import wrap_program


@pytest.mark.parametrize("width", [0, -1])
def test_nonpositive_width_does_not_wrap(width: int) -> None:
    assert wrap_program("a b c", "decleq", width) == "a b c"


def test_multiline_source_is_untouched() -> None:
    program = "line one\nline two"
    assert wrap_program(program, "decleq", 4) == program
