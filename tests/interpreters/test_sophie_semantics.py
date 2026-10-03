"""Independent Sophie scanner and accumulator model; wiki 96564 and author spec."""

import itertools
import random
import unicodedata

import pytest

import esolangs
from esolangs.exceptions import HaltError, InputExhaustedError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.register_based.sophie import _Machine, find, matches, run


def number(text):
    if not text or not all(char.isdecimal() for char in text):
        raise ValueError(f"invalid literal for int() with base 10: {text!r}")
    value = 0
    for char in text:
        value = 10 * value + unicodedata.decimal(char)
    return value


def decimal(value):
    negative = value < 0
    value = abs(value)
    digits = []
    while value:
        value, digit = divmod(value, 10)
        digits.append(chr(48 + digit))
    return ("-" if negative else "") + ("".join(reversed(digits)) or "0")


def literal(code, index, *, conditional=False):
    start = index + 1
    if start == len(code):
        return None
    if code[start] == "$":
        stop = start + 1
        while stop < len(code) and code[stop].isdecimal():
            stop += 1
        if stop > start + 1 and (not conditional or code[stop : stop + 1] == "{"):
            return number(code[start + 1 : stop]), stop + int(conditional)
        if start + 1 < len(code) and code[start + 1] != "\n":
            start += 1
    candidates = [start]
    original = index + 1
    if conditional and code[original] == "$" and start != original:
        candidates.append(original)
    for candidate in candidates:
        if code[candidate] == "\n":
            continue
        stop = candidate + 1
        if conditional:
            if code[stop : stop + 1] != "{":
                continue
            stop += 1
        return ord(code[candidate]), stop
    return None


def structure(code):
    brackets = []
    index = 0
    while index < len(code):
        glyph = code[index]
        token = (
            literal(code, index, conditional=glyph == "@") if glyph in "#@" else None
        )
        if token is not None:
            _value, following = token
            if glyph == "@":
                brackets.append((following - 1, "{"))
            index = following
            continue
        if glyph in "[]{}":
            brackets.append((index, glyph))
        index += 1
    for opener, closer in (("[", "]"), ("{", "}")):
        depth = 0
        for index, glyph in brackets:
            if glyph == opener:
                depth += 1
            elif glyph == closer:
                if depth == 0:
                    raise ValueError(f"unmatched '{closer}' at position {index}")
                depth -= 1
        if depth:
            raise ValueError(f"unmatched '{opener}'")
    return brackets


class Reference:
    def __init__(self, code, stdin="", acc=0):
        self.brackets = structure(code)
        self.code, self.stdin = code, stdin
        self.acc, self.ip, self.cursor = acc, 0, 0
        self.stack = []
        self.stopped = False
        self.output = ""
        self.past_end = 0

    @property
    def halted(self):
        return self.stopped or self.ip >= len(self.code)

    def state(self):
        return self.ip, self.acc, False, tuple(self.stack), self.stopped, self.cursor

    def closing(self, index):
        opener = self.code[index]
        closer = "]" if opener == "[" else "}"
        depth = 1
        for position, glyph in self.brackets:
            if position <= index:
                continue
            depth += (glyph == opener) - (glyph == closer)
            if depth == 0:
                return position
        return len(self.code)

    def read(self, *, token=False):
        if token:
            while self.cursor < len(self.stdin) and self.stdin[self.cursor].isspace():
                self.cursor += 1
        if self.cursor == len(self.stdin):
            self.past_end += 1
            raise InputExhaustedError(self.cursor, len(self.stdin), "character")
        start = self.cursor
        if token:
            while (
                self.cursor < len(self.stdin) and not self.stdin[self.cursor].isspace()
            ):
                self.cursor += 1
            return self.stdin[start : self.cursor]
        self.cursor += 1
        return ord(self.stdin[start])

    def step(self):
        if self.halted:
            return
        glyph = self.code[self.ip]
        following = self.ip + 1
        if glyph == "[":
            self.stack.append(self.ip)
        elif glyph in "]*":
            if not self.stack:
                raise HaltError(
                    f"{glyph!r} at position {self.ip} closes a loop that never opened"
                )
            opener = self.stack.pop()
            following = opener if glyph == "]" else self.closing(opener) + 1
        elif glyph == ".":
            self.output += decimal(self.acc)
        elif glyph == ",":
            self.output += chr(self.acc)
        elif glyph == ":":
            value = self.read(token=True)
            if value.isdigit():
                self.acc = number(value)
        elif glyph == ";":
            self.acc = self.read()
        elif glyph == "{":
            following = self.closing(self.ip) + 1
        elif glyph == "&":
            self.stopped = True
            return
        elif glyph in "#@":
            token = literal(self.code, self.ip, conditional=glyph == "@")
            if token is not None:
                value, following = token
                if glyph == "#":
                    self.acc = value
                elif value != self.acc:
                    end = self.closing(following - 1)
                    following = end + (2 if self.code[end + 1 : end + 2] == "{" else 1)
        self.ip = following


