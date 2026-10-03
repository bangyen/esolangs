"""Independent 5x5 Home Row model; wiki 189085 and repository dialect decisions."""

import itertools
import random

import pytest

import esolangs
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.home_row import _Machine, run


class Reference:
    def __init__(self, code, grid=(0,) * 25, ptr=0, ip=0):
        self.code = code
        self.loops = [index for index, glyph in enumerate(code) if glyph == "l"]
        if len(self.loops) % 2:
            raise ValueError(f"unmatched 'l' at position {self.loops[-1]}")
        self.rows = [list(grid[start : start + 5]) for start in range(0, 25, 5)]
        self.row, self.column = divmod(ptr, 5)
        self.ip = ip
        self.output = ""

    @property
    def halted(self):
        return self.ip >= len(self.code) or self.code[self.ip] == ";"

    def state(self):
        return (
            self.ip,
            5 * self.row + self.column,
            tuple(value for row in self.rows for value in row),
        )

    def step(self):
        if self.halted:
            return
        glyph = self.code[self.ip]
        value = self.rows[self.row][self.column]
        following = self.ip + 1
        if glyph == "a":
            self.rows[self.row][self.column] += 1
        elif glyph == "s":
            self.rows[self.row][self.column] -= 1
        elif glyph == "d":
            self.row = (self.row + 1) % 5
        elif glyph == "f":
            self.column = (self.column + 1) % 5
        elif glyph == "j" and value == 0:
            # The wiki-linked interpreter skips one raw character, including whitespace.
            following += 1
        elif glyph == "k":
            self.output += chr(value % 256)
            self.rows[self.row][self.column] = 0
        elif glyph == "l":
            order = self.loops.index(self.ip)
            if order % 2 == 0 and value == 0:
                following = self.loops[order + 1] + 1
            elif order % 2 and value != 0:
                following = self.loops[order - 1] + 1
        self.ip = following


def inspect(machine):
    assert machine.ip == machine.ind == machine.state[0]
    assert machine.ptr == machine.state[1]
    assert machine.grid == machine.state[2]
    assert machine.memory == list(machine.grid)
    assert machine.stack == []
    assert machine.io.position() == machine.io.past_end == 0
    assert machine.snapshot() == machine.state
    return machine.state, machine.halted, machine.io.getvalue()


def compare(code, cap, grid=(0,) * 25, ptr=0, ip=0):
    expected = Reference(code, grid, ptr, ip)
    actual = _Machine(code, ScriptedIO("unused\x00\u0101"))
    assert actual.state == (0, 0, (0,) * 25)
    pairs = list(zip(expected.loops[::2], expected.loops[1::2], strict=True))
    assert actual.match == {
        key: value for pair in pairs for key, value in (pair, pair[::-1])
    }
    assert actual.open_l == set(expected.loops[::2])
    assert actual.code == code
    assert actual.size == len(code)
    actual.state = (ip, ptr, tuple(grid))
    assert inspect(actual) == (expected.state(), expected.halted, expected.output)
    states = {expected.state()}
    for _ in range(cap):
        before = actual.snapshot()
        saved_hash = hash(before)
        expected.step()
        actual.step()
        assert inspect(actual) == (
            expected.state(),
            expected.halted,
            expected.output,
        ), (code, ptr, ip, cap)
        assert hash(before) == saved_hash
        if expected.halted:
            terminal = inspect(actual)
            actual.step()
            actual.step()
            assert inspect(actual) == terminal
            return expected, "halt"
        if expected.state() in states:
            return expected, "cycle"
        states.add(expected.state())
    return expected, "bounded"


def multiplication_print(message):
    pieces = []
    for char in message:
        quotient, remainder = divmod(ord(char), 8)
        pieces.append(
            "a" * 8 + "lf" + "a" * quotient + "ffffslf" + "a" * remainder + "kffff"
        )
    return "".join(pieces) + ";"


