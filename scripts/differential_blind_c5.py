"""Generators and adapters for eight languages checked against clean-room refs.

SLOW ACV MAMMALIAN, Streetcode, Suffolk, Super SNUSP, Taglate, thisthat,
Unsquare and Vandevelo have no other implementation, so each reference is a
"blind" interpreter written from the wiki text alone::

    python scripts/differential.py LANG --patch blind/<slug>.py   # if any
    python scripts/differential.py LANG --ref \
        "env BLIND_STEP_LIMIT=<5 x max_steps> python3 blind/<slug>.py {program}"

Patches bring a reference to a reading our docstrings record as a choice
the page leaves open.  thisthat is generated in ASCII (the harness hands
the reference Latin-1); its reference is a wrapper that maps
``THISTHAT_ASCII`` back before running ``blind/thisthat.py``.  Suffolk never
halts, so it runs at the default limit and only output prefixes count.
``differential.py`` registers ``SPECS``.
"""

from __future__ import annotations

import dataclasses
import random
import sys
from typing import Any

# The harness runs as ``__main__`` and registers ``SPECS`` after defining
# ``Spec``; importing ``differential`` here would load it a second time.
_harness = sys.modules.get("differential") or sys.modules["__main__"]
Spec, balanced = _harness.Spec, _harness.balanced


def blind_outcome(code: int, stdout: bytes, stderr: bytes) -> object:
    """Map a blind reference's exit as the harness does, the limit as ``timeout``.

    As ``limit`` it would pass any status of ours that agrees on a prefix,
    hiding a halt or an error of ours inside the reference's budget.  Run
    the reference with ``BLIND_STEP_LIMIT`` at five times ``max_steps``.
    """
    got = _harness.blind_outcome(code, stdout, stderr)
    return dataclasses.replace(got, status="timeout") if code == 124 else got


def ours_utf8(language: str, program: str, stdin: str, max_steps: int) -> Any:
    """``run_ours`` with the output as UTF-8, for a reference writing text.

    The harness encodes Latin-1 until a code point passes 255, so a
    truncated run's encoding would depend on where it stopped.  Checks
    ``esolangs.run`` against the stepping as the harness would.
    """
    vm, outcome = None, _harness.Outcome
    try:
        vm = _harness.make_vm(language, program, stdin)
        for _ in range(max_steps):
            if vm.halted:
                break
            vm.step()
        status, detail = ("halt" if vm.halted else "timeout"), ""
    except Exception as exc:
        status = _harness._ours_status(exc)  # noqa: SLF001
        detail = f"{type(exc).__name__}: {exc}"
    text = vm.output if vm is not None else ""
    if status != "timeout":
        fast = _harness.run_ours_fast(language, program, stdin)
        raw = _harness._bytes(text)  # noqa: SLF001
        if fast.status != status or (status == "halt" and fast.output != raw):
            status = "crash:fastpath"
    return outcome(status, text.encode("utf-8", "surrogatepass"), detail)


_MAMMAL = (
    ("SEED",) * 6
    + ("EXCRETE", "CONSUME", "FISSION", "SPRINT", "LEAPFROG", "CONFLAGRATE")
    + ("DIGEST", "PRONOUNCE", "ACCEPT") * 2
)


def mammalian_program(rng: random.Random) -> str:
    """Return a short word list, SEED-heavy so cells and x leave zero.

    A third start with up to 40 SEEDs, so CONFLAGRATE meets cells near 255.
    """
    words = [rng.choice(_MAMMAL) for _ in range(rng.randint(1, 14))]
    if rng.random() < 0.3:
        words[:0] = ["SEED"] * rng.randint(5, 40) + ["EXCRETE", "CONFLAGRATE"]
    return " ".join(words)


def ascii_input(rng: random.Random, _program: str) -> str:
    """Return ASCII input, now and then empty."""
    pool = "aZ09 \n\x00\x7f"
    return "".join(rng.choice(pool) for _ in range(rng.choice((0, 3, 6, 6))))


