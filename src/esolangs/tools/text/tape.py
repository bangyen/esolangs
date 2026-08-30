"""Tape text generators."""

import math

from esolangs.tools.text.helpers import (
    _factor_triple,
    _require_ascii,
    _require_bytes,
    delta_program,
    run_step,
)
from esolangs.tools.wrap import shortest

__all__ = [
    "_MAMMALIAN_WALK",
    "_mammalian_walk",
    "_six_five_path",
    "bfstack",
    "brainfuck",
    "brainif",
    "circlefuck",
    "factor",
    "minifuck",
    "rotfuck",
    "six_five",
    "slow_acv_mammalian",
    "suffolk",
    "three_d_brainfuck",
]


def _six_five_path(src: int, dst: int) -> str:
    """Sequence of 6/2 additions and 9/5 subtractions from src to dst.

    The delta is covered by a run of sixes (moving up) or nines (moving down)
    plus ``62``/``95`` pairs for the remainder: each ``62`` nets ``+6 - 5 =
    +1`` and each ``95`` nets ``-6 + 5 = -1``.
    """
    delta = dst - src
    if delta >= 0:
        q, r = divmod(delta, 6)
        return "6" * q + "62" * r
    q, r = divmod(-delta, 6)
    return "9" * q + "95" * r


def _mammalian_walk(ptr: int) -> list[dict[int, int]]:
    """SPRINT paths from ``ptr`` for every possible SEED count mod 256.

    SEED gives array ``i`` the first value ``(i + 1) * K``, so a SPRINT from
    array ``q`` jumps the pointer to ``(q + (q + 1) * K) % 23``.  Each entry
    maps a SEED count to the arrays it visits and the step each is first hit.
    """
    if ptr not in _MAMMALIAN_WALK:
        paths = []
        for k in range(256):
            q = ptr
            seen = {}
            for step in range(1, 47):
                q = (q + ((q + 1) * k) % 256) % 23
                if q not in seen:
                    seen[q] = step
            paths.append(seen)
        _MAMMALIAN_WALK[ptr] = paths
    return _MAMMALIAN_WALK[ptr]


_MAMMALIAN_WALK: dict[int, list[dict[int, int]]] = {}


def _bf_set(value: int) -> str:
    """Brainfuck that sets the next cell to ``value`` and prints it.

    The current cell is assumed to be zero.  A run of ``a`` plus signs makes
    it ``a``, a loop moves that many copies of ``b`` into the next cell, and
    a final run tops the product up to ``value`` with the remainder ``r``;
    the pointer is left on the printed cell.  ``a`` is searched near
    ``sqrt(value)`` so the program is O(sqrt) rather than O(value).
    """
    a, b, r = _factor_triple(value)
    return "+" * a + "[>" + "+" * b + "<-]" + ">" + "+" * r + "."


def brainfuck(text: str) -> str:
    """Generate a brainfuck program that outputs ``text``.

    The pointer walks right one cell per character.  A cell is reused when
    the next character is close enough that its delta is shorter than
    rebuilding it: the program emits the +/- run and prints in place.
    Otherwise the cell is zeroed with ``[-]`` and rebuilt with a multiply
    loop (``_bf_set``), so large values cost O(sqrt) instead of O(value).

    The choice is made by :func:`shortest` over the two finished candidates
    rather than by comparing their costs, because a cost comparison has to
    restate each shape's length and then drift from it: this used to read
    ``len(inc) + 1 <= len(_bf_set(v)) + 3``, where the ``+ 1`` and ``+ 3``
    were the print and the ``[-]`` counted a second time, by hand.  The walk
    is passed first, so a tie keeps it -- 453 of the 65536 (previous, next)
    byte pairs are exact ties, so which side wins one is not academic.
    """
    _require_bytes(text, "Brainfuck")
    res: list[str] = []
    cur = 0
    for c in text:
        v = ord(c)
        delta = v - cur
        inc = "+" * delta if delta >= 0 else "-" * -delta
        res.append(shortest(inc + ".", "[-]" + _bf_set(v)))
        cur = v
    return "".join(res)


