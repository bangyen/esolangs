"""Independent regex grammar and mutable machine; Jaune wiki revision 89078."""

import itertools
import random
import re

import pytest

from esolangs.exceptions import HaltError, InputExhaustedError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.jaune import _Machine


def commands(source):
    tokens = re.findall(
        r"[+-]?[0-9]+[:?!$@+-]|[0-9]+|v[:$+?!@-]?|\++|-+|[\s\S]", source
    )
    result = []
    for token in tokens:
        if re.fullmatch(r"[+-]?[0-9]+[:?!$@+-]", token):
            result.append((token[-1], int(token[:-1])))
        elif token in ("v:", "v$") or (token.isascii() and token.isdigit()):
            continue
        elif token.startswith("v"):
            result.append((token, None))
        elif token[0] in "+-":
            result.append((token[0], len(token)))
        elif token in "^><#&%.;":
            result.append((token, None))
        elif token in ":?!$@":
            raise ValueError(f"command {token!r} requires a number")
    return result


class Reference:
    def __init__(self, source, stdin):
        self.commands = commands(source)
        self.stdin = stdin
        self.cells = [0]
        self.ptr = self.hold = self.ip = self.offset = self.reads = self.past_end = 0
        self.calls = []
        self.output = ""

    @property
    def halted(self):
        return self.ip >= len(self.commands)

    def snapshot(self):
        chunks = tuple(
            tuple(self.cells[i : i + 32]) for i in range(0, len(self.cells), 32)
        )
        return (self.ip, chunks, self.ptr, self.hold, tuple(self.calls), self.offset)

    def read(self):
        while self.offset < len(self.stdin) and self.stdin[self.offset].isspace():
            self.offset += 1
        if self.offset == len(self.stdin):
            self.past_end += 1
            raise InputExhaustedError(self.offset, len(self.stdin), "character")
        start = self.offset
        while self.offset < len(self.stdin) and not self.stdin[self.offset].isspace():
            self.offset += 1
        self.reads += 1
        return int(self.stdin[start : self.offset])

    def find(self, kind, number):
        for index, token in enumerate(self.commands):
            if token == (kind, number):
                return index
        name = "label" if kind == ":" else "subroutine"
        verb = "jump" if kind == ":" else "call"
        raise HaltError(f"{verb} to undefined {name} {number}")

    def step(self):
        if self.halted:
            return
        op, arg = self.commands[self.ip]
        following = self.ip + 1
        if op.startswith("v"):
            number = self.read()
            if op == "v":
                self.cells[self.ptr] = number
            elif op in ("v+", "v-"):
                self.cells[self.ptr] += number if op == "v+" else -number
            else:
                target = self.find("$" if op == "v@" else ":", number)
                if op == "v@":
                    self.calls.append(following)
                    following = target
                elif bool(self.cells[self.ptr]) == (op == "v?"):
                    following = target
        elif op == "^":
            self.output += str(self.cells[self.ptr])
        elif op == ">":
            self.ptr += 1
            if self.ptr == len(self.cells):
                self.cells.append(0)
        elif op == "<":
            self.ptr = max(0, self.ptr - 1)
        elif op == "#":
            self.hold = self.cells[self.ptr]
        elif op == "&":
            self.cells[self.ptr] += self.hold
        elif op == "%":
            self.cells[self.ptr] = 0
        elif op in ("+", "-"):
            self.cells[self.ptr] += arg if op == "+" else -arg
        elif op in ("?", "!", "@"):
            target = self.find("$" if op == "@" else ":", arg)
            if op == "@":
                self.calls.append(following)
                following = target
            elif bool(self.cells[self.ptr]) == (op == "?"):
                following = target
        elif op == ";":
            if not self.calls:
                raise HaltError("; with no active subroutine call")
            following = self.calls.pop()
        elif op == ".":
            following = len(self.commands)
        self.ip = following


def inspect(actual):
    snapshot = actual.snapshot()
    assert actual.ip == actual.pos
    assert actual.stack == list(actual.frames)
    assert actual.frame_entry_key(None) == (*snapshot[:4], snapshot[-1])
    return (
        snapshot,
        actual.halted,
        actual.io.getvalue(),
        actual.io.reads,
        actual.io.past_end,
    )


def compare(source, stdin="", cap=30):
    try:
        expected = Reference(source, stdin)
    except ValueError as error:
        message = str(error)
        with pytest.raises(ValueError, match="requires a number") as caught:
            _Machine(source, ScriptedIO(stdin))
        assert str(caught.value) == message
        return None, "syntax"
    actual = _Machine(source, ScriptedIO(stdin))
    assert [(c.op, c.arg) for c in actual.commands] == expected.commands
    seen = set()
    for step in range(cap + 1):
        before = actual.snapshot()
        fingerprint = hash(before)
        assert inspect(actual) == (
            expected.snapshot(),
            expected.halted,
            expected.output,
            expected.reads,
            expected.past_end,
        )
        assert actual.memory == expected.cells
        memory, stack = actual.memory, actual.stack
        memory.append(99)
        stack.append(99)
        assert actual.snapshot() == before
        if expected.halted:
            actual.step()
            actual.step()
            assert actual.snapshot() == before
            return expected, "halt"
        if before in seen:
            return expected, "cycle"
        seen.add(before)
        if step == cap:
            return expected, "bounded"
        try:
            expected.step()
        except (ValueError, EOFError, HaltError) as error:
            message = str(error)
            with pytest.raises(type(error)) as caught:
                actual.step()
            assert str(caught.value) == message
            assert inspect(actual) == (
                expected.snapshot(),
                expected.halted,
                expected.output,
                expected.reads,
                expected.past_end,
            )
            return expected, "error"
        actual.step()
        assert hash(before) == fingerprint
    raise AssertionError("unreachable")