#: The reference brought to our readings of what the page leaves open: an
#: empty array is skipped by SEED and ignored by CONSUME, FISSION and
#: LEAPFROG, a zero divisor skips its CONFLAGRATE pair, and a LEAPFROG to
#: the "0th" instruction or past the end halts.  EXCRETE and PRONOUNCE
#: reduce mod 256 (our default dialect; the page says 255).
MAMMALIAN_PATCHES = (
    ('raise Halt(3, "SEED: array %d is empty" % i)', "continue"),
    ('raise Halt(3, "CONSUME on empty array")', "pc = nxt; continue"),
    ('raise Halt(3, "FISSION on empty array")', "pc = nxt; continue"),
    ('raise Halt(3, "LEAPFROG on empty array")', "pc = nxt; continue"),
    ("if not 0 <= t < n:", "if not 0 < t < n:\n                    return"),
    ('raise Halt(3, "CONFLAGRATE: division by zero")', "continue"),
    ('raise Halt(3, "CONFLAGRATE: modulo by zero")', "continue"),
    ("arr.append(x % 255)", "arr.append(x % 256)"),
    ("out.append(x % 255)", "out.append(x % 256)"),
)

#: Street shapes: the wiki's four programs, the test suite's counting ring
#: and junction mouth, and an island; the road under them is re-drawn.
_STREETS = (
    ("+----+", "|    |", "|CIO;|", "+----+"),
    ("+----+", "|UOI |", "|CIOU|", "+----+"),
    ("+-------+", "|       |", "|C      |", "++  ++  |", " |  ++  |",
     " |      |", " |      |", " +------+"),
    ("+--------+", "|        |", "|C^      |", "+-+IO++  |", "  |OI++  |",
     "  |      |", "  |      |", "  +------+"),
    ("+------------+", "|            |", "|C^        O;|", "+--+  ++  +--+",
     "   |      |", "   | ^_~ =|", "   | ^++= |", "   |^^++^U|",
     "   |^^^^^=|", "   |^^^^^^|", "   +------+"),
    ("+---------+", "|         |", "|C^      ;|", "+--+  ++--+", "   |      |",
     "   |;     |", "   +------+"),
    ("+--------+", "|        |", "|C       |", "|  ++++  |", "|  ++++  |",
     "|        |", "|        |", "+--------+"),
)  # fmt: skip


def _road(grid: list[list[str]]) -> list[tuple[int, int]]:
    """Return the cells reachable from ``C`` without crossing ``+-|``."""
    start = next(
        (r, c) for r, row in enumerate(grid) for c, ch in enumerate(row) if ch == "C"
    )
    seen, todo = {start}, [start]
    while todo:
        r, c = todo.pop()
        for cell in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
            if (
                cell not in seen
                and 0 <= cell[0] < len(grid)
                and 0 <= cell[1] < len(grid[cell[0]])
                and grid[cell[0]][cell[1]] not in "+-|"
            ):
                seen.add(cell)
                todo.append(cell)
    return sorted(seen - {start})


def streetcode_program(rng: random.Random) -> str:
    """Return a street shape with its road re-drawn: mostly blanks, some ops.

    A third are a straight two-lane street of random length.
    """
    if rng.random() < 0.3:
        n = rng.randint(1, 8)
        shape: tuple[str, ...] = (
            "+" + "-" * n + "+",
            "|" + " " * n + "|",
            "|C" + " " * (n - 1) + "|",
            "+" + "-" * n + "+",
        )
    else:
        shape = rng.choice(_STREETS)
    grid = [list(line) for line in shape]
    blank = rng.choice((0.4, 0.6, 0.8))
    for r, c in _road(grid):
        grid[r][c] = " " if rng.random() < blank else rng.choice("^^~~==__IIOOU;")
    return "\n".join("".join(row) for row in grid)


#: ``O`` writes the cell as a code point (UTF-8, see ``ours_utf8``)
#: and refuses a negative one, as ours does.
STREETCODE_PATCHES = (
    (
        "out.append(cells.get(cp, 0) % 256)",
        "v = cells.get(cp, 0)\n"
        "                if v < 0:\n"
        '                    raise Halt(3, "O of a negative cell")\n'
        '                out += chr(v).encode("utf-8")',
    ),
)


def streetcode_valid(program: str) -> bool:
    """Whether ours accepts the street (the reference takes any text)."""
    from esolangs.interpreters.grid_based.streetcode import _Machine
    from esolangs.interpreters.io import IO

    try:
        _Machine(program.split("\n"), IO())
    except ValueError:
        return False
    return True