def rotfuck(text: str) -> str:
    """Generate a ROTfuck program that outputs ``text``.

    After ``i`` commands the character at source position ``i`` has been
    rotated ``i`` steps, so a straight-line program is just a sequence of
    *effective* commands: the raw character for position ``i`` is the
    ``i``-fold inverse rotation of the desired command.  The generated
    program keeps one cell and drives it in place from one character's code
    to the next (the shorter way around the 8-bit wrap), printing with ``.``
    and halting at the end of the source.
    """
    _require_bytes(text, "ROTfuck")
    chain = "+-><,.[]"
    commands: list[str] = []
    cur = 0
    for char in text:
        target = ord(char)
        delta = (target - cur) % 256
        if delta and delta <= 128:
            commands.extend("+" * delta)
        elif delta:
            commands.extend("-" * (256 - delta))
        commands.append(".")
        cur = target

    res: list[str] = []
    for i, command in enumerate(commands):
        back = i % 8
        res.append(chain[(chain.index(command) - back) % 8])
    return "".join(res)


_BF_RESIDUE = {">": 1, "<": 2, "+": 3, "-": 4, ".": 5, ",": 6, "[": 7, "]": 8}


def _factor_encode(code: str) -> int:
    """Encode a brainfuck program as the Factor integer for it.

    The decoder sorts the prime factors ascending, so the encoder walks
    primes upward and hands each instruction the next prime with the right
    residue modulo 11 (Dirichlet's theorem guarantees one always exists).  A
    run of identical instructions is folded into one prime's exponent, which
    keeps the integer small while decoding to the same run.
    """
    from sympy import isprime

    number = 1
    candidate = 2
    i = 0
    while i < len(code):
        residue = _BF_RESIDUE[code[i]]
        j = i
        while j < len(code) and code[j] == code[i]:
            j += 1
        prime = candidate
        while not (prime % 11 == residue and isprime(prime)):
            prime += 1
        number *= prime ** (j - i)
        candidate = prime + 1
        i = j
    return number


def factor(text: str) -> str:
    """Generate a Factor program that outputs ``text``.

    A Factor program is a single integer, so the output is the decimal form
    of the integer whose prime factorization encodes a brainfuck program
    (from :func:`bf`) that prints ``text``.
    """
    _require_bytes(text, "Factor")
    return str(_factor_encode(brainfuck(text)))


def three_d_brainfuck(text: str) -> str:
    """Build a 3D Brainfuck program that outputs ``text``.

    The memory array is three-dimensional, so the brainfuck tape moves
    ``>``/``<`` map to ``n``/``s`` along the +X axis of the array and the
    rest of the program is the brainfuck generator's unchanged.  The program
    runs along a single axis of the 3D array, keeping 3D Brainfuck a
    faithful brainfuck superset.
    """
    _require_bytes(text, "3D Brainfuck")
    return brainfuck(text).replace(">", "n").replace("<", "s")


def bfstack(text: str) -> str:
    """Build a BFStack program that outputs ``text``.

    The top of the stack is driven from the previous character's value; a
    small delta uses ``+``/``-`` and a large one zeroes the cell with
    ``[-]`` and builds the code from scratch, printing each with ``.``.

    As in :func:`brainfuck`, the two shapes are built and the shorter kept.
    **The rebuild is passed first here**, because this generator breaks a
    tie the other way: its threshold was ``abs(n) < ord(c) + 3`` -- strict,
    where brainfuck's was ``<=`` -- so an equal-length pair rebuilt rather
    than walked.  127 of the 65536 byte pairs tie, so preserving the
    direction is what keeps the emitted program byte-identical.
    """
    _require_bytes(text, "BFStack")
    res = ">"
    acc = 0

    for c in text:
        n = ord(c) - acc
        o = "+" if n > 0 else "-"
        res += shortest("[-]" + "+" * ord(c) + ".", o * abs(n) + ".")
        acc = ord(c)

    return res