def inspect(actual):
    assert actual.ip == actual.ind
    assert actual.memory == [actual.acc]
    assert actual.stack == list(actual.stk)
    assert actual.skp is False
    assert actual.snapshot() == (
        actual.ind,
        actual.acc,
        False,
        actual.stk,
        actual._halted_by_command,  # noqa: SLF001
        actual.io.position(),
    )
    return actual.snapshot(), actual.halted, actual.io.getvalue(), actual.io.past_end


def compare(code, stdin="", cap=24, acc=0):
    expected = Reference(code, stdin, acc)
    actual = _Machine(code, ScriptedIO(stdin))
    assert (actual.acc, actual.ind, actual.skp, actual.stk) == (0, 0, False, ())
    actual.acc = acc
    assert inspect(actual) == (expected.state(), expected.halted, "", 0)
    states = {expected.state()}
    for _ in range(cap):
        before = actual.snapshot()
        old_hash = hash(before)
        error = None
        try:
            expected.step()
        except (HaltError, EOFError, ValueError) as exc:
            error = exc
        if error is not None:
            with pytest.raises(type(error), match=r".") as caught:
                actual.step()
            assert str(caught.value) == str(error)
        else:
            actual.step()
        assert inspect(actual) == (
            expected.state(),
            expected.halted,
            expected.output,
            expected.past_end,
        ), (code, stdin, cap)
        assert hash(before) == old_hash
        if error is not None:
            return expected, type(error).__name__
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


def corpus():
    for length in range(4):
        for glyphs in itertools.product("#@$0[]{}*:;,.&x \n", repeat=length):
            yield "".join(glyphs)
    atoms = (
        "#A",
        "#$0",
        "#$65",
        ";",
        ":",
        ",",
        ".",
        "&",
        "x",
        "{#B,}",
        "@A{#B,}",
        "@A{#B,}{#C,}",
        "[*]",
        "[]",
    )
    for length in range(3):
        for parts in itertools.product(atoms, repeat=length):
            yield "".join(parts)
    yield from (
        "{#}#B,}#A,&",
        "[#]*]#A,&",
        "[#A[,*][#B,*]*]#C,&",
        "[#A[,*]#B,]",
        "#A@A{#},#C,}{#B,}&",
        "#}@}{#A,}{#B,}&",
        "##@#{#A,}{#B,}&",
        "#[@[{#A,}{#B,}&",
        "#$#@[{@${#A,}{#B,}&",
        "#$².@$²{#A,}{#B,}&",
        "#$١٢.@$١٢{#A,}{#B,}&",
        "@\n{#A,}",
        "#\n#A,",
        "#$\n.",
        "@$$ {#A,}",
        "#A@B{,#C,}",
        "#A@A{@$65{,#B,}}{#C,}&",
        "#H,#e,#l,,#o,#,,# ,#W,#o,#r,#l,#d,#!,&",
        ";@1{[,]}{,&}",
        "[;@$0{&}{,}]",
        ":@$0{:@$0{#0,}{#1,}}{:@$0{#1,}{#0,}}&",
        "#$42:.&",
        ":;,&",
        "#$42;.&",
        "#$#[]",
        "#$1[",
        "&]",
        "[[]]",
        "[;*];",
        "[#A[#B[#C[.*]]]*]",
        "{[;]}#A,",
    )


