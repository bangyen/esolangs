"""Super SNUSP agrees with an independent model of wiki revision 194514.

The page has no threads, no call stack and no SNUSP ``@``/``#``/``&``: those
characters are IN, OUT and AND.  The tape is a signed, unbounded integer map.
``/`` and ``\\`` are "same as in SNUSP": reflections (SNUSP wiki revision
74965: ``\\`` swaps left/up and right/down, ``/`` right/up and left/down).
Ambiguities the page leaves open, pinned at the interpreter's choice:

- With no ``"`` the IP "starts at bottom right" with no heading; it moves
  left.  The page's own cat example has no ``"`` and runs only from the top
  left (see ``test_wiki_cat_needs_a_start_marker``).
- EOF on ``,`` or ``@`` raises rather than storing a value.
- ``.`` writes ``chr(cell)`` ("byte character" is not reduced mod 256); a
  cell outside ``range(0x110000)`` is an error.
- ROOT of degree <= 0 and shifts by a negative count are errors.
"""

import itertools

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.grid_based.super_snusp import _Machine, run
from esolangs.interpreters.io import ScriptedIO
from esolangs.tools.super_snusp import super_snusp
from tests.interpreters.views import view as vm_view

HEADINGS = ((0, 1), (1, 0), (0, -1), (-1, 0))


class FaultError(Exception):
    """A command the page leaves undefined (empty stack, zero divisor, ...)."""


class Draws:
    def __init__(self, choice=0):
        self.choice = choice
        self.calls = []

    def randbelow(self, upper):
        self.calls.append(upper)
        return self.choice % upper


def floor_root(value, degree):
    if degree <= 0 or (value < 0 and degree % 2 == 0):
        raise FaultError
    lo, hi = (0, value + 1) if value >= 0 else (value, 0)
    while hi - lo > 1:  # largest r in [lo, hi) with r**degree <= value
        mid = (lo + hi) // 2
        lo, hi = (mid, hi) if mid**degree <= value else (lo, mid)
    return lo


def remainder(cell, top):
    return (abs(cell) % abs(nonzero(top))) * (-1 if cell < 0 else 1)


def nonzero(value):
    if value == 0:
        raise FaultError
    return value


def count(value):
    if value < 0:
        raise FaultError
    return value


BINARY = {
    "%": remainder,
    "&": lambda a, b: a & b,
    "|": lambda a, b: a | b,
    "^": lambda a, b: a ^ b,
    "*": lambda a, b: a * b,
    "+": lambda a, b: a + b,
    "-": lambda a, b: a - b,
    ":": lambda a, b: a // nonzero(b),
    ";": floor_root,
    "[": lambda a, b: a << count(b),
    "]": lambda a, b: a >> count(b),
}
UNARY = {
    "(": lambda a: a - 1,
    ")": lambda a: a + 1,
    "_": lambda a: -a,
    "~": lambda a: ~a,
}
# Mirrors as in SNUSP: ``/`` swaps right/up and left/down, ``\`` right/down.
SLASH = {(0, 1): (-1, 0), (-1, 0): (0, 1), (0, -1): (1, 0), (1, 0): (0, -1)}
BACKSLASH = {(0, 1): (1, 0), (1, 0): (0, 1), (0, -1): (-1, 0), (-1, 0): (0, -1)}