def brainif(text: str) -> str:
    """Build a BrainIf program that outputs ``text``.

    A cell only ever counts up -- ``if <k> increment`` fires while the cell
    holds ``k``, and there is no decrement -- so a character below the
    running value has to be built somewhere else.  The tape is what makes
    that cheap: a cell keeps its value after the pointer leaves, so every
    character already printed is still parked where it was built, and
    ``move left``/``move right`` walk back to it.

    So a falling character starts from the largest parked value not above
    it and climbs the difference, taking a fresh zero cell only when that
    is actually cheaper (the walk costs a line per step).  Climbing from
    ``0`` every time, as this used to, re-pays the whole ascent: the ``l``
    of ``Hello, World!`` costs 110 lines from zero against 66 from the
    parked ``44`` of the comma.
    """
    lines: list[str] = []
    cells = [0]  # every cell's value; the pointer's own cell included
    ptr = 0

    def walk(target: int) -> None:
        """Step the pointer to ``target``, guarding each move by its cell."""
        nonlocal ptr
        while ptr != target:
            step = 1 if target > ptr else -1
            way = "right" if step > 0 else "left"
            lines.append(f"if {cells[ptr]} move {way}")
            ptr += step
            # The caller only ever walks to a cell it has already allocated
            # or to the one immediately past the end, and the fresh-cell
            # targets are appended before the walk starts.
            if ptr == len(cells):
                cells.append(0)  # pragma: no cover - the target is parked

    for c in text:
        n = ord(c)
        # The cheapest cell to build ``n`` in: the climb from its current
        # value plus the walk to reach it.  A cell above ``n`` cannot be
        # used at all, since a cell never counts down.
        usable = [i for i, v in enumerate(cells) if v <= n]
        best = min(usable, key=lambda i: (n - cells[i]) + abs(i - ptr), default=None)
        # A fresh cell past the end is always available, and is worth taking
        # when the walk to the best parked cell costs more than the climb it
        # saves -- or when every cell is already above ``n``.
        fresh = len(cells)
        if best is None or n + abs(fresh - ptr) < (n - cells[best]) + abs(best - ptr):
            cells.append(0)
            best = fresh

        walk(best)
        for k in range(cells[ptr], n):
            lines.append(f"if {k} increment")
        cells[ptr] = n
        lines.append(f"if {n} output")

    return "\n".join(lines)


def suffolk(text: str) -> str:
    """Build a Suffolk program that outputs ``text``.

    Each character is factored as ``n = a * b + r``; ``!`` computes
    ``max(0, cell + 1 - acc)`` so the multiplier ``a`` is built into a helper
    cell and the remainder ``r`` is added by repeated ``>!`` moves, then ``.``
    prints.  The ``>!`` and ``><`` moves cost two characters each, so ``a``
    is searched over the factorization that minimizes ``a + 2b + 2r`` rather
    than fixed at ``sqrt(n)``.  Cell 2 is sized so ``!`` zeroes the working
    cells and they can be reused per character.
    """
    if not text:
        return ""
    # Cell 2 is a persistent helper large enough that ``!`` (which computes
    # max(0, cell + 1 - acc)) zeroes cells 0 and 1, so they can be reused.
    big = max(int((ord(c) + 1) ** 0.5) for c in text) + 2
    res = []
    for c in text:
        n = ord(c) + 1
        best = min(
            (a + 2 * b + 2 * r, a, b, r)
            for a in range(1, n + 1)
            for b, r in (divmod(n, a),)
        )
        _, a, b, r = best
        res.append(f">><!>><>!{'!' * a}{'>!' * r}><{'<' * b}.")
    return ">>!" * big + "".join(res)


def six_five(text: str) -> str:
    """Build a 6-5 program that outputs ``text``.

    Each character is reached from the previous one by a ``_six_five_path``
    of arithmetic tokens that moves the cell from ``cur`` to ``ord(c)``,
    followed by ``A`` to print it.
    """
    return delta_program(text, _six_five_path, "A")


def minifuck(text: str) -> str:
    """Build a Minifuck program that outputs ``text``.

    The 8-bit pool is kept in the tape and the pointer is tracked so that
    ``[x`` toggles drive the bits toward the next character.  The pool is
    printed with ``.`` only when it holds a nonzero byte (a zero pool would
    be read as input), and the NUL character cannot be emitted at all.
    """
    _require_ascii(text, "Minifuck")
    if "\x00" in text:
        raise ValueError("Minifuck cannot output the NUL character")
    res = []
    tape = [0] * 8
    ptr = 0

    def ensure(index: int) -> None:
        while len(tape) <= index:
            tape.append(0)

    def flip(position: int) -> None:
        nonlocal ptr
        ptr = position + 1
        ensure(ptr + 1)
        tape[ptr] ^= 1
        if not tape[ptr]:
            ensure(ptr + 2)
            tape[ptr + 1] ^= 1

    for c in text:
        bits = [int(b) for b in f"{ord(c):07b}"]
        first = next((k for k in range(1, 8) if tape[k] != bits[k - 1]), None)
        if first is None:
            res.append(".")
            ptr += 1
            ensure(ptr)
            tape[ptr] ^= 1
            continue
        if ptr > first - 1:
            res.append("<" * (ptr - (first - 1)))
            ptr = first - 1
        for k in range(ptr + 1 if ptr < first - 1 else first, 8):
            res.append("[x")
            flip(k - 1)
            if tape[k] != bits[k - 1]:
                res.append("<")
                ptr -= 1
                res.append("[x")
                flip(k - 1)
        res.append(".")
        ptr += 1
        ensure(ptr)
        tape[ptr] ^= 1

    return "".join(res)


