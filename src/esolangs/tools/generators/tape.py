"""Tape text generators."""

import math

__all__ = ['_ASCII_ART_BLOCKS', '_MAMMALIAN_WALK', '_MINUS_REM', '_PLUS_REM', '_mammalian_walk', '_six_five_path', 'ascii_art', 'bfstack', 'brainif', 'circlefuck', 'excon', 'mammalian', 'minifuck', 'six_five', 'suffolk']
def _six_five_path(src, dst):
    """Shortest sequence of 5/6 additions and 2/9 subtractions from src to dst.

    The delta is built from a run of sixes (or fives) plus a short remainder
    pattern, choosing whichever base yields the shorter program.
    """
    delta = dst - src
    if delta < 0:
        delta = -delta
        q6, r6 = divmod(delta, 6)
        q5, r5 = divmod(delta, 5)
        p6 = "9" * q6 + _MINUS_REM[r6]
        p5 = "2" * q5 + _MINUS_REM[r5]
        return p6 if len(p6) <= len(p5) else p5
    q6, r6 = divmod(delta, 6)
    q5, r5 = divmod(delta, 5)
    p6 = "6" * q6 + _PLUS_REM[r6]
    p5 = "5" * q5 + _PLUS_REM[r5]
    return p6 if len(p6) <= len(p5) else p5


def _mammalian_walk(ptr):
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



_PLUS_REM = ["", "62", "6622", "55599", "559", "5"]  # +5/+6 paths for remainders
_MINUS_REM = ["", "95", "9955", "999555", "262", "2"]  # -5/-6 paths

_MINUS_REM = ["", "95", "9955", "999555", "262", "2"]  # -5/-6 paths

_ASCII_ART_BLOCKS = {
    "-": "-",
    ".": "#\n#",
    "+": "|\n|\n|\n|\n|",
    "[": "_\n_\n_\n_\n_\n_",
    "]": "|\n|\n|\n|\n|\n|",
}

_MAMMALIAN_WALK: dict[int, list[dict[int, int]]] = {}

def bfstack(text):
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


def brainif(text):
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


def suffolk(text):
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


def excon(text):
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


def six_five(text):
    cur = 0
    res = []
    for c in text:
        res.append(_six_five_path(cur, ord(c)))
        res.append("A")
        cur = ord(c)
    return "".join(res)


def ascii_art(text):
    # An empty program still needs a cell; the "+" block is a no-op.
    if not text:
        return _ASCII_ART_BLOCKS["+"]
    bf = "".join("[-]" + "+" * ord(c) + "." for c in text)
    return "\n\n".join(_ASCII_ART_BLOCKS[ch] for ch in bf)


def minifuck(text):
    if "\x00" in text:
        raise ValueError("Minifuck cannot output the NUL character")
    res = []
    tape = [0] * 8
    ptr = 0

    def ensure(index):
        while len(tape) <= index:
            tape.append(0)

    def flip(position):
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


def circlefuck(text):
    """Generate a CircleFuck program that outputs ``text``.

    CircleFuck's tape is the program itself, so each cell starts out holding
    the character code of whatever instruction occupies that position. The
    generator walks a single data pointer across the cells, emitting the
    ``+``/``-`` run needed to reach each target value (reading the current
    cell's base off the program text built so far), then ``.`` to print and
    ``>`` to advance, ending with ``@``.
    """
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


def mammalian(text):
    """A SEED/SPRINT walk that reaches the array whose value is the character.

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


