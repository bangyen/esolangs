"""Independent Thue parsing, all-draw transitions and generated execution."""

import itertools
import random

import pytest

from esolangs import generate
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.thue import _Machine
from esolangs.tools.thue import thue
from tests.interpreters.thue_reference import Reference


class Draw:
    def __init__(self, choice):
        self.choice = choice
        self.calls = []

    def randbelow(self, upper):
        self.calls.append(upper)
        assert 0 <= self.choice < upper
        return self.choice


def check(source, stdin=""):
    try:
        reference = Reference(source, stdin)
    except ValueError:
        with pytest.raises(ValueError, match=r"."):
            _Machine(source, ScriptedIO(stdin))
        return
    matches = reference.matches()
    for choice in range(max(1, len(matches))):
        reference = Reference(source, stdin)
        io = ScriptedIO(stdin)
        draw = Draw(choice)
        native = _Machine(source, io, draw)
        assert native.rules == tuple(reference.rules)
        assert native.state == reference.state
        assert native.ip == (matches[0] if matches else ())
        assert native.halted == (not matches)
        assert native.branching_snapshot() == reference.state
        assert native.branching_halted(reference.state) == (not matches)
        assert (
            native.branching_successors(reference.state, 100) == reference.successors()
        )
        assert not draw.calls
        try:
            reference.step(choice)
        except EOFError:
            with pytest.raises(EOFError):
                native.step()
        else:
            native.step()
        assert native.snapshot() == (reference.state, reference.offset)
        assert io.getvalue() == reference.output
        assert io.reads == reference.reads
        assert draw.calls == ([len(matches)] if matches else [])


@pytest.mark.medium
def test_all_rule_occurrences_outputs_and_input_transitions():
    words = [
        "".join(chars)
        for length in range(4)
        for chars in itertools.product("ab", repeat=length)
    ]
    rights = ("", "a", "ba", "~", "~x", ":::")
    for left, right, state, stdin in itertools.product(
        words[1:], rights, words, ("", "\n", " a\r\nb")
    ):
        check(f"{left}::={right}\n::=\n{state}", stdin)
    for left, right, left2, right2, state in itertools.product(
        ("a", "b", "aa", "ab", "ba"),
        rights,
        ("a", "b", "aa", "ab", "ba"),
        rights,
        words,
    ):
        check(f"{left}::={right}\n{left2}::={right2}\n::=\n{state}", "a\nb")


@pytest.mark.parametrize(
    "source",
    [
        "",
        "a::=b",
        "::=x\n::=\na",
        "nonsense\n::=\na",
        "\n::=\na",
        "a::=b\n \t::=\r \na\nb\n",
        "a::=:::x\n::=\na",
        "a::=~~\n::=\na",
        "a::=x::=y\n::=\na",
        " ::==\n::=\n ",
        "::=\n:::",
        "a::=b\r\n::=\na",
        "::=\nfirst\nsecond\n",
    ],
)
def test_syntax_special_rule_boundaries_and_multiline_states(source):
    check(source)


class OnlyDraw:
    def __init__(self):
        self.calls = 0

    def randbelow(self, upper):
        assert upper == 1
        self.calls += 1
        return 0


def check_generated(source, table, row):
    n = len(table).bit_length() - 1
    stdin = "\n".join(f"{row:0{n}b}")
    reference = Reference(source, stdin)
    io = ScriptedIO(stdin)
    rng = OnlyDraw()
    native = _Machine(source, io, rng)
    assert native.rules == tuple(reference.rules)
    for step in range(5 * len(table) + 4 * n + 20):
        available = reference.matches()
        assert native.snapshot() == (reference.state, reference.offset)
        assert io.getvalue() == reference.output
        assert native.halted == (not available)
        assert native.ip == (available[0] if available else ())
        if not available:
            native.step()
            assert native.snapshot() == (reference.state, reference.offset)
            assert rng.calls == step
            break
        assert len(available) == 1
        reference.step(0)
        native.step()
    else:
        pytest.fail("bounded generated Thue control exhausted")
    assert reference.output == table[row]
    assert reference.state == ""
    assert reference.reads == io.reads == n
    assert reference.offset == len(stdin)