# Circlefuck command characters (everything else is a harmless no-op cell).
_CF_COMMANDS = frozenset("+-<>[],.@#{}")


def circlefuck(text: str) -> str:
    """Generate a Circlefuck program that outputs ``text``.

    Circlefuck's tape is the program itself, so a cell starts out holding the
    character code of whatever instruction occupies its position.  The
    generator keeps the data pointer on a single cell: a no-op character near
    the first target's code seeds it, and ``+``/``-`` runs placed later in the
    program drive the cell in place from one character's value to the next,
    ``.`` printing each and ``@`` halting.  Each character therefore costs
    only its delta from the previous one rather than a fresh-cell rebuild
    from its instruction code.
    """
    _require_bytes(text, "Circlefuck")
    if not text:
        return "@"
    base = min(
        (
            chr(i)
            for i in range(33, 127)
            if chr(i) not in _CF_COMMANDS and chr(i) != "\\"
        ),
        key=lambda c: abs(ord(c) - ord(text[0])),
    )
    return delta_program(
        text,
        run_step("+", "-"),
        ".",
        start=ord(base),
        prologue=base,
        epilogue="@",
    )


def slow_acv_mammalian(text: str) -> str:
    """Build a SEED/SPRINT walk that reaches the array whose value is the character.

    SEED once so every array's first value is ``(i + 1) * K`` for the running
    SEED count K, letting SPRINT move.  For each character, a run of SEEDs is
    split around the SPRINT walk: the first count is chosen so the walk lands
    on a usable array, the final count so that DIGEST there equals the
    character.  EXCRETE stores the value (an "extra") and clears the
    accumulator for the next character.

    A construction always exists: an even array ``q`` has ``gcd(q+1, 256) == 1``,
    so the value equation ``(q+1) * K == target (mod 256)`` is always solvable,
    and the SPRINT walk from any pointer reaches some even array under some
    SEED count.  The scan below was verified exhaustively over every
    (pointer, SEED count, character) state with no extras, plus random states
    with extras, without ever failing.
    """
    _require_bytes(text, "SLOW ACV MAMMALIAN")
    if not text:
        return ""
    k = 1
    ptr = 0
    extras: list[list[int]] = [[] for _ in range(23)]
    prog = ["SEED"]

    for c in text:
        t = ord(c)
        walks = _mammalian_walk(ptr)
        best = (float("inf"), 0, 0, 0)

        for q in range(23):
            target = (t - sum(extras[q])) % 256
            g = math.gcd(q + 1, 256)
            if target % g:
                continue
            base = (target // g) * pow((q + 1) // g, -1, 256 // g) % (256 // g)
            for lift in range(g):
                final = base + lift * (256 // g)
                seeds = (final - k) % 256
                for mid in range(seeds + 1):
                    mid_k = (k + mid) % 256
                    if q in walks[mid_k]:
                        steps = walks[mid_k][q]
                        if seeds + steps < best[0]:
                            best = (seeds + steps, mid_k, final, steps)
                        break

        if best[0] == float("inf"):
            raise ValueError(f"mammalian: cannot build {c!r}")
        _, mid_k, final, steps = best
        dk = (mid_k - k) % 256
        d = (final - mid_k) % 256
        prog += (
            ["SEED"] * dk
            + ["SPRINT"] * steps
            + ["SEED"] * d
            + [
                "DIGEST",
                "PRONOUNCE",
                "EXCRETE",
            ]
        )
        k += dk + d
        for _ in range(steps):
            ptr = (ptr + ((ptr + 1) * mid_k) % 256) % 23
        extras[ptr].append(t % 256)

    return " ".join(prog)
