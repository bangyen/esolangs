"""Independent Malbolge machine: load, decipher, crazy, rotate, encipher.

Written from the esolangs.org Malbolge page, wiki revision 195070: the
``(C+[C])%94`` opcode table with the reference interpreter's I/O codes, the
three-by-three crazy table, the ORIGINAL/TRANSLATED encipherment, the
crazy-operation memory fill and the 33-126 halt rule.  Truth-machine controls
come from the Truth-machine page, wiki revision 197006.

Pinned where that page is silent or says "undefined":

* a source shorter than two words fills from absent predecessors read as 0
  (the page calls this undefined behavior of the reference implementation);
* a cell at ``C`` outside 33-126 after an instruction is left unenciphered
  (the page: "the result is undefined");
* EOF reads 59048, and a read stores the character's code point unreduced,
  so a code point above 59048 is not a ten-trit word (the page only says
  ``A = INPUT``; EOF and wide characters are not specified).
"""

import itertools
import random
from functools import lru_cache

import pytest

from esolangs import generate
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.malbolge import _Machine, run
from tests.interpreters.views import view as vm_view

WORDS = 3**10
#: ``(C+[C])%94`` to instruction, per the page's table.
OPS = {4: "i", 5: "<", 23: "/", 39: "*", 40: "j", 62: "p", 68: "o", 81: "v"}
#: The page's crazy table, keyed by (A trit, [D] trit).
CRAZY = {
    (0, 0): 1,
    (1, 0): 0,
    (2, 0): 0,
    (0, 1): 1,
    (1, 1): 0,
    (2, 1): 2,
    (0, 2): 2,
    (1, 2): 2,
    (2, 2): 1,
}
TRANSLATED = (
    "5z]&gqtyfr$(we4{WP)H-Zn,[%\\3dL+Q;>U!pJS72FhOA1C"
    "B6v^=I_0/8|jsb9m<.TVac`uY*MK'X~xDl}REokN:#?G\"i@"
)
CIPHER = {33 + index: ord(char) for index, char in enumerate(TRANSLATED)}