def corpus():
    for size in range(5):
        for glyphs in itertools.product("asdfjkl;x", repeat=size):
            yield "".join(glyphs)
    yield from (
        "ak;l",
        ";l",
        "ll;l",
        "llall",
        "jllak",
        "j lsl",
        "j\nak;",
        "j\tak;",
        "gak;",
        "\u0101\x00\r\nafk\u2603;",
        "af" * 5 + "k;",
        "ad" * 5 + "k;",
        "a" * 65 + "kk;",
        "a" * 300 + "kk;",
        "s" * 257 + "kk;",
        "alslalslk;",
        "alslak;",
        "alal",
        "slsl",
        "all",
        "alflll",
        multiplication_print("Hello, World!"),
        multiplication_print("\x00\xffA\n"),
    )


@pytest.mark.medium
def test_load_pairs_and_unreachable_unmatched_loops():
    for code in corpus():
        positions = [index for index, glyph in enumerate(code) if glyph == "l"]
        if len(positions) % 2:
            for factory in (_Machine, lambda code, io: run(code, io)):
                with pytest.raises(ValueError, match="unmatched") as caught:
                    factory(code, ScriptedIO())
                assert str(caught.value) == f"unmatched 'l' at position {positions[-1]}"
        else:
            compare(code, 0)


@pytest.mark.medium
@pytest.mark.parametrize("cap", [0, 1, 2, 7, 24])
def test_bounded_torus_commands_and_ordinal_loops(cap):
    for code in corpus():
        if code.count("l") % 2 == 0:
            compare(code, cap)


@pytest.mark.medium
@pytest.mark.parametrize("cap", [0, 1, 2, 7, 24])
def test_every_pointer_with_distinct_neighbors_and_signed_cells(cap):
    for ptr in range(25):
        for value in (-(10**80), -257, -256, -1, 0, 1, 255, 256, 257, 10**80):
            grid = [1000 + index for index in range(25)]
            grid[ptr] = value
            for code in (
                "a",
                "s",
                "d",
                "f",
                "j",
                "k",
                ";",
                "ll",
                "lsl",
                "lfdl",
                "j;k",
                "j lsl",
            ):
                compare(code, cap, grid, ptr)


def test_every_instruction_position_preserves_zero_and_nonzero_skip():
    for code in ("ffjak;", "j;k", "j\nak;", "lal;", "l;lak;", "lslalal", "llll"):
        if code.count("l") % 2:
            continue
        for ip in range(len(code) + 2):
            for ptr in (0, 4, 5, 24):
                for value in (0, 1, -1):
                    grid = [0] * 25
                    grid[ptr] = value
                    compare(code, 7, grid, ptr, ip)


def test_public_runner_matches_independent_halt_certificates():
    programs = (
        "",
        ";ak",
        "ak;ak;",
        "ak",
        "sk;",
        "afak;",
        "af" * 5 + "k;",
        "ad" * 5 + "k;",
        "ada" + "d" * 4 + "k;",
        "jk;",
        "ajk;",
        "jak;",
        "ajak;",
        "ffjak;",
        "aalslk;",
        "lalk;",
        "alslalslk;",
        "alslak;",
        "j\nak;",
        "gak;",
        "a" * 65 + "kk;",
        "a" * 300 + "kk;",
        "s" * 257 + "kk;",
        multiplication_print("Hello, World!"),
        multiplication_print("\x00\xffA\n"),
    )
    for code in programs:
        expected, verdict = compare(code, 10000)
        assert verdict == "halt"
        io = ScriptedIO("unused")
        run(code, io)
        assert (io.getvalue(), io.position(), io.past_end) == (expected.output, 0, 0)
        assert (
            esolangs.run("Home Row", code, "unused", max_steps=10000) == expected.output
        )


