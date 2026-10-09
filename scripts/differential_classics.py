"""FALSE, Malbolge and Fish for ``differential.py``: generators and patches."""

from __future__ import annotations

import random
import re
import tomllib
from pathlib import Path


def _wiki(language: str) -> list[str]:
    """Return the wiki example sources pinned in ``tests/fixtures``."""
    path = Path(__file__).parents[1] / "tests/fixtures/wiki_examples"
    data = tomllib.loads((path / f"{language}.toml").read_text("utf-8"))
    return [example["source"] for example in data["examples"]]


# --- FALSE ----------------------------------------------------------------

FALSE_TOKEN = re.compile(r"[a-z][:;]|'.|\"[^\"]*\"|\{[^}]*\}|\d+|.", re.DOTALL)


def false_join(tokens: list[str]) -> str:
    """Join tokens, keeping two adjacent numbers apart."""
    out = ""
    for token in tokens:
        out += " " * (out[-1:].isdigit() and token[:1].isdigit()) + token
    return out


def false_block(rng: random.Random, depth: int = 0) -> list[str]:
    """Return tokens of a FALSE block; variables only as ``x:``/``x;``.

    A bare variable reference never sits on the stack: ours makes it the
    integer 0..25, the portable reference a third type.  Loops count a
    private variable (``i``..``k``) down, so they halt.
    """
    out: list[str] = []
    for _ in range(rng.randint(1, 7 - 2 * depth)):
        roll = rng.random()
        if roll < 0.2:
            out.append(
                str(rng.choice((rng.randint(0, 9), rng.randint(0, 999), 2**31 - 1)))
            )
        elif roll < 0.24:
            out.append("'" + rng.choice("aZ0 \n!~{}"))
        elif roll < 0.44:
            out.append(rng.choice("$$%%\\\\@@++--**//&|__~~==>>"))
        elif roll < 0.52:
            out.append(rng.choice(".,"))
        elif roll < 0.6:
            out.append(rng.choice("abcxyz") + rng.choice(":;"))
        elif roll < 0.63:
            out += [str(rng.randint(-1, 3)), "O"] if rng.random() < 0.9 else ["O"]
        elif roll < 0.67:
            out.append('"' + "".join(rng.choice("ab 1\n[]{'") for _ in range(3)) + '"')
        elif roll < 0.71:
            out.append("^")
        elif roll < 0.73:
            out.append("{" + rng.choice(("", "x", "[", '"', "]")) + "}")
        elif roll < 0.75:
            out.append(rng.choice((" ", "\n", "\t", "B", "X", "(", "\xdf")))
        elif depth >= 2:
            out.append(rng.choice("+-.,$%"))
        elif roll < 0.82:
            out += ["[", *false_block(rng, depth + 1), "]", rng.choice("!!?")]
        elif roll < 0.88:
            v = "ijk"[depth]
            out += [str(rng.randint(0, 4)), v + ":", "[", v + ";", "0", ">", "]"]
            out += ["[", *false_block(rng, depth + 1), v + ";", "1", "-", v + ":"]
            out += ["]", "#"]
        elif roll < 0.9:
            out += list("[^$1_=~][,]#") if rng.random() < 0.5 else list("[^1_=~][]#")
        elif roll < 0.95:
            out += ["[", *false_block(rng, depth + 1), "]", "f:", "f;", "!"]
            out += ["f;", "!"] if rng.random() < 0.3 else []
        else:
            out += ["[", *false_block(rng, depth + 1), "]"]
    return out


def false_program(rng: random.Random) -> str:
    """Return a FALSE program: numbers, a stored variable or two, a block."""
    if rng.random() < 0.03:
        return rng.choice(_wiki("false"))
    out = [str(rng.randint(0, 20)) for _ in range(rng.randint(1, 5))]
    for name in rng.sample("abcxyz", rng.choice((0, 1, 2, 3))):
        out += [str(rng.randint(-5, 300)), name + ":"]
    out += false_block(rng)
    return false_join(out + ["."] * rng.choice((0, 1, 1, 2)))


def false_valid(program: str) -> bool:
    """Whether brackets, strings, comments and quotes all close."""
    from esolangs.interpreters.stack_based.false import _closers

    try:
        _closers(program)
    except ValueError:
        return False
    return True


# --- Malbolge -------------------------------------------------------------


def malbolge_ops(program: str) -> list[str]:
    """Decode each source cell to its instruction, or ``!`` plus a bad char."""
    from esolangs.interpreters.other.malbolge import _op

    cells = [char for char in program if char not in " \t\n\r\x0b\x0c"]
    ops = [
        _op(ord(char), i) if ord(char) < 127 else None for i, char in enumerate(cells)
    ]
    return [
        op if op is not None and op in "ji*p</vo" else "!" + char
        for op, char in zip(ops, cells, strict=True)
    ]


def malbolge_valid(program: str) -> bool:
    """At least two cells: the reference fills cell 2 on from the two before."""
    return len(malbolge_ops(program)) >= 2


