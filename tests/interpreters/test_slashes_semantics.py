"""Independent regex literal rewriting; esolangs.org/wiki////, revision 166743."""

import itertools
import random
import re

import pytest

import esolangs
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.slashes import _Machine, run

_RULE = re.compile(r"/((?:\\[\s\S]|[^/\\])*)/((?:\\[\s\S]|[^/\\])*)/")
_ESCAPE = re.compile(r"\\([\s\S])")


class Reference:
    def __init__(self, source):
        self.body = source
        self.pattern = None
        self.replacement = ""
        self.matcher = None
        self.output = ""

    @property
    def halted(self):
        return self.body == "" and self.pattern is None

    def state(self):
        return self.body, self.pattern, self.replacement

    def step(self):
        if self.pattern is not None:
            if self.pattern == "":
                return
            if self.matcher.search(self.body) is None:
                self.pattern = None
                self.replacement = ""
                self.matcher = None
            else:
                self.body = self.matcher.sub(
                    lambda _match: self.replacement, self.body, count=1
                )
            return
        if self.halted:
            return
        if self.body.startswith("/"):
            fields = _RULE.match(self.body)
            if fields is None:
                self.body = ""
                return
            self.pattern, self.replacement = (
                _ESCAPE.sub(lambda match: match[1], field) for field in fields.groups()
            )
            self.body = self.body[fields.end() :]
            self.matcher = re.compile(re.escape(self.pattern))
        else:
            count = 2 if self.body.startswith("\\") else 1
            self.output += self.body[count - 1 : count]
            self.body = self.body[count:]


def inspect(machine):
    assert machine.ip is None
    assert machine.ip_shape == "opaque"
    assert machine.stack == []
    assert machine.memory == [ord(char) for char in machine.state[0]]
    assert machine.io.position() == machine.io.past_end == 0
    return machine.state, machine.halted, machine.io.getvalue()


def compare(code, cap):
    expected = Reference(code)
    actual = _Machine(code, ScriptedIO("unused\x00\u0101"))
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
        ), code
        assert actual.snapshot() == (*expected.state(), 0)
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
    assert inspect(actual) == (expected.state(), expected.halted, expected.output)
    return expected, "bounded"


def quote(text):
    return "".join("\\" + char if char in "/\\" else char for char in text)


def corpus():
    for size in range(7):
        for chars in itertools.product("a/\\\n\x00", repeat=size):
            yield "".join(chars)
    fields = (
        "",
        "a",
        "b",
        "aa",
        "ab",
        "/",
        "\\",
        ".*",
        "$",
        "[a]",
        "\n",
        "\x00",
        "\u0101",
    )
    tails = ("", "a", "aa", "ababa", "/a/b/a", "\\a", "\n\x00\u0101.*$[a]")
    for pattern, replacement, tail in itertools.product(fields, fields, tails):
        rule = "/" + quote(pattern) + "/" + quote(replacement) + "/"
        yield rule + tail
        yield rule[:-1]
    yield "/foo/Hello, world!//bar/foo/bar"
    yield "/ab/bbaa/abb"
    yield "/a/\\//ab/world!/ab world!/Hello, aworld! bworld!"
    yield "/a/a/a"
    yield "/a/aa/a"


@pytest.mark.medium
@pytest.mark.parametrize("cap", [0, 1, 2, 7, 24])
def test_bounded_literal_rules_and_output(cap):
    for code in corpus():
        compare(code, cap)


def test_known_halting_programs_reach_public_runner():
    examples = (
        ("", ""),
        ("\\", ""),
        ("/a", ""),
        ("/a/", ""),
        ("/a/\\", ""),
        (r"a\/b\\", "a/b\\"),
        (r"/a\/b/c/a/b", "c"),
        ("/a/b/aaa", "bbb"),
        ("/foo/Hello, world!//bar/foo/bar", "Hello, world!"),
        (r"/a/\//ab/world!/ab world!/Hello, aworld! bworld!", "Hello, world!"),
        ("/a/$/a", "$"),
        ("$", "$"),
        ("/./X/.*.", "X*X"),
        (r"/a/\\1/a", "1"),
        ("/\n/\u0101/\n", "\u0101"),
    )
    for source, answer in examples:
        expected, verdict = compare(source, 100)
        assert verdict == "halt"
        assert expected.output == answer
        io = ScriptedIO("unused")
        run(source, io)
        assert (io.getvalue(), io.position(), io.past_end) == (answer, 0, 0)
        assert esolangs.run("Slashalash", source, "unused", max_steps=100) == answer


def test_exact_cycles_and_growth_have_distinct_certificates():
    from esolangs.vm import run_until_halt_or_cycle

    for source in ("///", "//x/", "/a/a/a"):
        expected, verdict = compare(source, 20)
        assert verdict == "cycle"
        assert not expected.halted
        assert not run_until_halt_or_cycle(_Machine(source, ScriptedIO()), limit=20)
    for source in ("/a/aa/a", "/ab/bbaa/abb"):
        expected, verdict = compare(source, 20)
        assert verdict == "bounded"
        assert not expected.halted
        assert len(expected.body) > len(source)
        with pytest.raises(TimeoutError, match="undecided"):
            run_until_halt_or_cycle(_Machine(source, ScriptedIO()), limit=20)


def test_snapshot_distinguishes_active_rule_and_substitution_data():
    snapshots = []
    for source in ("/a/b/a", "/b/b/a", "/a/c/a", "/a/b/b"):
        machine = _Machine(source, ScriptedIO())
        machine.step()
        snapshots.append(machine.snapshot())
    assert len(set(snapshots)) == 4


def generated_result(table, row, n, width=None, cap=40000):
    template = esolangs.generate("///", table, width=width)
    bits = [int(bit) for bit in format(row, f"0{n}b")]
    code = esolangs.instantiate("///", template, bits)
    expected = Reference(code)
    actual = _Machine(code, ScriptedIO("unused"))
    for _ in range(cap):
        if expected.halted:
            break
        expected.step()
        actual.step()
        assert actual.state == expected.state()
        assert actual.halted == expected.halted
        assert actual.io.getvalue() == expected.output
    assert expected.halted, (n, row, width)
    assert inspect(actual) == (expected.state(), True, expected.output)
    assert expected.output == table[row]
    assert esolangs.run("///", code, "unused", timeout=3) == table[row]
    return len(template)


@pytest.mark.medium
@pytest.mark.parametrize("n", [1, 2, 3])
def test_every_small_generated_table(n):
    for value in range(1 << (1 << n)):
        table = format(value, f"0{1 << n}b")
        for row in range(1 << n):
            generated_result(table, row, n)


@pytest.mark.medium
@pytest.mark.parametrize("n", [4, 5, 6])
@pytest.mark.parametrize("case", range(11))
def test_larger_seeded_generated_tables(n, case):
    rng = random.Random(1729 + n)
    tables = [
        "0" * (1 << n),
        "1" * (1 << n),
        "".join(str(row.bit_count() % 2) for row in range(1 << n)),
        *("".join(str(rng.randrange(2)) for _ in range(1 << n)) for _ in range(8)),
    ]
    for row in range(1 << n):
        generated_result(tables[case], row, n)


@pytest.mark.medium
def test_executed_rendered_scaling():
    sizes = []
    for n in (8, 10, 12):
        rng = random.Random(1729)
        table = "".join(str(rng.randrange(2)) for _ in range(1 << n))
        sizes.append(generated_result(table, (1 << n) // 3, n))
    assert (sizes[2] - sizes[1]) / (sizes[1] - sizes[0]) <= 4.4