def _streetcode_valid_program(rng: random.Random) -> str:
    while not streetcode_valid(program := streetcode_program(rng)):
        pass
    return program


def suffolk_program(rng: random.Random) -> str:
    """Return a short command string, ``!``/``<``-heavy, now and then a comment."""
    pool = "!!!!<<<<>>.,," + "x " * (rng.random() < 0.1)
    return "".join(rng.choice(pool) for _ in range(rng.randint(1, 20)))


def long_input(rng: random.Random, _program: str) -> str:
    """Return ASCII input long enough that most runs stop short of EOF."""
    return "".join(rng.choice("aZ09 \n\x00\x7f") for _ in range(rng.randint(0, 300)))


#: Every command but ``=`` (random), weighted to arithmetic on a stocked stack.
_SNUSP_OPS = "  !#$%&'()*+,-./0123456789:;<>?@AZaz[\\]^_`{{{|}~" + "{)(#.."


def super_snusp_program(rng: random.Random) -> str:
    """Return one to four rows; a ``"`` in most, mirrors to turn among them.

    Some start by pushing a number, so the stack operators have an operand.
    """
    rows = [
        "".join(rng.choice(_SNUSP_OPS) for _ in range(rng.randint(1, 12)))
        for _ in range(rng.choice((1, 1, 2, 3, 4)))
    ]
    if rng.random() < 0.4:
        rows[0] = f'"{rng.randint(0, 99)}{{{rng.randint(0, 9)}#' + rows[0]
    elif rng.random() < 0.6:
        r = rng.randrange(len(rows))
        c = rng.randint(0, len(rows[r]))
        rows[r] = rows[r][:c] + '"' + rows[r][c:]
    return "\n".join(rows)


def super_snusp_input(rng: random.Random, program: str) -> str:
    """Return decimal tokens when the program reads ``@``, else characters."""
    if "@" in program and rng.random() < 0.8:
        count = rng.choice((0, 1, 3, 6))
        return " ".join(str(rng.randint(-20, 300)) for _ in range(count))
    return ascii_input(rng, program)


#: The reference brought to our readings: with no ``"`` the IP starts on the
#: last line's last non-space character; ``,`` and ``@`` at EOF stop the run
#: (``@`` on a non-number is an error); ``.`` writes the code point as text.
SUPER_SNUSP_PATCHES = (
    ("start = (0, 0)", "start = (len(rows) - 1, len(rows[-1].rstrip()) - 1)"),
    (
        """                else:
                    tape[mp] = 0
            elif ch == "-":""",
        """                else:
                    raise Halt(4, "EOF")
            elif ch == "-":""",
    ),
    (
        "out.append(cell % 256)",
        """if not 0 <= cell <= 0x10FFFF:
                    raise Halt(3, "not a code point")
                out += chr(cell).encode("utf-8", "surrogatepass")""",
    ),
    (
        """                else:
                    tape[mp] = 0
            elif "A" <= ch""",
        """                else:
                    raise Halt(4 if ip == len(inp) else 3, "no number")
            elif "A" <= ch""",
    ),
)


def _taglate_body(rng: random.Random, depth: int = 0) -> str:
    """Return commands with balanced ``gy``/``gz`` loops, shallowly nested.

    At most one ``t``, outside the loops: each one multiplies the queue.
    """
    out = []
    for _ in range(rng.randint(1, 8 if depth else 12)):
        if depth < 2 and rng.random() < 0.15:
            out.append("gy" + _taglate_body(rng, depth + 1) + "gz")
        else:
            out.append(rng.choice("aabbccddeeeeffhiiiijjj"))
    if not depth and rng.random() < 0.3:
        out.insert(rng.randint(0, len(out)), "t")
    return "".join(out)


def taglate_program(rng: random.Random) -> str:
    """Return a seed line (ASCII, now and then a NUL or empty) and commands."""
    seed = "".join(
        rng.choice("Hello, w0rld!\x00\x01~%") for _ in range(rng.choice((0, 4, 8, 16)))
    )
    return seed + "\n" + _taglate_body(rng)