@pytest.mark.medium
def test_literal_aware_validation_and_public_find():
    for code in corpus():
        message = None
        try:
            brackets = structure(code)
        except ValueError as error:
            message = str(error)
        if message is not None:
            with pytest.raises(ValueError, match="unmatched") as caught:
                matches(code)
            assert str(caught.value) == message
            with pytest.raises(ValueError, match="unmatched"):
                _Machine(code, ScriptedIO())
        else:
            matches(code)
            expected = Reference(code)
            actual = _Machine(code, ScriptedIO())
            for index, glyph in brackets:
                if glyph in "[{":
                    assert find(code, index) == expected.closing(index)
                    assert actual._partners[index] == expected.closing(index)  # noqa: SLF001
    assert find("{unmatched", 0) == len("{unmatched")


@pytest.mark.medium
@pytest.mark.parametrize("cap", [0, 1, 2, 7, 24])
@pytest.mark.parametrize("stdin", ["", "A 0\x00"])
def test_bounded_commands_nested_breaks_and_literal_blocks(cap, stdin):
    for code in corpus():
        try:
            structure(code)
        except ValueError:
            continue
        compare(code, stdin, cap)


@pytest.mark.medium
@pytest.mark.parametrize("cap", [0, 1, 2, 7, 24])
def test_accumulator_and_input_boundaries(cap):
    programs = (
        ".",
        ",",
        ":",
        ";",
        "#.;&",
        "@$0{#A,}{#B,}",
        "@A{#B,}",
        "[;@$0{*}{,}]",
        ":;,:.",
        "[;*][;*].",
    )
    feeds = (
        "",
        "\n",
        " ",
        "A",
        "AA\x00",
        "0",
        "00 1",
        "65 B",
        "-1\n",
        "not_a_number\n",
        "\u0101\n",
        "١٢\n",
        "²\n",
        "123\u20030",
        "\x00tail",
    )
    for acc in (-1, 0, 10, 48, 49, 65, 255, 256, 0x110000, 10**80):
        for code in programs:
            for stdin in feeds:
                compare(code, stdin, cap, acc)


def test_every_byte_literal_and_optional_dollar_marker():
    for value in range(256):
        char = chr(value)
        forms = ("$$", "$$") if char == "$" else (char, "$" + char)
        for text in forms:
            code = "#" + text + "@" + text + "{#A,}{#B,}&"
            expected, verdict = compare(code, cap=24)
            assert verdict == "halt"
            assert expected.output == ("" if char == "\n" else "A")
    for code in ("#$36@${#A,}{#B,}&", "#$37@${#A,}{#B,}&"):
        expected, verdict = compare(code, cap=24)
        assert verdict == "halt"
        assert expected.output == ("A" if code.startswith("#$36") else "B")


def test_large_decimal_load_guard_input_and_output():
    digits = "9" * 6000
    value = number(digits)
    for code, stdin, output in (
        ("#$" + digits + ".&", "", digits),
        ("#$" + digits + "@$" + digits + "{#A,}{#B,}&", "", "A"),
        (":.&", digits, digits),
    ):
        expected, verdict = compare(code, stdin, cap=8)
        assert verdict == "halt"
        assert expected.output == output
        assert expected.acc in (value, ord("A"))
        io = ScriptedIO(stdin)
        run(code, io)
        assert io.getvalue() == output


def test_input_cursor_and_loop_state_prevent_false_cycles():
    from esolangs.vm import run_until_halt_or_cycle

    machine = _Machine("[;@$0{&}{,}]", ScriptedIO("AAB\x00"))
    assert run_until_halt_or_cycle(machine, limit=60)
    assert machine.io.getvalue() == "AAB"
    assert machine.io.position() == 4
    for code in ("[]", "[#A[,*]#B,]"):
        _expected, verdict = compare(code, cap=24)
        assert verdict == "cycle"
        assert run_until_halt_or_cycle(_Machine(code, ScriptedIO()), limit=60) is False
    machine = _Machine("&", ScriptedIO("x"))
    snapshots = {machine.snapshot()}
    for acc, ip, stack, halted in (
        (1, 0, (), False),
        (0, 1, (), False),
        (0, 0, (1,), False),
        (0, 0, (1, 2), False),
        (0, 0, (), True),
    ):
        machine.acc, machine.ind, machine.stk = acc, ip, stack
        machine._halted_by_command = halted  # noqa: SLF001
        snapshots.add(machine.snapshot())
    machine.io.input_char()
    snapshots.add(machine.snapshot())
    assert len(snapshots) == 7