class Reference:
    def __init__(self, rows, stdin="", choice=0):
        width = max(map(len, rows))
        self.rows = [row.ljust(width) for row in rows]
        starts = [
            (r, c)
            for r, row in enumerate(self.rows)
            for c, ch in enumerate(row)
            if ch == '"'
        ]
        if starts:
            self.at, self.heading = starts[0], (0, 1)
        else:
            self.at, self.heading = (len(rows) - 1, width - 1), (0, -1)
        self.tape, self.pointer, self.stack = {}, 0, []
        self.digit = self.done = False
        self.stdin, self.offset, self.output = stdin, 0, []
        self.choice, self.draws = choice, []
        self.error = None

    @property
    def cell(self):
        return self.tape.get(self.pointer, 0)

    @cell.setter
    def cell(self, value):
        self.tape[self.pointer] = value

    def read_char(self):
        if self.offset == len(self.stdin):
            raise EOFError
        self.offset += 1
        return ord(self.stdin[self.offset - 1])

    def read_number(self):
        rest = self.stdin[self.offset :]
        token = rest.lstrip()
        if not token:
            self.offset = len(self.stdin)
            raise EOFError
        token = token.split()[0]
        self.offset = len(self.stdin) - len(rest.lstrip()) + len(token)
        return int(token)

    def step(self):
        if self.done:
            return
        try:
            self._step()
        except FaultError:
            self.error = "runtime"
        except EOFError:
            self.error = "eof"
        except ValueError:
            self.error = "value"

    def _step(self):
        row, col = self.at
        op = self.rows[row][col]
        stride = 1
        if op == "'":
            self.done = True
            return
        if op.isascii() and op.isdigit():
            self.cell = (self.cell * 10 if self.digit else 0) + int(op)
        elif op.isascii() and op.isalpha():
            self.cell = ord(op)
        elif op in BINARY:
            if not self.stack:
                raise FaultError
            self.cell = BINARY[op](self.cell, self.stack[-1])
        elif op in UNARY:
            self.cell = UNARY[op](self.cell)
        elif op == "!":
            stride = 2
        elif op == "?":
            stride = 2 if self.cell == 0 else 1
        elif op == "`":
            stride = 2 if self.cell < 0 else 1
        elif op == "#":
            self.output.append(str(self.cell))
        elif op == ".":
            if not 0 <= self.cell <= 0x10FFFF:
                raise FaultError
            self.output.append(chr(self.cell))
        elif op == ",":
            self.cell = self.read_char()
        elif op == "@":
            self.cell = self.read_number()
        elif op == "{":
            self.stack.append(self.cell)
        elif op in "}$=":
            if not self.stack:
                raise FaultError
            if op == "}":
                self.cell = self.stack[-1]
            elif op == "$":
                self.stack.pop()
            else:
                low, high = sorted((self.cell, self.stack.pop()))
                self.draws.append(high - low + 1)
                self.cell = low + self.choice % (high - low + 1)
        elif op == "<":
            self.pointer -= 1
        elif op == ">":
            self.pointer += 1
        elif op == "/":
            self.heading = SLASH[self.heading]
        elif op == "\\":
            self.heading = BACKSLASH[self.heading]
        self.digit = op.isascii() and op.isdigit()
        row += stride * self.heading[0]
        col += stride * self.heading[1]
        self.at = row, col
        self.done = not (0 <= row < len(self.rows) and 0 <= col < len(self.rows[0]))

    def view(self):
        cursor = None if self.done else (*self.at, HEADINGS.index(self.heading))
        # The tape is sparse: a cell set to zero is absent, not stored.
        cells = tuple(sorted((k, v) for k, v in self.tape.items() if v))
        state = (self.pointer, cells, tuple(self.stack), self.digit, self.done)
        return (
            cursor,
            *state[:3],
            None if self.done else self.digit,
            self.done,
            [v for _, v in cells],
            None if self.done else (*cursor, *state, self.offset),
            "".join(self.output),
            self.offset,
            self.draws,
        )


def machine_view(machine, io, draws):
    _cursor, (pointer, cells), values, digit, done = machine.state
    assert list(values) == vm_view(machine, "stack")
    return (
        vm_view(machine, "ip"),
        pointer,
        cells,
        tuple(values),
        None if done else digit,  # unobservable once halted
        done,
        vm_view(machine, "memory"),
        None if done else machine.snapshot(),
        io.getvalue(),
        io.position(),
        draws.calls,
    )


def step_machine(machine):
    try:
        machine.step()
    except HaltError:
        return "runtime"
    except EOFError:
        return "eof"
    except ValueError:
        return "value"
    return None


def compare(rows, stdin="", cap=200, choice=0):
    """Step both engines ``cap`` times; return the reference at the end."""
    ref = Reference(rows, stdin, choice)
    io, draws = ScriptedIO(stdin), Draws(choice)
    machine = _Machine(rows, io, draws)
    for count in range(cap + 1):
        assert machine_view(machine, io, draws) == ref.view(), (rows, stdin, count)
        if ref.done or ref.error or count == cap:
            break
        ref.step()
        assert step_machine(machine) == ref.error, (rows, stdin, count)
    if ref.done:
        before = machine.snapshot(), io.getvalue()
        machine.step()
        machine.step()
        assert (machine.snapshot(), io.getvalue()) == before
    return ref


def check_instruction(op, cell, stack, *, at=(2, 2), heading=0, digit=False, stdin=""):
    rows = ["     "] * 5
    rows[at[0]] = rows[at[0]][: at[1]] + op + rows[at[0]][at[1] + 1 :]
    ref = Reference(rows, stdin)
    ref.at, ref.heading = at, HEADINGS[heading]
    ref.tape, ref.stack, ref.digit = ({0: cell} if cell else {}), list(stack), digit
    io, draws = ScriptedIO(stdin), Draws()
    machine = _Machine(rows, io, draws)
    tape = (0, ((0, cell),) if cell else ())
    machine.state = ((*at, heading), tape, tuple(stack), digit, False)
    ref.step()
    assert step_machine(machine) == ref.error, (op, cell, stack, heading, stdin)
    if not ref.error:
        assert machine_view(machine, io, draws) == ref.view(), (op, cell, stack)


