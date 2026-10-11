"""bio generator tests."""

import re

import pytest

import esolangs
from esolangs._evaluate import _evaluate
from esolangs.registry import LANGUAGES
from esolangs.tools.wrap import (
    DEFAULT_WIDTH,
    _bio,
    balance_program,
    balance_score,
)


@pytest.mark.medium
@pytest.mark.parametrize("bit", ["0", "1"])
def test_constant_root_keeps_setters_without_index_save_loops(bit):
    from esolangs.debugger import make_vm
    from esolangs.tools.bio import BIO_PAIR, _bio
    from esolangs.tools.helpers import input_weights, mark_runs, unmark

    table = bit * 256
    template = esolangs.generate("BIO", table)
    assert "{" not in template
    assert len(template) == 4 * 8 + 4 * (49 + int(bit))
    assert _evaluate("BIO", template, inputs=8) == table
    weights, projected = input_weights(table, 8)
    legacy = _bio(projected, weights, keep_constant_input=True)
    marked = mark_runs(legacy, "$", (BIO_PAIR,) * 8)
    old_balance = unmark(balance_program(marked, "bio"), "$", 8)
    balanced = esolangs.generate("BIO", table, balance=True)
    assert balance_score(balanced) <= balance_score(old_balance)
    assert _evaluate("BIO", balanced, inputs=8) == table
    for row in (0, 1, 128, 255):
        bits = [int(c) for c in f"{row:08b}"]
        vm = make_vm("BIO", esolangs.instantiate("BIO", template, bits))
        commands = 0
        while not vm.halted and commands < 58:
            vm.step()
            commands += 1
        assert vm.halted
        assert vm.output == bit
        assert commands == 8 + 49 + int(bit)


class TestParameterizedBIO:
    """Input-by-substitution generators for the no-input language BIO."""

    def test_template_is_input_independent(self) -> None:
        """The template has input runs, not hardcoded bits."""
        from esolangs import tools as generators
        from esolangs.tools.bio import BIO_PAIR
        from esolangs.tools.helpers import runs

        template = generators.bio("0110")
        # one four-character unit per input; the doubling between them
        # (eight commands, 32 characters) carries the first input's weight
        double = "0ix{1ox;0oy;0oy;};0iy{1oy;0ox;};"
        assert template.startswith("$$$$" + double + "$$$$")
        assert runs(template, "$", (BIO_PAIR,) * 2) == [(0, 4), (36, 40)]

    def test_padding_never_touches_a_read_register(self) -> None:
        """``z`` is inert: the generator emits no command that reads it."""
        from esolangs import tools as generators

        for n in (1, 2, 3):
            template = generators.bio(format(0, f"0{2**n}b"))
            assert "z" not in template.lower()

    def test_every_input_is_the_same_pair(self) -> None:
        """The weight lives in the template: one ``(zero, one)`` at every arity."""
        import esolangs

        for n in range(1, 7):
            setters = esolangs.generate("BIO", "01" * (2 ** (n - 1))).setters
            assert set(setters) == {("0oz;", "0ox;")}, n
            assert len(setters) == n


def test_bio_balance_keeps_source_that_does_not_tile_commands():
    assert balance_program("not BIO", "bio") == "not BIO"


def test_bio_layouts_differ_only_in_whitespace() -> None:
    same_layout = LANGUAGES["BIO"].same_layout
    assert same_layout is not None
    assert same_layout("a\n b", "a b", lambda _width: "")
    assert not same_layout("ab c", "a b", lambda _width: "")


# A three-level nest around a short ramp, in the shape the boolean BIO
# generator emits: each level decrements ``x`` and the innermost tops ``y``
# up before the closers unwind.
_NESTED_BIO = "0ox; 0ix{1ox;0ix{1ox;0oy;};};0oy;0oy;1iy;"


def _bio_tokens(program: str) -> list[str]:
    """The commands BIO's own parser keeps, in order."""
    return re.findall(r"[01][oOiI][xXyYzZ](?:\{|;)|\};", program)


def test_bio_indents_a_nested_program_by_depth() -> None:
    """Each loop level is two spaces deeper than the one outside it."""
    lines = _bio(_NESTED_BIO, DEFAULT_WIDTH).split("\n")
    indents = [len(line) - len(line.lstrip(" ")) for line in lines]
    assert indents == [0, 2, 4, 2, 0, 0]


def test_bio_indent_preserves_the_command_sequence() -> None:
    """Indenting is whitespace only: the parser sees the same commands."""
    wrapped = _bio(_NESTED_BIO, DEFAULT_WIDTH)
    assert _bio_tokens(wrapped) == _bio_tokens(_NESTED_BIO)


def test_bio_packs_a_ramp_to_the_width_at_its_own_indent() -> None:
    """A long straight run costs rows at its level, not one long line."""
    program = "0ox;0ix{" + "0oy;" * 40 + "0ix{1ox;};};"
    lines = _bio(program, 20).split("\n")
    assert max(len(line) for line in lines) <= 20
    # The ramp sits inside the outer loop, so every one of its rows is
    # indented rather than only the first.
    ramp = [line for line in lines if "0oy" in line]
    assert len(ramp) > 1
    assert all(line.startswith("  ") for line in ramp)


def test_bio_indent_stops_growing_before_it_crowds_the_line() -> None:
    """A deep program keeps room to pack, and still unwinds its closers."""
    depth = 40
    program = "0ox;" + "0ix{" * depth + "1ox;" + "};" * depth
    lines = _bio(program, 20).split("\n")
    assert max(len(line) for line in lines) <= 20
    assert _bio_tokens("\n".join(lines)) == _bio_tokens(program)


def test_bio_indent_leaves_no_trailing_whitespace() -> None:
    """No line carries the separator the boolean generator writes."""
    wrapped = _bio(_NESTED_BIO, DEFAULT_WIDTH)
    assert all(line == line.rstrip() for line in wrapped.split("\n"))


def test_bio_refuses_a_program_its_tokens_do_not_tile() -> None:
    """A stray character means the regex missed something: left alone."""
    assert _bio("0ox;!!!", 40) == "0ox;!!!"
