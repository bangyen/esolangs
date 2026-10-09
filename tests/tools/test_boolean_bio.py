"""bio generator tests."""

import importlib
import random
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
    wrap_program,
)
from tests.tools.fills import _run_form


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

    def run_bio(self, prog: str, bits: list[int]) -> str:
        from tests.interpreters.runner import run_program

        run = importlib.import_module("esolangs.interpreters.register_based.bio").run
        return run_program(run, prog, "".join(f"{b}\n" for b in bits))

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        """Fill the template the way the example harness does."""
        from tests.tools.fills import fill

        _fill_bio = fill("BIO")

        return _fill_bio(tpl, bits)

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

    def test_each_input_is_stored_once(self) -> None:
        """The packing scheme embeds each input exactly once."""

        from esolangs import tools as generators
        from esolangs.tools.bio import BIO_PAIR
        from esolangs.tools.helpers import runs

        for n in (1, 2, 3):
            table = format(0, f"0{2**n}b")
            template = generators.bio(table)
            assert len(runs(template, "$", (BIO_PAIR,) * n)) == n

    def test_both_bits_embed_at_the_same_width(self) -> None:
        """A zero pads against the unread ``z``, so the program's length
        does not reveal the inputs."""
        from esolangs.tools.bio import BIO_PAIR
        from tests.tools.fills import fill

        _fill_bio = fill("BIO")

        for n in (1, 2, 3):
            template = _run_form(BIO_PAIR, n)
            for i in range(n):
                zeros = [0] * n
                ones = list(zeros)
                ones[i] = 1
                assert len(_fill_bio(template, zeros)) == len(
                    _fill_bio(template, ones)
                ), f"n={n} input {i}"

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

    def test_trailing_run_is_one_level(self) -> None:
        """Entries 2..7 are flat: one bare level re-tests x to zero, still correct."""
        import esolangs

        table = "01000000"
        template = esolangs.generate("BIO", table)
        assert template.split("$$$$")[-1].count("0ix{") == 3
        for row in range(8):
            bits = [row >> s & 1 for s in (2, 1, 0)]
            program = self.instantiate(template, bits)
            assert self.run_bio(program, []) == table[row]


def test_bio_balance_keeps_source_that_does_not_tile_commands():
    assert balance_program("not BIO", "bio") == "not BIO"


def test_bio_nested_spaced_commands_keep_their_structural_runs():
    program = "0ix{0ox; 0ix{0oy;};};"
    balanced = balance_program(program, "bio")
    layouts = [program] + [
        wrap_program(program, "bio", width) for width in range(1, len(program) + 1)
    ]
    assert balance_score(balanced) == min(map(balance_score, layouts))
    assert esolangs.run("BIO", balanced) == esolangs.run("BIO", program) == ""


@pytest.mark.medium
@pytest.mark.parametrize("inputs", [4, 6])
def test_bio_padding_caps_match_every_width(inputs):
    rng = random.Random(1017 + inputs)
    table = "".join(rng.choice("01") for _ in range(1 << inputs))
    default = esolangs.generate("BIO", table)
    balanced = esolangs.generate("BIO", table, balance=True)
    layouts = [default] + [
        esolangs.generate("BIO", table, width=width)
        for width in range(1, len(default) + 1)
    ]
    assert balanced in layouts
    assert balance_score(balanced) == min(map(balance_score, layouts))
    assert _evaluate("BIO", balanced, inputs=inputs) == table


@pytest.mark.medium
@pytest.mark.parametrize("inputs", [7, 10])
def test_bio_saturated_runs_attain_both_geometry_bounds(inputs):
    rng = random.Random(1018 + inputs)
    table = "".join(rng.choice("01") for _ in range(1 << inputs))
    default = esolangs.generate("BIO", table)
    balanced = esolangs.generate("BIO", table, balance=True)
    full = esolangs.generate("BIO", table, width=3 * len(table))
    # Deep runs contain at most three four-cell commands; the last has at
    # least one. A cap over four levels below the deepest cannot attain Wmax.
    depth = len(table) - 1
    lower = 2 * (depth - 4) + 2 * (depth - 4) // 3
    upper = 2 * (depth + 1) + 2 * (depth + 1) // 3
    layouts = [default, full] + [
        esolangs.generate("BIO", table, width=width)
        for width in range(lower, upper + 1)
    ]
    assert balanced in layouts
    assert balance_score(balanced) == min(map(balance_score, layouts))
    assert len(balanced.split("\n")) == 2 * len(table) + 6 * (inputs - 1)
    assert max(map(len, balanced.split("\n"))) == max(map(len, full.split("\n")))
    for row in (0, 1, len(table) // 2, len(table) - 1):
        bits = tuple(map(int, format(row, f"0{inputs}b")))
        output = esolangs.run("BIO", esolangs.instantiate("BIO", balanced, bits))
        assert esolangs.read_answer("BIO", output) == table[row]


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


def test_bio_keeps_a_brace_with_the_command_that_opens_it() -> None:
    """``{`` marks the body of the ``0i?`` before it and never leads a line."""
    lines = _bio(_NESTED_BIO, DEFAULT_WIDTH).split("\n")
    assert not any(line.lstrip(" ").startswith("{") for line in lines)
    assert [line for line in lines if line.rstrip().endswith("{")]


def test_bio_indent_preserves_the_command_sequence() -> None:
    """Indenting is whitespace only: the parser sees the same commands."""
    wrapped = _bio(_NESTED_BIO, DEFAULT_WIDTH)
    assert _bio_tokens(wrapped) == _bio_tokens(_NESTED_BIO)


def test_bio_leaves_a_flat_program_packed() -> None:
    """A program under two levels deep gains no indentation."""
    flat = "0ox;0ix{1ox;0oy;};0oy;1iy;"
    wrapped = _bio(flat, DEFAULT_WIDTH)
    assert not any(line.startswith(" ") for line in wrapped.split("\n"))


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


def test_bio_layouts_differ_only_in_whitespace() -> None:
    same_layout = LANGUAGES["BIO"].same_layout
    assert same_layout is not None
    assert same_layout("a\n b", "a b", lambda _width: "")
    assert not same_layout("ab c", "a b", lambda _width: "")


def test_bio_refuses_a_program_its_tokens_do_not_tile() -> None:
    """A stray character means the regex missed something: left alone."""
    assert _bio("0ox;!!!", 40) == "0ox;!!!"
