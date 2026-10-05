"""Independent array machine; esolangs.org/wiki/SLOW_ACV_MAMMALIAN, revision 197094.

The wiki leaves several points open; the model follows the conventions the
interpreter's own suite already pins, each named where it is used:

* moduli: the wiki says cells hold 0-255 and EXCRETE/PRONOUNCE take x
  "modulo 255".  The interpreter defaults both to 256 and offers 255 as an
  option, so the model takes ``cell`` and ``io`` moduli and is compared at all
  four combinations.
* "top" of an array is its end (EXCRETE and ACCEPT append).
* SPRINT indexes from 0 and is a NOP unless ``x < len``.
* LEAPFROG with target ``k = x - first`` lands on 0-based index ``k`` and
  halts when ``k <= 0`` (the wiki says nothing about a non-positive target).
* CONFLAGRATE skips a pair whose divisor would be zero (the wiki divides by
  it unconditionally).
* reading past the end of stdin is the shared IO's InputExhaustedError.
"""

import itertools
import random

import pytest

import esolangs
from esolangs.exceptions import InputExhaustedError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine, run
from tests.interpreters.views import view as vm_view

COMMANDS = (
    "SEED",
    "EXCRETE",
    "CONSUME",
    "FISSION",
    "SPRINT",
    "LEAPFROG",
    "DIGEST",
    "CONFLAGRATE",
    "ACCEPT",
    "PRONOUNCE",
)


