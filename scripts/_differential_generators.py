"""Deterministic random program constructors for differential campaigns."""

import random

# --- brainfuck ------------------------------------------------------------

_BF_IDIOMS = ("[-]", "[+]", "[>+<-]", "[>++<-]", "[>-<-]", "[<+>-]")


def bf_block(rng: random.Random, depth: int = 0) -> str:
    """Return a Brainfuck block; inside a loop it returns the pointer home.

    A loop body that ends where it began and decrements its own cell halts
    unless an inner loop resets that cell, so most programs halt.
    """
    parts: list[str] = []
    offset = 0
    for _ in range(rng.randint(1, 8 - 2 * depth)):
        roll = rng.random()
        if roll < 0.3:
            parts.append(rng.choice("+-") * rng.randint(1, 4))
        elif roll < 0.5:
            step = rng.choice((-1, 1)) * rng.randint(1, 3)
            parts.append((">" if step > 0 else "<") * abs(step))
            offset += step
        elif roll < 0.62:
            parts.append(".")
        elif roll < 0.72:
            parts.append(",")
        elif roll < 0.88 and depth < 3:
            parts.append("[" + bf_block(rng, depth + 1) + "-]")
        else:
            parts.append(rng.choice(_BF_IDIOMS))
    if depth:
        parts.append(("<" if offset > 0 else ">") * abs(offset))
    return "".join(parts)


def bf_program(rng: random.Random) -> str:
    """Return a balanced program: mostly structured, sometimes free-form."""
    if rng.random() < 0.85:
        return bf_block(rng)
    out, depth = [], 0
    for _ in range(rng.randint(1, 30)):
        char = rng.choice("+-<>.,[]" if depth else "+-<>.,[")
        depth += {"[": 1, "]": -1}.get(char, 0)
        out.append(char)
    return "".join(out) + "]" * depth


def balanced(program: str) -> bool:
    """Whether every bracket in ``program`` has a partner."""
    depth = 0
    for char in program:
        depth += {"[": 1, "]": -1}.get(char, 0)
        if depth < 0:
            return False
    return depth == 0


def ascii_input(rng: random.Random, _program: str) -> str:
    """Return a short ASCII input; often empty, to hit EOF."""
    pool = "abcxyz019 \n\x00\x01\x7f"
    return "".join(rng.choice(pool) for _ in range(rng.choice((0, 0, 1, 2, 3, 6))))


# --- Befunge-93 -----------------------------------------------------------

_BEF_CELLS = (
    "0123456789" * 3
    + "+-*/%!`"
    + "><^v_|" * 2
    + ":\\$" * 2
    + ".,.,"
    + "#gp&~"
    + '"@@  '
)
#: Edge idioms for a one-line run: a byte above 127 stored and read back,
#: ``g``/``p`` off the grid and at its far corner, zero divisors, signed
#: division, a near-overflow product, and reads.
_BEF_IDIOMS = (
    "99*3*00p00g.",
    "99*3*00p00g,",
    "01-0g.",
    "501-p",
    "98*7+0g.",
    "0/.",
    "0%.",
    "07-2/.",
    "07-2%.",
    "99*:*:*:*:*:*.",
    "&.",
    "~.",
)


def befunge_program(rng: random.Random) -> str:
    """Return a grid within 80x25: a one-line run or a small random grid.

    No ``?``: the two sides draw differently.  A cell at column 79 or row 24
    now and then puts the far edge in play; small grids wrap the torus fast.
    """
    if rng.random() < 0.5:
        line = _BEF_CELLS.translate({ord(c): None for c in "^v|"})
        cells = [rng.choice(line) for _ in range(rng.randint(2, 24))]
        for _ in range(rng.choice((0, 1, 1, 2))):
            cells.insert(rng.randrange(len(cells) + 1), rng.choice(_BEF_IDIOMS))
        if rng.random() < 0.3:
            cells.insert(
                rng.randrange(len(cells)),
                '"' + "".join(rng.choice("ab 0~") for _ in range(3)) + '"',
            )
        rows = ["".join(cells) + "@"]
    else:
        width, height = rng.randint(2, 10), rng.randint(1, 5)
        rows = [
            "".join(rng.choice(_BEF_CELLS + "@@@") for _ in range(width))
            for _ in range(height)
        ]
    if rng.random() < 0.1:
        rows[0] = rows[0].ljust(79) + rng.choice(_BEF_CELLS.strip())
    if rng.random() < 0.1:
        rows += [""] * (24 - len(rows)) + [rng.choice("<>^v.@")]
    return "\n".join(row.rstrip() for row in rows)


def befunge_input(rng: random.Random, _program: str) -> str:
    """Return integer tokens and characters, often empty to hit EOF."""
    tokens = [
        str(rng.randint(-20, 300)) if rng.random() < 0.7 else rng.choice("ab\n")
        for _ in range(rng.choice((0, 0, 1, 2, 4)))
    ]
    return " ".join(tokens)


def befunge_join(tokens: list[str]) -> str:
    """Rebuild a grid, trimming the padding a shrink leaves behind."""
    rows = [row.rstrip() for row in "".join(tokens).split("\n")]
    while len(rows) > 1 and not rows[-1]:
        rows.pop()
    return "\n".join(rows)


# --- Subleq ---------------------------------------------------------------


def subleq_program(rng: random.Random) -> str:
    """Return triples: arithmetic, ``a -1 c`` output and ``-1 b c`` input.

    Jumps go next, anywhere, negative (halt) or past the end (halt);
    operands sometimes point past loaded memory or at -2 (an error), and the
    last triple is sometimes cut short.
    """
    count = rng.randint(1, 6)
    size = 3 * count + rng.randint(0, 5)

    def address() -> int:
        roll = rng.random()
        return (
            rng.randrange(size)
            if roll < 0.9
            else (-2 if roll < 0.92 else size + rng.randint(0, 3))
        )

    cells: list[int] = []
    for pc in range(0, 3 * count, 3):
        roll = rng.random()
        a, b = (
            (-1, address())
            if roll < 0.12
            else (address(), -1)
            if roll < 0.32
            else (address(), address())
        )
        if rng.random() < 0.01:
            a = b = -1
        jump = rng.random()
        c = (
            pc + 3
            if jump < 0.4
            else 3 * rng.randrange(count)
            if jump < 0.65
            else rng.randrange(size)
            if jump < 0.75
            else -rng.randint(1, 3)
            if jump < 0.9
            else size + rng.randint(0, 3)
        )
        cells += [a, b, c]
    cells += [rng.randint(-3, 120) for _ in range(size - len(cells))]
    if rng.random() < 0.05:
        cells = cells[: 3 * (count - 1) + rng.randint(1, 2)]
    return " ".join(map(str, cells))


# --- Deadfish -------------------------------------------------------------


def deadfish_program(rng: random.Random) -> str:
    """Return ``idso`` with rare ``h`` and junk, at most six squarings."""
    out: list[str] = []
    squares = 0
    for _ in range(rng.randint(1, 40)):
        char = rng.choice(
            "iiiiiddds"
            + "oooo"
            + ("h" if rng.random() < 0.05 else "i")
            + ("x " if rng.random() < 0.1 else "i")
        )
        if char == "s":
            squares += 1
            if squares > 6:
                char = "o"
        out.append(char)
    return "".join(out)