def malbolge_join(ops: list[str]) -> str:
    """Encode instructions (normalized Malbolge) at their cell positions."""
    from esolangs.interpreters.other.malbolge import _XLAT1

    return "".join(
        op[1:] if op[0] == "!" else chr((_XLAT1.index(op) - i) % 94 + 33)
        for i, op in enumerate(ops)
    )


def malbolge_program(rng: random.Random) -> str:
    """Return normalized Malbolge: eight instructions, then encrypted.

    At least two cells (the reference fills cell 2 onward from the previous
    two, and reads before ``mem`` with fewer).  Now and then a cell that
    is no instruction, or whitespace (the C and Python sets agree on these
    six), goes in.  The wiki's cat runs past any bound.
    """
    if rng.random() < 0.02:
        return rng.choice(_wiki("malbolge"))
    ops = rng.choices(
        "ji*p</vo", weights=(2, 2, 3, 3, 5, 3, 1, 8), k=rng.randint(2, 40)
    )
    if rng.random() < 0.4:
        ops.append("v")
    if rng.random() < 0.04:
        ops.insert(rng.randrange(len(ops)), "!" + rng.choice("\x7f\xe9ABC"))
    text = list(malbolge_join(ops))
    for _ in range(rng.choice((0, 0, 0, 0, 1, 3))):
        text.insert(rng.randrange(len(text) + 1), rng.choice(" \t\n\r\x0b\x0c"))
    return "".join(text)


# --- Fish -----------------------------------------------------------------

_FISH_CELLS = (
    "0123456789abcdef" * 2
    + "+-*,%()="
    + ":~$@}{rl" * 2
    + "[]&&gp!?"
    + "onon;; "
    + "><|#"
    + "i'\""
)
#: Idioms: register, stack-of-stacks (including too few values), ``g``/``p``
#: in, past and before the box (``p`` writing a control character into the
#: code), float division, a jump, and EOF.
_FISH_IDIOMS = (
    "1&&n",
    "&",
    "23&&&n",
    "123 2[rnn]n",
    "12 3[",
    "0[l]n",
    "]l",
    "1[2&]&n",
    "00gn",
    "f0gn",
    "01-0gn",
    '"z"01-0p01-0gno',
    "a00p",
    "9a0p",
    "c88*p",
    "6a*f0p",
    "94,n",
    "10,",
    "52,o",
    "32,:n",
    "00.",
    "a0.",
    "i:n",
    "io",
    "ff*f*:*n",
)


def fish_program(rng: random.Random) -> str:
    """Return a one-line run or a small grid; never ``x``, never ``#!``."""
    if rng.random() < 0.03:
        return rng.choice(_wiki("fish"))
    if rng.random() < 0.5:
        cells = [rng.choice("0123456789abcdef") for _ in range(rng.randint(0, 5))]
        cells += [rng.choice(_FISH_CELLS + "nnoo") for _ in range(rng.randint(1, 14))]
        for _ in range(rng.choice((0, 1, 1, 2))):
            cells.insert(rng.randrange(len(cells) + 1), rng.choice(_FISH_IDIOMS))
        if rng.random() < 0.1:
            cells.insert(0, rng.choice(("<", '"', "\t")))
        rows = ["".join(cells) + (";" if rng.random() < 0.8 else "")]
    else:
        width, height = rng.randint(2, 8), rng.randint(2, 5)
        rows = [
            "".join(rng.choice(_FISH_CELLS + "^v/\\_;") for _ in range(width))
            for _ in range(height)
        ]
        if rng.random() < 0.5:
            rows[rng.randrange(height)] += rng.choice(_FISH_IDIOMS)
        if rng.random() < 0.3:
            rows[-1] = rows[-1][: rng.randint(0, width)]
    program = "\n".join(rows)
    return "<" + program[2:] if program.startswith("#!") else program


def fish_valid(program: str) -> bool:
    """fish.py strips a ``#!`` line, and ours rejects an empty box."""
    return bool(program.strip("\n")) and not program.startswith("#!")


FALSE_PATCHES: tuple[tuple[str, str], ...] = (
    # Reference bug: a string, comment or lambda that closes on the
    # last byte reads as unterminated (the end marker is one short).
    ("ent=s-1;", "ent=s;"),
    # `a` is not argc: an unstored variable reads as an error (ours).
    ("var[1]=(X)NUM;var[0]=(X)ic;", ""),
    (
        "l(';')pop(b,VADR)push(",
        "l(';')pop(b,VADR)if(*(((XP)b)+1)==(X)UNDEF)x(6)push(",
    ),
    # Ours raises on a zero divisor; INT_MIN/-1 wraps.
    (
        "l('/')op(/)",
        "l('/')po(b)po(d)if(!(int)b)x(6)pu((X)(long)(int)((long long)(int)d/(int)b))",
    ),
    # Comparing lambdas is computing on them, which ours refuses.
    ("l('=')cm(==,tt)", "l('=')po(b)po(d)pu((X)(long)-((int)d==(int)b))"),
    ("l('>')cm(>,tt)", "l('>')po(b)po(d)pu((X)(long)-((int)d>(int)b))"),
    # Reference bug: a negative or huge pick (`t=b*2` overflows) reads
    # outside the stack.
    ("l('O')po(b)", "l('O')po(b)if((int)b<0||(int)b>MS)x(5)"),
    # Reference bug: the scan for a lambda's `]` reads `'[` or `'{` as
    # a bracket or comment; `'c` is a literal (ours, and the compiler).
    ("if(a=='['){t++;}", "if(a=='\\''){p++;}else if(a=='['){t++;}"),
    # `B` flushes output only (this C library drops buffered input).
    ("fflush(stdout);fflush(stdin);", "fflush(stdout);"),
    # Ours ignores unknown characters and a nonempty stack at exit.
    ("break;default:x(8);", "break;default:;"),
    ("c=0;p=0;if(S!=se)x(7);", "c=0;p=0;"),
    # Errors exit 71 (stack overflow is a limit, 72) without a report.
    (
        "er:if(ernum) {",
        "er:if(ernum) {fflush(stdout);return ernum==4||ernum==13?72:71;",
    ),
)