def taglate_balanced(program: str) -> bool:
    """Whether the loops pair up (ours only notices an unpaired one it jumps)."""
    body = program.partition("\n")[2].replace("gy", "[").replace("gz", "]")
    return balanced(body.replace("g", ""))


#: The reference brought to our recorded readings: an empty queue reads as
#: 0 at ``gy``/``gz``, and ``t`` writes ``%XX`` of each code unit.
TAGLATE_PATCHES = (
    ("return not q or q[0] != 0", "return bool(q) and q[0] != 0"),
    ("text = units_to_text(units)", 'text = "".join(map(chr, units))'),
    (
        'enc.extend("%%%02X" % b for b in ch.encode("utf-8"))',
        'enc.append("%%%02X" % o)',
    ),
)


#: thisthat in ASCII, since the harness hands the reference Latin-1: ours
#: translates back (``thisthat_ours``), the reference through a wrapper that
#: does the same before running ``blind/thisthat.py``.
THISTHAT_ASCII = dict(zip("SHopinyxLDldu", "▣◉◯◔◇□■▦◧⬓◨⬒◹", strict=True))
THISTHAT_ASCII |= {"v": "◺", ">": "▶", ")": "▷", "-": "─", "|": "║"}


def thisthat_program(rng: random.Random) -> str:
    """Return ``▣`` and a chain of nodes on one execution wire, in ASCII.

    Under some nodes a data wire runs down to an output ``◇``; the chain
    ends in ``◉`` or open.
    """
    nodes = [rng.choice("opiinyxLDlduv>)") for _ in range(rng.randint(1, 6))]
    chain = "-".join(["S", *nodes] + ["H"] * (rng.random() < 0.7))
    taps = [
        "|" if 2 * i + 2 < len(chain) and rng.random() < 0.5 else " "
        for i in range(len(nodes))
    ]
    under = " " + "".join(f" {tap}" for tap in taps)
    return "\n".join((chain, under, under.replace("|", "i")))


def thisthat_ours(language: str, program: str, stdin: str, max_steps: int) -> Any:
    """``ours_utf8`` on the program spelled in thisthat's own glyphs."""
    glyphs = program.translate(str.maketrans(THISTHAT_ASCII))
    return ours_utf8(language, glyphs, stdin, max_steps)


def bits_input(rng: random.Random, _program: str) -> str:
    """Return a few bits, now and then none."""
    return "".join(rng.choice("01") for _ in range(rng.choice((0, 2, 5))))


def unsquare_block(rng: random.Random, depth: int = 0) -> str:
    """Return Unsquare commands with balanced ``>``/``<`` loops.

    A loop body usually walks the accumulator down by 2 so it can end.
    """
    out = []
    for _ in range(rng.randint(1, 8)):
        roll = rng.random()
        if depth < 2 and roll < 0.12:
            body = unsquare_block(rng, depth + 1)
            out.append(">" + body + "P" * (rng.random() < 0.3) + "-<")
        else:
            out.append(rng.choice("OOIIAAS++++--xxPPPPoooi"))
    return "".join(out)


def unsquare_program(rng: random.Random) -> str:
    """Return a program, now and then the wiki's Cat or Truth-machine inside."""
    if rng.random() < 0.1:
        return rng.choice(("iA>PoiA<", "ioAx>Io<"))
    return "OI" * rng.randint(0, 2) + unsquare_block(rng)


#: The reference brought to our readings: ``o`` needs a stack top, writes it
#: as a code point (decimal when it is not one) and ``i`` at EOF stops.
UNSQUARE_PATCHES = (
    (
        """                v = stack[-1] if stack else acc
                out.append(v % 256)""",
        """                if not stack:
                    raise Halt(3, "o on empty stack")
                v = stack[-1]
                u = v & 0xFFFFFFFF
                if u <= 0x10FFFF and not 0xD800 <= u < 0xE000:
                    out += chr(u).encode("utf-8")
                else:
                    try:
                        out += str(v).encode()
                    except ValueError:
                        raise Halt(3, "too many digits to print")""",
    ),
    (
        """                else:
                    stack.append(0)""",
        """                else:
                    raise Halt(4, "EOF")""",
    ),
)