COMMANDS = " !\"#$%&'()*+,-./0123456789:;<=>?@AZaz[\\]^_`{|}~\u0661é"
VALUES = (-9, -2, -1, 0, 1, 2, 3, 9, 4225, (1 << 70) + 5, 0x110000)


@pytest.mark.parametrize("op", COMMANDS)
def test_instruction_domains(op):
    # A shift or root by 2**70 would build 2**70-bit integers in both engines.
    tops = VALUES[:-2] if op in "[];" else VALUES
    stacks = [()] + [(v,) for v in tops] + [(7, -2)]
    for cell, stack in itertools.product(VALUES, stacks):
        for heading, digit in itertools.product(range(4), (False, True)):
            check_instruction(op, cell, stack, heading=heading, digit=digit, stdin="A")
        for stdin in ("", " ", "-12 7", "x", "\n"):
            check_instruction(op, cell, stack, stdin=stdin)


@pytest.mark.parametrize("op", "!?`/\\ )'")
def test_grid_edges(op):
    for at, heading, cell in itertools.product(
        itertools.product(range(5), range(5)), range(4), (-1, 0, 1)
    ):
        check_instruction(op, cell, (), at=at, heading=heading)


LINEAR = "12{}+-_?!`()#.><$"


def linear_corpus():
    for length in range(4):
        for body in itertools.product(LINEAR, repeat=length):
            yield ['"' + "".join(body)]


def grid_corpus():
    for cells in itertools.product("\"'/\\?!) #", repeat=4):
        yield ["".join(cells[:2]), "".join(cells[2:])]


@pytest.mark.parametrize("cap", [0, 1, 2, 5, 60])
def test_bounded_linear_states(cap):
    for rows in linear_corpus():
        compare(rows, cap=cap)


@pytest.mark.parametrize("cap", [0, 1, 3, 40])
def test_bounded_grid_states(cap):
    for rows in grid_corpus():
        compare(rows, cap=cap)


def test_run_output_matches_reference():
    for rows in itertools.chain(linear_corpus(), grid_corpus()):
        ref = Reference(rows)
        for _ in range(60):
            ref.step()
        if not ref.done or ref.error:
            continue
        io = ScriptedIO()
        run(rows, io)
        assert io.getvalue() == "".join(ref.output), rows


def test_input_and_random_controls():
    for stdin in ("", "A", "AB", "é\n", " -42 7", "+5", "x"):
        for code in ('",.,.', '"@#@#', '",#@#'):
            compare([code], stdin)
    for choice in range(6):
        for code in ('"5{2=#', '"2{5=#', '"5_{3=#', '"3{3=#', '"={'):
            compare([code], choice=choice)


# The page's examples verbatim, less their four-column wiki indent.
HELLO = [
    "\"33>d>l>r>o>W>32>44>o>l>l>e>H!/ ?\\' ",
    " " * 30 + "\\<./",
]


def test_wiki_hello_world():
    ref = compare(HELLO, cap=1000)
    assert (ref.done, ref.error, "".join(ref.output)) == (True, None, "Hello, World!")
    io = ScriptedIO()
    run(HELLO, io)
    assert io.getvalue() == "Hello, World!"


def test_wiki_cat_needs_a_start_marker():
    """The page's cat has no ``"`` and works only from the top left.

    From the bottom right moving left, ``/`` turns it off the grid at once,
    so the verbatim example prints nothing; with a ``"`` prepended (one
    column, both rows) it echoes until EOF, which raises.
    """
    cat = [",!/ ?\\'", "  \\,./"]
    ref = compare(cat, "abc")
    assert (ref.done, "".join(ref.output), ref.offset) == (True, "", 0)
    ref = compare(['"' + cat[0], " " + cat[1]], "abc")
    assert (ref.error, "".join(ref.output), ref.offset) == ("eof", "abc", 3)


@pytest.mark.parametrize("width", [None, 1, 2, 3, 5, 8])
@pytest.mark.parametrize("n", [1, 2])
def test_generated_small_tables(n, width):
    for value in range(1 << (1 << n)):
        table = f"{value:0{1 << n}b}"
        rows = super_snusp(table, width).splitlines()
        for row, answer in enumerate(table):
            ref = compare(rows, f"{row:0{n}b}", cap=5000)
            assert (ref.done, ref.error, "".join(ref.output)) == (True, None, answer)
            assert ref.offset == n


@pytest.mark.parametrize("width", [None, 4, 9])
def test_generated_three_input_tables(width):
    for value in range(0, 256, 7):
        table = f"{value:08b}"
        rows = super_snusp(table, width).splitlines()
        for row, answer in enumerate(table):
            ref = compare(rows, f"{row:03b}", cap=20000)
            assert (ref.done, ref.error, "".join(ref.output)) == (True, None, answer)