class Reference:
    def __init__(self, code, stdin, cell=256, io=256):
        self.words = code.split()
        if not set(self.words) <= set(COMMANDS):
            raise ValueError(code)
        self.stdin = stdin
        self.cell = cell
        self.io = io
        self.arrays = [[0] for _ in range(23)]
        self.ip = self.pointer = self.x = self.read = 0
        self.stopped = False
        self.output = ""

    @property
    def halted(self):
        return self.stopped or self.ip >= len(self.words)

    def state(self):
        return (
            self.ip,
            tuple(map(tuple, self.arrays)),
            self.pointer,
            self.x,
            self.read,
            self.stopped,
        )

    def step(self):
        if self.halted:
            return
        word = self.words[self.ip]
        here = self.arrays[self.pointer]
        self.ip += 1
        if word == "SEED":
            for index, array in enumerate(self.arrays):
                if array:
                    array[0] = (array[0] + index + 1) % self.cell
        elif word == "EXCRETE":
            here.append(self.x % self.io)
            self.x = 0
        elif word == "CONSUME":
            if here:
                self.x = here.pop((len(here) - 1) // 2)
        elif word == "FISSION":
            if here:
                half = here.pop((len(here) - 1) // 2) // 2
                here.insert(0, half)
                here.append(half)
        elif word == "SPRINT":
            if self.x < len(here):
                self.pointer = (self.pointer + here[self.x]) % 23
        elif word == "LEAPFROG":
            if here and here[-1] != 0:
                target = self.x - here[0]
                if target <= 0:
                    self.ip -= 1
                    self.stopped = True
                else:
                    self.ip = target
        elif word == "DIGEST":
            self.x ^= sum(here)
        elif word == "CONFLAGRATE":
            self.conflagrate()
        elif word == "ACCEPT":
            if self.read >= len(self.stdin):
                raise InputExhaustedError(self.read + 1, len(self.stdin), "character")
            value = ord(self.stdin[self.read]) ^ self.x
            self.read += 1
            self.arrays[0].append(value % self.cell)
        elif word == "PRONOUNCE":
            self.output += chr(self.x % self.io)

    def conflagrate(self):
        places = [
            (a, c) for a, array in enumerate(self.arrays) for c in range(len(array))
        ]
        values = [self.arrays[a][c] for a, c in places]
        n = len(values)
        for i in range(n // 2):
            j = n - 1 - i
            low, high = values[i], values[j]
            if high and low > high:
                moved = low // high
                values[i], values[j] = low - moved, (high + moved) % self.cell
            elif low and low < high:
                moved = high % low
                values[i], values[j] = (low + moved) % self.cell, high - moved
        for (a, c), value in zip(places, values, strict=True):
            self.arrays[a][c] = value


def observe(machine):
    snapshot = machine.snapshot()
    assert vm_view(machine, "ip") == snapshot[0]
    assert vm_view(machine, "memory") == list(snapshot[1][snapshot[2]])
    assert vm_view(machine, "stack") == [
        value for array in snapshot[1] for value in array
    ]
    assert machine.io.position() == snapshot[4]
    return snapshot, machine.halted, machine.io.getvalue()


def expect(reference):
    return reference.state(), reference.halted, reference.output


def compare(code, stdin, cap, cell=256, io=256):
    """Step both engines together, comparing complete state after every step."""
    expected = Reference(code, stdin, cell, io)
    actual = _Machine(code, ScriptedIO(stdin), cell_modulus=cell, io_modulus=io)
    assert observe(actual) == expect(expected), code
    for _ in range(cap):
        if expected.halted:
            terminal = observe(actual)
            actual.step()
            actual.step()
            assert observe(actual) == terminal, code
            break
        try:
            expected.step()
        except InputExhaustedError:
            with pytest.raises(InputExhaustedError):
                actual.step()
            return expected
        actual.step()
        assert observe(actual) == expect(expected), (code, stdin)
    return expected


STDIN = "\x05\xff\x01AŁ\x00\x02\x80"


def corpus():
    for length in range(5):
        for words in itertools.product(COMMANDS, repeat=length):
            yield " ".join(words)
    rng = random.Random(197094)
    for _ in range(1500):
        yield " ".join(rng.choice(COMMANDS) for _ in range(rng.randrange(4, 14)))
    yield from WITNESSES


WITNESSES = (
    "SEED SPRINT SPRINT SPRINT " + "SEED " * 8 + "DIGEST PRONOUNCE",
    "SEED " * 256 + "DIGEST PRONOUNCE",
    "ACCEPT ACCEPT CONSUME CONSUME PRONOUNCE CONSUME PRONOUNCE",
    "ACCEPT ACCEPT ACCEPT FISSION FISSION CONSUME PRONOUNCE",
    "CONSUME CONSUME FISSION SPRINT DIGEST LEAPFROG EXCRETE",
    "ACCEPT ACCEPT DIGEST EXCRETE EXCRETE CONFLAGRATE CONFLAGRATE",
    "SEED ACCEPT ACCEPT ACCEPT CONFLAGRATE DIGEST PRONOUNCE",
    "ACCEPT LEAPFROG PRONOUNCE",
    "SEED ACCEPT LEAPFROG SEED",
    "ACCEPT ACCEPT CONSUME LEAPFROG SEED SEED SEED",
    "ACCEPT ACCEPT ACCEPT ACCEPT DIGEST LEAPFROG SEED",
    "ACCEPT ACCEPT ACCEPT ACCEPT DIGEST DIGEST SPRINT SPRINT EXCRETE",
    "SEED\tSEED\nCONSUME\r\nPRONOUNCE\x0bDIGEST\x0cPRONOUNCE\xa0EXCRETE",
    "",
    "   \n",
)


@pytest.mark.medium
@pytest.mark.parametrize(
    ("cell", "io"), [(256, 256), (255, 255), (255, 256), (256, 255)]
)
def test_every_step_matches_independent_engine(cell, io):
    for code in corpus():
        compare(code, STDIN, 60, cell, io)


@pytest.mark.parametrize("stdin", ["", "\x01", "\xff\xff\xff", "ĀA"])
def test_input_boundaries_match(stdin):
    for code in WITNESSES:
        compare(code, stdin, 400)
    for count in range(1, 5):
        compare(" ".join(["ACCEPT"] * count + ["DIGEST", "PRONOUNCE"]), stdin, 10)


@pytest.mark.parametrize(
    ("cell", "io"), [(256, 256), (255, 255), (255, 256), (256, 255)]
)
def test_run_matches_independent_engine(cell, io):
    # The extra case wraps CONFLAGRATE's increased cell: 58 SEEDs make
    # array 21's head 22 * 58 % 255 == 1, paired against an accepted 254,
    # and the suffix walks the pointer there so DIGEST reads 0 (not 255).
    wrap = "SEED " * 58 + (
        "ACCEPT CONFLAGRATE FISSION CONSUME FISSION SPRINT FISSION SPRINT "
        "DIGEST PRONOUNCE"
    )
    cases = [(code, STDIN) for code in itertools.islice(corpus(), 0, None, 7)]
    for code, stdin in [*cases, (wrap, "\xfe")]:
        expected = Reference(code, stdin, cell, io)
        try:
            for _ in range(100):
                expected.step()
        except InputExhaustedError:
            continue
        if not expected.halted:
            continue
        scripted = ScriptedIO(stdin)
        run(code, scripted, cell_modulus=cell, io_modulus=io)
        actual = (scripted.getvalue(), scripted.position())
        assert actual == (expected.output, expected.read), code


@pytest.mark.parametrize(
    ("code", "stdin", "output"),
    [
        # The wiki's own example: prints "H" without a trailing newline.
        ("SEED SPRINT SPRINT SPRINT " + "SEED " * 8 + "DIGEST PRONOUNCE", "", "H"),
        ("PRONOUNCE", "", "\x00"),
        ("SEED SEED SEED CONSUME PRONOUNCE", "", "\x03"),
        ("ACCEPT CONSUME CONSUME PRONOUNCE", "A", "A"),
        ("ACCEPT ACCEPT CONSUME PRONOUNCE", "AB", "A"),
        ("ACCEPT CONSUME FISSION CONSUME PRONOUNCE", "@", " "),
        ("SEED ACCEPT DIGEST PRONOUNCE", "\xff", "\x00"),
        ("SEED ACCEPT LEAPFROG PRONOUNCE", "\x05", ""),
        ("", "", ""),
    ],
)
def test_reference_positive_controls(code, stdin, output):
    expected = compare(code, stdin, 400)
    assert expected.halted
    assert expected.output == output
    io = ScriptedIO(stdin)
    run(code, io)
    assert io.getvalue() == output


def test_conflagrate_wraps_the_cell_it_increases():
    """255 against 1 moves 255 onto the 1, which wraps to 0.

    167 SEEDs bring array 22's head to 23 * 167 % 256 == 1; 'X' XOR 167
    stores 255 alone in array 0, so the two heads are the outermost pair.
    """
    code = "SEED " * 167 + "CONSUME ACCEPT CONFLAGRATE"
    expected = compare(code, "X", 400)
    assert expected.halted
    assert expected.arrays[0] == [0]
    assert expected.arrays[22] == [0]


def test_hello_world_fixture_matches():
    from pathlib import Path

    code = (Path(__file__).parents[1] / "fixtures/mammalian.txt").read_text()
    expected = compare(code, "", 5000)
    assert expected.halted
    assert expected.output == "Hello, world!\n"


def test_unknown_words_are_rejected_by_both():
    for code in ("seed", "SEEDSEED", "SEED!", "SEED FOO"):
        with pytest.raises(ValueError, match=code):
            Reference(code, "")
        with pytest.raises(ValueError, match="unknown SLOW ACV MAMMALIAN command"):
            _Machine(code, ScriptedIO())


def generated(table, row, n):
    code = esolangs.generate("SLOW ACV MAMMALIAN", table)
    stdin = format(row, f"0{n}b")
    expected = compare(code, stdin, 200000)
    assert expected.halted, (table, row)
    assert expected.output == table[row]
    assert expected.read == n


def test_one_input_generated_tables():
    for table in ("00", "01", "10", "11"):
        for row in range(2):
            generated(table, row, 1)


@pytest.mark.medium
def test_two_input_generated_tables():
    n = 2
    for value in range(1 << (1 << n)):
        table = format(value, f"0{1 << n}b")
        for row in range(1 << n):
            generated(table, row, n)


@pytest.mark.medium
def test_three_input_generated_tables():
    n = 3
    rng = random.Random(1729 + n)
    tables = [format(rng.getrandbits(1 << n), f"0{1 << n}b") for _ in range(6)]
    for table in tables:
        for row in range(1 << n):
            generated(table, row, n)