def test_public_examples_and_nearest_loop_break():
    xor = ":@$0{:@$0{#0,}{#1,}}{:@$0{#1,}{#0,}}&"
    cases = [
        ("#H,#e,#l,,#o,#,,# ,#W,#o,#r,#l,#d,#!,&", "", "Hello, World!"),
        (";@1{[,]}{,&}", "0", "0"),
        ("[;@$0{&}{,}]", "AAB\x00", "AAB"),
        ("{#}#B,}#A,&", "", "A"),
        ("[#]*]#A,&", "", "A"),
        ("[#A[,*][#B,*]*]#C,&", "", "ABC"),
        ("##@#{#A,}{#B,}&", "", "A"),
        ("#}@}{#A,}{#B,}&", "", "A"),
    ]
    cases += [(xor, f"{a} {b}", str(a ^ b)) for a in (0, 1) for b in (0, 1)]
    for code, stdin, output in cases:
        expected, verdict = compare(code, stdin, 2000)
        assert verdict == "halt"
        assert expected.output == output
        io = ScriptedIO(stdin)
        run(code, io)
        assert io.getvalue() == output
        assert esolangs.run("Sophie", code, stdin, max_steps=2000) == output


def generated_result(table, row, n, program):
    stdin = format(row, f"0{n}b") + "!"
    expected = Reference(program, stdin)
    actual = _Machine(program, ScriptedIO(stdin))
    for _ in range(2000 + 20 * len(program)):
        if expected.halted:
            break
        expected.step()
        actual.step()
    assert expected.halted
    assert expected.output == table[row]
    assert expected.cursor == n
    assert inspect(actual) == (expected.state(), True, table[row], 0)
    io = ScriptedIO(stdin)
    run(program, io)
    assert io.getvalue() == table[row]
    assert io.position() == n
    assert io.input_char() == ord("!")


@pytest.mark.medium
@pytest.mark.parametrize("n", [1, 2, 3])
@pytest.mark.parametrize("width", [None, 1, 4, 9])
def test_every_small_generated_table(n, width):
    for value in range(1 << (1 << n)):
        table = format(value, f"0{1 << n}b")
        program = esolangs.generate("Sophie", table, width=width)
        for row in range(1 << n):
            generated_result(table, row, n, program)


@pytest.mark.medium
@pytest.mark.parametrize("n", [4, 5, 6, 7, 8])
@pytest.mark.parametrize("kind", range(6))
def test_larger_generated_tables(n, kind):
    rng = random.Random(1743 + n)
    tables = [
        "0" * (1 << n),
        "1" * (1 << n),
        "".join(str(row.bit_count() % 2) for row in range(1 << n)),
        "".join(rng.choice("01") for _ in range(1 << n)),
        "".join(str(int(row.bit_count() == 1)) for row in range(1 << n)),
    ]
    tables.append("1" * ((1 << n) - 1) + "0")
    table = tables[kind]
    program = esolangs.generate("Sophie", table)
    for row in range(1 << n):
        generated_result(table, row, n, program)


@pytest.mark.medium
@pytest.mark.parametrize("n", [8, 10, 12])
def test_legacy_shared_residual_seeded_tables(n):
    rng = random.Random(929 + n)
    table = "".join(rng.choice("01") for _ in range(1 << n))
    program = esolangs.generate("Sophie", table)
    for row in (0, (1 << n) - 1, *[rng.randrange(1 << n) for _ in range(6)]):
        generated_result(table, row, n, program)


def test_named_label_collision_and_numeric_fallback():
    table = "00000000000000010000000100000100"
    program = esolangs.generate("Sophie", table)
    for row in range(32):
        generated_result(table, row, 5, program)
    rng = random.Random(5)
    weights = [rng.choice("01") for _ in range(19)]
    table = "".join(weights[row.bit_count()] for row in range(1 << 18))
    program = esolangs.generate("Sophie", table)
    assert "@$1{" in program
    for row in rng.sample(range(1 << 18), 40):
        generated_result(table, row, 18, program)