MALBOLGE_PATCHES: tuple[tuple[str, str], ...] = (
    ("#include <malloc.h>", ""),  # not on macOS; stdlib.h declares malloc
    # Ours halts at a code cell outside 33..126 (the spec ends the
    # program; the reference spins), and does not encrypt such a cell
    # after `i` lands on it (the reference indexes outside xlat2).
    (
        "if ( mem[c] < 33 || mem[c] > 126 ) continue;",
        "if ( mem[c] < 33 || mem[c] > 126 ) return;",
    ),
    (
        "mem[c] = xlat2[mem[c] - 33];",
        "if ( mem[c] >= 33 && mem[c] <= 126 ) mem[c] = xlat2[mem[c] - 33];",
    ),
    # Reference bug: it loads a non-graphic, non-space byte unchecked
    # (the spec, and ours, reject it).
    ("if ( x < 127 && x > 32 )", "if ( x > 126 || x < 33 ) goto bad; else"),
    ("% 94] ) == NULL )\n      {", "% 94] ) == NULL )\n      { bad:"),
)


FISH_PATCHES: tuple[tuple[str, str], ...] = (
    # A space is codepoint 32 to `g` (ours stores raw codepoints).
    ('0 if char == " " else ord(char)', "ord(char)"),
    # The box is a rectangle (ours), grown by `p` at positive cells.
    (
        "self._position = [-1,0]",
        "self._position = [-1,0]\n        self._h = len(code.splitlines())\n"
        "        self._w = max(map(len, code.splitlines()))",
    ),
    (
        "self._position[1] > max(self._codebox.keys()):",
        "self._position[1] >= self._h:",
    ),
    (
        "self._position[1] = max(self._codebox.keys())",
        "self._position[1] = self._h - 1",
    ),
    (
        "self._position[0] > max(self._codebox[self._position[1]].keys()):",
        "self._position[0] >= self._w:",
    ),
    (
        "self._position[0] = max(self._codebox[self._position[1]].keys())",
        "self._position[0] = self._w - 1",
    ),
    (
        "self._codebox[x][y] = z",
        "assert x == int(x) and y == int(y) and z == int(z)\n"
        "            self._codebox[x][y] = z\n"
        "            self._h = max(self._h, x + 1)\n"
        "            self._w = max(self._w, y + 1)",
    ),
    # Coordinates, counts and `o`'s codepoint must be integral (ours).
    (
        "x, y = self._pop(), self._pop()\n",
        "x, y = self._pop(), self._pop()\n"
        "            assert x == int(x) and y == int(y)\n",
    ),
    (
        "y, x = self._pop(), self._pop()\n",
        "y, x = self._pop(), self._pop()\n"
        "            assert x == int(x) and y == int(y)\n",
    ),
    (
        "self._output(chr(int(self._pop())))",
        "o = self._pop()\n            assert o == int(o)\n"
        "            self._output(chr(o))",
    ),
    # Reference bug: `[` moving more values than the stack holds (the
    # spec's "too few values" error) slices instead.
    (
        "count = int(self._pop())",
        "count = self._pop()\n"
        "            assert count == int(count) and 0 <= count <= len(self._stack)",
    ),
    # A negative cell is an invalid instruction, and an empty cell (0) is
    # a NOP that a string pushes as 0, not as a space (ours).
    ('chr(instruction) if instruction > 0 else " "', "chr(instruction)"),
    ('elif instruction == " ":', 'elif instruction in " \\0":'),
    # A surrogate codepoint is output like any other (ours), not a
    # failure to encode it; errors exit 71.
    (
        "import sys\n",
        "import sys\nsys.stdout.reconfigure(errors='surrogatepass')\n",
    ),
    # A jump past the box re-enters it modulo its size (ours; fish.py
    # walks the empty cells to the edge in the direction of travel).
    (
        "        # wrap around if we reach the borders of the codebox\n",
        "        self._position[0] %= self._w\n        self._position[1] %= self._h\n",
    ),
    ("parser.exit(message=(newline+", "parser.exit(71 if stop.message else 0)#("),
)
