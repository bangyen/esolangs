"""Tape text generators."""

import math

from esolangs.tools.generators.helpers import _require_ascii, _require_bytes
from esolangs.tools.transpilers import bf_to_ascii_art

__all__ = [
    "_MAMMALIAN_WALK",
    "_mammalian_walk",
    "_six_five_path",
    "ascii_art",
    "bf",
    "bfstack",
    "brainif",
    "circlefuck",
    "excon",
    "factor",
    "mammalian",
    "minifuck",
    "rotfuck",
    "six_five",
    "suffolk",
    "three_d_bf",
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
    best = min(
        (
            (a + b + r, a, b, r)
            for a in range(1, int(value**0.5) + 2)
            for b, r in (divmod(value, a),)
        ),
    )
    _, a, b, r = best
    return "+" * a + "[>" + "+" * b + "<-]" + ">" + "+" * r + "."


def bf(text: str) -> str:
    """Generate a brainfuck program that outputs ``text``.

    The pointer walks right one cell per character.  A cell is reused when
    the next character is close enough that its delta is shorter than
    rebuilding it: the program emits the +/- run and prints in place.
    Otherwise the cell is zeroed with ``[-]`` and rebuilt with a multiply
    loop (``_bf_set``), so large values cost O(sqrt) instead of O(value).
    """
    _require_bytes(text, "Brainfuck")
    res: list[str] = []
    cur = 0
    for c in text:
        v = ord(c)
        delta = v - cur
        inc = "+" * delta if delta >= 0 else "-" * -delta
        if len(inc) + 1 <= len(_bf_set(v)) + 3:
            res.append(inc + ".")
            cur = v
        else:
            res.append("[-]" + _bf_set(v))
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
    return str(_factor_encode(bf(text)))


def ascii_art(text: str) -> str:
    """Generate an ASCII-art program that outputs ``text``.

    ASCII art is brainfuck with an art alphabet, so the program is exactly
    the brainfuck program for ``text`` rendered as art blocks.
    """
    _require_bytes(text, "ASCII art")
    return bf_to_ascii_art(bf(text))


def three_d_bf(text: str) -> str:
    """Build a 3D Brainfuck program that outputs ``text``.

    The memory array is three-dimensional, so the brainfuck tape moves
    ``>``/``<`` map to ``n``/``s`` along the +X axis of the array and the
    rest of the program is the brainfuck generator's unchanged.  The program
    runs along a single axis of the 3D array, keeping 3D Brainfuck a
    faithful brainfuck superset.
    """
    _require_bytes(text, "3D Brainfuck")
    return bf(text).replace(">", "n").replace("<", "s")


def bfstack(text: str) -> str:
    """Build a BFStack program that outputs ``text``.

    The top of the stack is driven from the previous character's value; a
    small delta uses ``+``/``-`` and a large one zeroes the cell with
    ``[-]`` and builds the code from scratch, printing each with ``.``.
    """
    _require_bytes(text, "BFStack")
    res = ">\n"
    acc = 0

    for c in text:
        n = ord(c) - acc
        if abs(n) < ord(c) + 3:
            o = "+" if n > 0 else "-"
            res += o * abs(n) + ".\n"
        else:
            o = "+" * ord(c)
            res += f"[-]{o}.\n"
        acc = ord(c)

    return res


def brainif(text: str) -> str:
    """Build a BrainIf program that outputs ``text``.

    Each character is built by incrementing the cell from the previous
    character's value to the new one, guarded by ``if <k> increment`` lines
    that run only while the cell equals ``k``; a decreasing value first moves
    right to a fresh cell.  ``if <n> output`` prints the character.
    """
    res = ""
    acc = 0

    for c in text:
        if (n := ord(c)) < acc:
            res += f"\nif {acc} move right\n"
            for k in range(n):
                res += f"if {k} increment\n"
            res += f"if {n} output\n"
        else:
            res += "\n"
            for k in range(acc, n):
                res += f"if {k} increment\n"
            res += f"if {n} output\n"
        acc = ord(c)

    return res.strip()


def suffolk(text: str) -> str:
    """Build a Suffolk program that outputs ``text``.

    Each character is factored as ``n = a * b + r`` with ``a`` near
    ``sqrt(n)``; ``!`` computes ``max(0, cell + 1 - acc)`` so the multiplier
    ``a`` is built into a helper cell and the remainder ``r`` is added by
    repeated ``>!`` moves, then ``.`` prints.  Cell 2 is sized so ``!``
    zeroes the working cells and they can be reused per character.
    """
    if not text:
        return ""
    # Cell 2 is a persistent helper large enough that ``!`` (which computes
    # max(0, cell + 1 - acc)) zeroes cells 0 and 1, so they can be reused.
    big = max(int((ord(c) + 1) ** 0.5) for c in text) + 2
    res = []
    for c in text:
        n = ord(c) + 1
        a = max(1, int(n**0.5))
        b, r = divmod(n, a)
        res.append(f">><!>><>!{'!' * a}{'>!' * r}><{'<' * b}.")
    return ">>!" * big + "\n" + "\n".join(res)


def excon(text: str) -> str:
    """Build an EXCON program that outputs ``text``.

    For each character, ``:`` resets the 8-cell pool, ``^`` flips the bits
    that are 1 in the character's binary representation (moving left to the
    next set bit with ``<``), and ``!`` prints the pool as a byte.
    """
    _require_bytes(text, "EXCON")
    res = ""

    for c in text:
        bits = format(ord(c), "08b")
        res += ":"
        pos = 7
        for j in range(7, -1, -1):
            if bits[j] == "1":
                res += "<" * (pos - j) + "^"
                pos = j
        res += "!"

    return res


def six_five(text: str) -> str:
    """Build a 6-5 program that outputs ``text``.

    Each character is reached from the previous one by a ``_six_five_path``
    of arithmetic tokens that moves the cell from ``cur`` to ``ord(c)``,
    followed by ``A`` to print it.
    """
    cur = 0
    res = []
    for c in text:
        res.append(_six_five_path(cur, ord(c)))
        res.append("A")
        cur = ord(c)
    return "".join(res)


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


def circlefuck(text: str) -> str:
    """Generate a CircleFuck program that outputs ``text``.

    CircleFuck's tape is the program itself, so each cell starts out holding
    the character code of whatever instruction occupies that position. The
    generator walks a single data pointer across the cells, emitting the
    ``+``/``-`` run needed to reach each target value (reading the current
    cell's base off the program text built so far), then ``.`` to print and
    ``>`` to advance, ending with ``@``.
    """
    _require_bytes(text, "CircleFuck")
    if not text:
        return "@"
    prog: list[str] = []
    for i, c in enumerate(text):
        target = ord(c)
        if i == 0:
            if target >= 44:
                run = "+" * (target - 43)
            elif target == 43:
                run = "+-"
            else:
                run = "-" * (45 - target)
        else:
            delta = (target - ord(prog[i])) % 256
            if delta == 0:
                run = ""
            elif delta <= 128:
                run = "+" * delta
            else:
                run = "-" * (256 - delta)
        prog.extend(run)
        prog.append(".")
        if i != len(text) - 1:
            prog.append(">")
    prog.append("@")
    return "".join(prog)


def mammalian(text: str) -> str:
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
    _require_bytes(text, "MAMMALIAN")
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

    return "\n".join(prog)