def test_exact_cycles_and_signed_growth_have_distinct_certificates():
    from esolangs.vm import run_until_halt_or_cycle

    assert run_until_halt_or_cycle(_Machine("ak;", ScriptedIO()), limit=24)
    for code in ("all", "alfffffl"):
        expected, verdict = compare(code, 24)
        assert verdict == "cycle"
        assert not expected.halted
        assert not run_until_halt_or_cycle(_Machine(code, ScriptedIO()), limit=24)
    for code in ("alal", "slsl"):
        expected, verdict = compare(code, 24)
        assert verdict == "bounded"
        assert abs(expected.rows[0][0]) > 1
        with pytest.raises(TimeoutError, match="undecided"):
            run_until_halt_or_cycle(_Machine(code, ScriptedIO()), limit=24)


def test_snapshots_distinguish_cursor_pointer_and_buried_cells():
    machine = _Machine("adfk;", ScriptedIO())
    states = [(0, 0, (0,) * 25), (1, 0, (0,) * 25), (0, 5, (0,) * 25)]
    states += [(0, 0, (0,) * cell + (1,) + (0,) * (24 - cell)) for cell in range(25)]
    snapshots = []
    for state in states:
        machine.state = state
        snapshots.append(machine.snapshot())
    assert len(set(snapshots)) == len(states)


def generated_result(table, row, n, width=None, template=None):
    if template is None:
        template = esolangs.generate("Home Row", table, width=width)
    code = esolangs.instantiate(
        "Home Row", template, [int(bit) for bit in format(row, f"0{n}b")]
    )
    expected = Reference(code)
    actual = _Machine(code, ScriptedIO("unused"))
    for _ in range(2000 + 40 * (1 << n)):
        if expected.halted:
            break
        expected.step()
        actual.step()
    assert expected.halted, (n, row, width)
    assert inspect(actual) == (expected.state(), True, expected.output)
    assert expected.output == table[row]
    io = ScriptedIO("unused")
    run(code, io)
    assert (io.getvalue(), io.position(), io.past_end) == (table[row], 0, 0)


@pytest.mark.medium
@pytest.mark.parametrize("n", [1, 2, 3])
@pytest.mark.parametrize("width", [None, 1, 4, 9])
def test_every_small_generated_table(n, width):
    for value in range(1 << (1 << n)):
        table = format(value, f"0{1 << n}b")
        template = esolangs.generate("Home Row", table, width=width)
        for row in range(1 << n):
            generated_result(table, row, n, template=template)


@pytest.mark.medium
@pytest.mark.parametrize("n", [4, 5, 6, 9])
@pytest.mark.parametrize("kind", range(5))
@pytest.mark.parametrize("half", [0, 1])
def test_larger_generated_tables(n, kind, half):
    rng = random.Random(1743 + n)
    tables = [
        "0" * (1 << n),
        "1" * (1 << n),
        "".join(str(row.bit_count() % 2) for row in range(1 << n)),
        "".join(rng.choice("01") for _ in range(1 << n)),
        "1" * (1 << (n - 1)) + "0" * (1 << (n - 1)),
    ]
    table = tables[kind]
    template = esolangs.generate("Home Row", table)
    start = half * (1 << (n - 1))
    for row in range(start, start + (1 << (n - 1))):
        generated_result(table, row, n, template=template)


@pytest.mark.medium
@pytest.mark.parametrize("case", range(5))
def test_legacy_dense_five_input_seeded_tables(case):
    rng = random.Random(0)
    tables = ["".join(rng.choice("01") for _ in range(32)) for _ in range(5)]
    template = esolangs.generate("Home Row", tables[case])
    for row in range(32):
        generated_result(tables[case], row, 5, template=template)


@pytest.mark.medium
@pytest.mark.parametrize("case", range(7))
def test_wide_generated_index_boundaries(case):
    n, size = 12, 1 << 12
    table = "".join(str(row.bit_count() % 2) for row in range(size))
    rows = (0, 1, size // 3, size // 2 - 1, size // 2, size - 2, size - 1)
    generated_result(table, rows[case], n)