@pytest.mark.parametrize(
    "source", ["\u0661+^.", "\uff12+^.", "\u00b2+^.", "+\u0661+^."]
)
def test_non_ascii_digits_are_comments(source):
    expected, status = compare(source)
    assert status == "halt"
    assert expected.output in ("1", "2")


@pytest.mark.medium
@pytest.mark.parametrize("stdin", ["", "1 -7\n42", "bad", "\u0661\t\n-2"])
@pytest.mark.parametrize("cap", [0, 1, 2, 7, 30])
def test_exhaustive_short_grammar_and_execution(stdin, cap):
    for length in range(4):
        for chars in itertools.product("^v><#&%+-01:?!$@.;x", repeat=length):
            compare("".join(chars), stdin, cap)


@pytest.mark.medium
@pytest.mark.parametrize("seed", range(8))
def test_seeded_signed_operands_labels_and_calls(seed):
    randomizer = random.Random(904 + seed)
    tokens = [
        "^",
        "v",
        ">",
        "<",
        "#",
        "&",
        "%",
        "++",
        "--",
        "0+",
        "-7+",
        "+7-",
        "12",
        "1:",
        "1?",
        "1!",
        "2$",
        "2@",
        "v?",
        "v!",
        "v@",
        "v+",
        "v-",
        "v:",
        "v$",
        ";",
        ".",
        "ignored",
        "\uff12",
    ]
    for _ in range(100):
        compare(
            "".join(randomizer.choice(tokens) for _ in range(15)),
            "1 -7 0 2 42 1",
            cap=80,
        )


@pytest.mark.medium
def test_positive_controls_nested_calls_and_tape_chunk_boundaries():
    for source in ("v+v+^.", "v+>v+#<&^.", "v+>v+1@^.1$#<&;", "v+>v+1:1-<1+>1?<^."):
        expected, status = compare(source, "3 4", cap=200)
        assert status == "halt"
        assert expected.output == "7"
    expected, status = compare("v+1->v+#<1:2!>&<1-1?2:>^.", "3 4", cap=200)
    assert status == "halt"
    assert expected.output == "12"
    for source in (
        "1@^.1$2@;2$7+;",
        "1@.1$1@;",
        "1:1?",
        "1:1!",
        "1:7+1:9+1?",
        ">" * 70 + "-7+#" + "<" * 38 + "&^.",
    ):
        compare(source, cap=200)


def generated_row(program, row, n, answer):
    stdin = "\n".join(format(row, f"0{n}b"))
    expected, status = compare(program, stdin, cap=10_000)
    assert status == "halt"
    assert expected.output == answer
    assert expected.reads == n
    assert expected.offset == len(stdin)


@pytest.mark.medium
@pytest.mark.parametrize("n", [1, 2, 3])
@pytest.mark.parametrize("width", [None, 1, 7, 80])
def test_generated_all_small_tables(n, width):
    from esolangs import generate

    for value in range(1 << (1 << n)):
        table = format(value, f"0{1 << n}b")
        program = generate("Jaune", table, width)
        for row, answer in enumerate(table):
            generated_row(program, row, n, answer)


@pytest.mark.medium
@pytest.mark.parametrize("batch", range(10))
def test_generated_five_input_sample(batch):
    from esolangs import generate
    from tests.tools.sample_tables import five_input_sample

    for table in five_input_sample()[batch * 20 : (batch + 1) * 20]:
        program = generate("Jaune", table)
        for row, answer in enumerate(table):
            generated_row(program, row, 5, answer)


@pytest.mark.medium
@pytest.mark.parametrize("n", [6, 8, 10, 12])
def test_generated_parity_and_seeded_larger_tables(n):
    from esolangs import generate

    randomizer = random.Random(n)
    tables = ["".join(str(row.bit_count() & 1) for row in range(1 << n))]
    if n == 8:
        tables.extend(format(randomizer.getrandbits(256), "0256b") for _ in range(3))
    else:
        tables.append(format(randomizer.getrandbits(1 << n), f"0{1 << n}b"))
    for table in tables:
        program = generate("Jaune", table)
        rows = range(len(table)) if n <= 8 else (0, 1, len(table) // 2, len(table) - 1)
        for row in rows:
            generated_row(program, row, n, table[row])


@pytest.mark.medium
def test_generated_plain_and_spatial_lookup_controls():
    from esolangs.tools.jaune import _jaune_ordered
    from tests.tools.plain_oracles import _jaune_linear

    for table in ("00", "11"):
        program = _jaune_ordered(table, (0,))
        for row in range(2):
            generated_row(program, row, 1, table[row])
    table = "".join(str(row.bit_count() & 1) for row in range(64))
    program = _jaune_linear(table)
    for row in (0, 1, 2, 7, 31, 32, 62, 63):
        generated_row(program, row, 6, table[row])