_VANDEVELO_NAMES = ("0", "1", "2", "3", "Nil", "Inp")


def _vandevelo_expr(rng: random.Random) -> str:
    """Return ``name?``, or two or three of them compared."""
    count = rng.choice((1, 1, 2, 3))
    terms = [rng.choice(_VANDEVELO_NAMES) + "?" for _ in range(count)]
    out = terms[0]
    for term in terms[1:]:
        out += rng.choice((" == ", " != ")) + term
    return out


def vandevelo_program(rng: random.Random) -> str:
    """Return lines of assignments to 0-3 and ``::`` tests; comments, blanks.

    Most names are defined up front; a target is never ``Nil``/``Inp``, and
    a ``::`` has two operands (the reference refuses a chain of them).
    """
    lines = []
    for _ in range(rng.randint(1, 6)):
        roll = rng.random()
        if roll < 0.6:
            op = rng.choice(("->", "-!>", "~>", "~!>"))
            line = f"{rng.choice('0123')} {op} {_vandevelo_expr(rng)}"
        elif roll < 0.9:
            line = f"{_vandevelo_expr(rng)} :: {_vandevelo_expr(rng)}"
        else:
            line = rng.choice(("", "-- note", "  "))
        if rng.random() < 0.1:
            line += " --c"
        lines.append(line)
    defs = "\n".join(f"{n} ~> Nil?" for n in "0123" if rng.random() < 0.7)
    return defs + "\n" + "\n".join(lines)


def vandevelo_input(rng: random.Random, _program: str) -> str:
    """Return lines that ``Inp`` reads as nil (``0``, a space, empty) or not."""
    pool = ("0", "1", " ", "", "x", "00")
    return "".join(rng.choice(pool) + "\n" for _ in range(rng.choice((3, 30))))


SPECS: dict[str, Spec] = {
    "SLOW ACV MAMMALIAN": Spec(
        "SLOW ACV MAMMALIAN",
        mammalian_program,
        ascii_input,
        ref_outcome=blind_outcome,
        split=str.split,
        join=" ".join,
        patches=MAMMALIAN_PATCHES,
    ),
    "Streetcode": Spec(
        "Streetcode",
        _streetcode_valid_program,
        ascii_input,
        max_steps=20_000,
        ref_outcome=blind_outcome,
        ours=ours_utf8,
        split=lambda program: list(program),
        blank=" ",
        valid=streetcode_valid,
        patches=STREETCODE_PATCHES,
    ),
    # Never halts by the page; ours ends a scripted run at EOF, so only the
    # output prefixes are compared (the reference's limit is ``limit``).
    "Suffolk": Spec(
        "Suffolk",
        suffolk_program,
        long_input,
        max_steps=5_000,
        ref_outcome=_harness.blind_outcome,
        ours=ours_utf8,
    ),
    "Super SNUSP": Spec(
        "Super SNUSP",
        super_snusp_program,
        super_snusp_input,
        max_steps=20_000,
        ref_outcome=blind_outcome,
        ours=ours_utf8,
        split=list,
        blank=" ",
        patches=SUPER_SNUSP_PATCHES,
    ),
    "Taglate": Spec(
        "Taglate",
        taglate_program,
        ascii_input,
        max_steps=20_000,
        ref_outcome=blind_outcome,
        ours=ours_utf8,
        valid=taglate_balanced,
        patches=TAGLATE_PATCHES,
    ),
    "thisthat": Spec(
        "thisthat",
        thisthat_program,
        bits_input,
        max_steps=2_000,
        ref_outcome=blind_outcome,
        ours=thisthat_ours,
        split=list,
        blank=" ",
    ),
    "Unsquare": Spec(
        "Unsquare",
        unsquare_program,
        long_input,
        max_steps=20_000,
        ref_outcome=blind_outcome,
        ours=ours_utf8,
        valid=lambda program: balanced(program.translate(str.maketrans("><", "[]"))),
        patches=UNSQUARE_PATCHES,
    ),
    "Vandevelo": Spec(
        "Vandevelo",
        vandevelo_program,
        vandevelo_input,
        max_steps=2_000,
        ref_outcome=blind_outcome,
        split=lambda program: program.split("\n"),
        join="\n".join,
    ),
}