def crazy_trits(a, d, width):
    return sum(CRAZY[a // 3**k % 3, d // 3**k % 3] * 3**k for k in range(width))


#: Five-trit halves, so a ten-trit crazy is two lookups.
HALF = [[crazy_trits(a, d, 5) for d in range(243)] for a in range(243)]


def crazy(a, d):
    low = HALF[a % 243][d % 243]
    return low + 243 * HALF[a // 243 % 243][d // 243 % 243]


def rotate_right(value):
    return value // 3 + value % 3 * 3**9


def instruction(address, value):
    return OPS.get((address + value) % 94, "o")


@lru_cache(maxsize=32)
def load(code):
    memory = []
    for char in code:
        if char.isspace():
            continue
        value = ord(char)
        if not 33 <= value <= 126 or (len(memory) + value) % 94 not in OPS:
            raise ValueError(f"{char!r} does not decipher to an instruction")
        memory.append(value)
    start = len(memory)
    memory += [0] * (WORDS - start)
    for address in range(start, WORDS):
        memory[address] = crazy(memory[address - 1], memory[address - 2])
    return tuple(memory)


def reference(code, stdin, cap):
    memory = list(load(code))
    a = c = d = cursor = 0
    output = []
    halted = False
    for _ in range(cap):
        if halted:
            break
        value = memory[c]
        if not 33 <= value <= 126:
            halted = True
            continue
        op = instruction(c, value)
        if op == "v":
            halted = True
            continue
        if op == "i":
            c = memory[d]
        elif op == "j":
            d = memory[d]
        elif op == "*":
            a = memory[d] = rotate_right(memory[d])
        elif op == "p":
            a = memory[d] = crazy(a, memory[d])
        elif op == "<":
            output.append(chr(a % 256))
        elif op == "/":
            if cursor < len(stdin):
                a = ord(stdin[cursor])
                cursor += 1
            else:
                a = WORDS - 1
        if 33 <= memory[c] <= 126:
            memory[c] = CIPHER[memory[c]]
        c = (c + 1) % WORDS
        d = (d + 1) % WORDS
    return "".join(output), (a, c, d, halted, tuple(memory), cursor)


def normalize(code):
    """Decipher a source into the page's opcode-table letters."""
    letters, address = [], 0
    for char in code:
        if char.isspace():
            letters.append(char)
            continue
        op = instruction(address, ord(char))
        letters.append(op)
        address += 1
    return "".join(letters)


def valid(address):
    return [chr(v) for v in range(33, 127) if (address + v) % 94 in OPS]


def short_programs(length):
    return ["".join(chars) for chars in itertools.product(*map(valid, range(length)))]


STDIN = "A\nλ"
CAPS = (0, 1, 2, 3, 5, 10, 40, 400)


def observe(code, stdin, caps):
    """Step one machine, yielding (cap, output, snapshot) at each cap."""
    io = ScriptedIO(stdin)
    machine = _Machine(code, io)
    steps = 0
    for cap in caps:
        while steps < cap and not machine.halted:
            machine.step()
            steps += 1
        snapshot = machine.snapshot()
        assert vm_view(machine, "ip") == (None if machine.halted else snapshot[1])
        assert vm_view(machine, "stack") == []
        yield cap, io.getvalue(), snapshot
    if machine.halted:
        snapshot, output = machine.snapshot(), io.getvalue()
        machine.step()
        machine.step()
        assert machine.snapshot() == snapshot
        assert io.getvalue() == output


def check(code, stdin, caps=CAPS):
    for cap, output, snapshot in observe(code, stdin, caps):
        expected = reference(code, stdin, cap)
        assert (output, snapshot) == expected, (code, stdin, cap)
    if expected[1][3]:
        io = ScriptedIO(stdin)
        run(code, io)
        assert (io.getvalue(), io.position()) == (output, expected[1][5]), code


def test_crazy_matches_the_page_table_trit_by_trit():
    for a, d in itertools.product(range(0, WORDS, 401), range(5, WORDS, 389)):
        assert crazy(a, d) == crazy_trits(a, d, 10)


def test_allowed_source_characters_match_the_page():
    assert "".join(valid(0)) == "'(>DQbcu"
    assert "".join(valid(94)) == "'(>DQbcu"
    assert "".join(valid(1)) == "&'=CPabt"


def test_cat_normalizes_to_the_page_listing():
    assert normalize(CAT) == (
        "jpoo*pjoooop*ojoopoo*ojoooooppjoivvv\no/i\n<iviv\ni<vvvvvvvvvvvvv\noji"
    )


@pytest.mark.parametrize("shard", range(9))
def test_every_one_and_two_word_program(shard):
    for code in (short_programs(1) + short_programs(2))[shard::9]:
        check(code, STDIN)


#: A seeded 32 of the 512 three-word programs.
THREE_WORDS = random.Random(3).sample(short_programs(3), 32)


@pytest.mark.parametrize("shard", range(4))
def test_sampled_three_word_programs(shard):
    for code in THREE_WORDS[shard::4]:
        check(code, STDIN)


@pytest.mark.parametrize(
    "code",
    [" ", "", " \n\tQ ", "(=BA#9", '(=BA#9\n"=<;']
    + [char + " \n&" for char in valid(0)],
)
@pytest.mark.parametrize("stdin", ["", "Z", "A\nλ", "\U0001f600", "\0"])
def test_boundary_witnesses(code, stdin):
    check(code, stdin)


@pytest.mark.parametrize(
    ("stdin", "output"),
    [
        ("Z", "Z"),
        ("", chr(59048 % 256)),  # pinned: EOF is 59048, the page is silent
        ("\U00010041", "A"),  # pinned: A keeps the unreduced code point
    ],
)
def test_read_then_print(stdin, output):
    assert normalize("ub") == "/<"
    assert reference("ub", stdin, 3)[0] == output
    check("ub", stdin, (1, 2, 3))


def test_non_instructions_are_rejected_at_load():
    for code in ["x", "Q\x7f", "Q~", "é", "QQ"]:
        with pytest.raises(ValueError, match="does not decipher"):
            load(code)
        with pytest.raises(ValueError, match="does not decipher"):
            _Machine(code, ScriptedIO())


#: The page's cat: copies input and never stops.
CAT = '(=BA#9"=<;:3y7x54-21q/p-,+*)"!h%B0/.\n~P<\n<:(8&\n66#"!~}|{zyxwvu\ngJ%'
#: The Truth-machine page's Malbolge entry.
TRUTH = (
    " (aONMLKJIHGFEDCBA@?>=<;:98765FD21dd!-,O*)y'&v5#\"!DC|Qzf,*vutsrqpF!Clk|ih\n"
    " gfed9(T&6KoOHZYXWVUTSRQPONM]KJIHGFEDCBA@?>=<;:9876\"'~g|edybav_zyxwvotsrq\n"
    ' pSnPlOjibKfedcba`_XA??ZYRW:UTSLQ3ONMLK.IHGFE>CBA@?"=<;:38765432s0/.n,+*)\n'
    ' j!&%f{"!~}|_zyxZvYnsrqpRnmlkjML:f_^GF!\n'
)
#: Hello world, as pinned in test_malbolge.py.
HELLO = (
    "(=<`#9]~6ZY327Uv4-QsqpMn&+Ij\"'E%e{Ab~w=_:]Kw%o44Uqp0/"
    "Q?xNvL:`H%c#DD2^WV>gY;dts76qKJImZkj"
)


def test_positive_controls_from_the_page():
    assert reference(CAT, "Hi!", 400)[0].startswith("Hi!")
    output, state = reference(TRUTH, "0", 10_000)
    assert (output, state[3]) == ("0", True)
    output, state = reference(TRUTH, "1", 10_000)
    assert len(output) > 10
    assert set(output) == {"1"}
    assert not state[3]
    output, state = reference(HELLO, "", 10_000)
    assert (output, state[3]) == ("Hello, world.", True)
    assert reference("Q", "", 1)[1][3]


@pytest.mark.parametrize("code", [CAT, TRUTH, HELLO])
@pytest.mark.parametrize("stdin", ["", "0", "1", "Hi!"])
def test_page_programs_match(code, stdin):
    check(code, stdin, (0, 1, 7, 50, 300, 2000))


def generated():
    for n in (1, 2):
        for bits in itertools.product("01", repeat=1 << n):
            yield "".join(bits)
    yield from ["01101001", "00010111", "1000000000000001"]


@pytest.mark.parametrize("table", list(generated()))
def test_generated_programs_run_like_the_reference(table):
    code = str(generate("malbolge", table))
    n = len(table).bit_length() - 1
    for row in range(1 << n):
        stdin = format(row, f"0{n}b")
        output, state = reference(code, stdin, 100_000)
        assert state[3], (table, row)
        assert output == table[row]
        assert state[5] == n
        io = ScriptedIO(stdin)
        run(code, io)
        assert io.getvalue() == output
        assert io.position() == state[5]
    check(code, "1" * n, (0, 1, 3, 30, 300))