@pytest.mark.medium
def test_generated_positive_controls():
    for table in ("00", "01", "10", "11", "0110", "0011", "0100", "10000000"):
        for width in (None, 1, 9, 13):
            source = thue(table, width)
            for row in range(len(table)):
                check_generated(source, table, row)


@pytest.mark.slow
def test_all_small_generated_tables_and_public_widths():
    for n in range(1, 4):
        for value in range(1 << (1 << n)):
            table = f"{value:0{1 << n}b}"
            for width in (None, 1, 7, 8, 9, 10, 13, 40):
                source = (
                    thue(table)
                    if width is None
                    else str(generate("Thue", table, width))
                )
                for row in range(1 << n):
                    check_generated(source, table, row)


@pytest.mark.slow
def test_wider_decoders_and_marker_digit_boundaries():
    for n in (4, 5, 6):
        rng = random.Random(n)
        tables = [f"{rng.getrandbits(1 << n):0{1 << n}b}" for _ in range(3)]
        tables += [
            "0" * (1 << n),
            "1" * (1 << n),
            "".join(str(row.bit_count() & 1) for row in range(1 << n)),
        ]
        for table in tables:
            for width in (None, 1, 13, 40):
                source = thue(table, width)
                for row in range(1 << n):
                    check_generated(source, table, row)
    for n in (8, 11):
        table = "".join(str(row.bit_count() & 1) for row in range(1 << n))
        for width in (1, 13, 40, 80):
            source = thue(table, width)
            for row in (0, 1, (1 << n) // 2, (1 << n) - 1):
                check_generated(source, table, row)


@pytest.mark.medium
def test_finite_all_draw_graphs_and_cycle_escape_controls():
    from esolangs.vm import run_until_halt_or_all_branches_cycle

    states = ("", "a", "b")
    forms = [
        (left, right) for left, right in itertools.product("ab", ("", "a", "b", "~0"))
    ]
    for subset in range(1 << len(forms)):
        rules = [
            f"{left}::={right}"
            for index, (left, right) in enumerate(forms)
            if subset & (1 << index)
        ]
        prefix = "\n".join([*rules, "::=", ""])
        references = [Reference(prefix + state) for state in states]
        edges = [set(reference.successors()) for reference in references]
        for start, state in enumerate(states):
            # Three nodes: I + A + A² contains every simple reachable path.
            expected = any(
                not references[end].matches()
                and (
                    start == end
                    or states[end] in edges[start]
                    or any(
                        states[middle] in edges[start] and states[end] in edges[middle]
                        for middle in range(3)
                    )
                )
                for end in range(3)
            )
            draw = Draw(0)
            machine = _Machine(prefix + state, ScriptedIO(""), draw)
            assert run_until_halt_or_all_branches_cycle(machine, limit=8) == expected
            assert not draw.calls
    for source, pattern in (
        ("a::=:::" + "\n::=\na", "needs input"),
        ("a::=aa\n::=\na", "may be unbounded"),
    ):
        io = ScriptedIO("a\n")
        with pytest.raises(TimeoutError, match=pattern):
            run_until_halt_or_all_branches_cycle(_Machine(source, io), limit=8)
        assert io.reads == 0


@pytest.mark.parametrize("choice", [0, 1])
def test_public_run_uses_the_supplied_output_and_draw(choice):
    from esolangs.interpreters.other.thue import run

    class PublicDraw(Draw):
        def randbelow(self, upper):
            self.calls.append(upper)
            return min(self.choice, upper - 1)

    source = "a::=~Hello\nb::=~ world\n::=\nab"
    reference = Reference(source)
    while reference.matches():
        reference.step(min(choice, len(reference.matches()) - 1))
    io = ScriptedIO("")
    draw = PublicDraw(choice)
    run(source, io, draw)
    assert io.getvalue() == reference.output
    assert draw.calls == [2, 1]


@pytest.mark.medium
def test_fixed_width_marker_positive_control():
    table = "".join(str((row * 17 + row // 3).bit_count() & 1) for row in range(64))
    for width in (1, 13):
        source = thue(table, width)
        for row in (0, 1, 32, 63):
            check_generated(source, table, row)
