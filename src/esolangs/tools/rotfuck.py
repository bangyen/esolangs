"""Boolean-function generator for ROTFuck.

Every command is written rotated by its own position, so the generator
builds the program in plain Brainfuck and rotates each character into place
at the end (:func:`_rotfuck_rot`).  The helpers pick, for each tape offset,
a command spelling that survives its rotation
(:func:`_rotfuck_allowed`, :func:`_rotfuck_neutral`).
"""

from functools import cache

from esolangs.tools.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    essential_inputs,
    read_at,
)

__all__ = ["rotfuck"]

# The eight-step rotation cycle: + -> - -> > -> < -> , -> . -> [ -> ] -> +.
_ROTFUCK_CHAIN = "+-><,.[]"


def _rotfuck_rot(char: str, steps: int) -> str:
    """Advance ``char`` ``steps`` steps along the ROTfuck rotation cycle."""
    index = _ROTFUCK_CHAIN.index(char)
    return _ROTFUCK_CHAIN[(index + steps) % 8]


def _rotfuck_allowed(offset: int) -> list[str]:
    """Commands a body may place at relative offset ``offset``.

    At the ``[``-fire seek state ``p + 1``, a body command at relative offset
    ``j`` shows ``rot^{-j}(cmd)``, which must not be a bracket (else the
    seek's depth count changes).  So ``cmd`` must not be ``rot^{j}`` of a
    bracket.
    """
    bad = {_rotfuck_rot("[", offset), _rotfuck_rot("]", offset)}
    return [c for c in "+-><" if c not in bad]


def _rotfuck_neutral(offset: int) -> str:
    """Return a two-char net-neutral pair usable at ``offset``.

    The pair is ``+-``/``-+`` or ``><``/``<>``, both of whose characters are
    allowed at ``offset`` and ``offset + 1``.
    """
    for pair in ("+-", "-+", "><", "<>"):
        if all(c in _rotfuck_allowed(offset + i) for i, c in enumerate(pair)):
            return pair
    raise ValueError(  # pragma: no cover - a neutral pair exists at every offset
        "ROTfuck body padding is impossible at this offset"
    )


@cache
def _rotfuck_move_cycle(state: int, direction: str) -> tuple[tuple[str, ...], int, str]:
    """Tile the move pattern from offset state ``state`` (mod 8).

    A move's emission depends only on the offset mod 8: an allowed offset
    emits the direction (offset + 1), a forbidden one a neutral pair first
    (offset + 2).  The per-move texts are therefore eventually periodic in
    the move count.  Returns the texts up to the first repeated state, the
    index where the cycle starts, and the cycle joined.
    """
    texts: list[str] = []
    seen = {state: 0}
    while True:
        pads: list[str] = []
        while direction not in _rotfuck_allowed(state):
            pads.append(_rotfuck_neutral(state))
            state = (state + 2) % 8
        texts.append("".join(pads) + direction)
        state = (state + 1) % 8
        if state in seen:
            start = seen[state]
            return tuple(texts), start, "".join(texts[start:])
        seen[state] = len(texts)


def _rotfuck_move(ptr: int, goal: int, offset: int, direction: str) -> str:
    """Emit ``>``/``<`` to move ``ptr`` toward ``goal``.

    The direction command is forbidden at some offsets, so a net-neutral
    padding pair is inserted there to shift past them while every command
    stays at an allowed offset.
    """
    dist = goal - ptr if direction == ">" else ptr - goal
    texts, start, cycle = _rotfuck_move_cycle(offset % 8, direction)
    if dist <= len(texts):
        return "".join(texts[:dist])
    reps, rem = divmod(dist - start, len(texts) - start)
    return "".join(texts[:start]) + cycle * reps + "".join(texts[start : start + rem])


@cache
def _rotfuck_body_for(delta: int, op: str) -> str:
    """Build the body for a guard-relative target at offset ``delta``."""
    out: list[str] = []
    offset = 0
    ptr = 0
    if delta > 0:
        out.append(_rotfuck_move(ptr, delta, offset, ">"))
        offset += len(out[-1])
        ptr = delta
    else:
        out.append(_rotfuck_move(ptr, delta, offset, "<"))
        offset += len(out[-1])
        ptr = delta
    if op not in _rotfuck_allowed(offset % 8):
        pad = _rotfuck_neutral(offset % 8)
        out.append(pad)
        offset += 2
        if op not in _rotfuck_allowed(offset % 8):
            # padding always shifts a +/- op off both its forbidden offsets
            raise ValueError(
                "ROTfuck body op lands on a forbidden offset"
            )  # pragma: no cover
    out.append(op)
    offset += 1
    if delta < 0:
        out.append(_rotfuck_move(ptr, 0, offset, ">"))
    else:
        out.append(_rotfuck_move(ptr, 0, offset, "<"))
    offset += len(out[-1])
    body = "".join(out)
    need = (8 - (len(body) + 1) % 8) % 8
    while need:
        pad = _rotfuck_neutral(offset % 8)
        body += pad
        offset += 2
        need -= 2
    return body


def _rotfuck_body(guard: int, target: int, op: str) -> str:
    """Build a body that moves the pointer from ``guard`` to ``target``.

    The body applies ``op`` to the target cell and returns to ``guard``.  It
    is straight-line ``+-><`` only, has length ``L`` with
    ``L + 1 ≡ 0 (mod 8)``, and every command sits at an allowed offset.  The
    tested cell (``guard``) stays nonzero, so the phantom ``[`` at the block
    end does not fire on the body path.  Only the offset ``target - guard``
    matters, so the builder is cached on it.
    """
    return _rotfuck_body_for(target - guard, op)


# Rotating the finished program: the char at absolute position ``i`` becomes
# ``rot^{-i}`` of itself, so one translation table per residue class mod 8.
_ROT_TABLES = tuple(
    bytes.maketrans(
        _ROTFUCK_CHAIN.encode(),
        "".join(_rotfuck_rot(c, -res) for c in _ROTFUCK_CHAIN).encode(),
    )
    for res in range(8)
)
_PHANTOM = tuple(ord(_rotfuck_rot("]", -res)) for res in range(8))


def rotfuck(truth_table: str) -> str:
    """Build a ROTfuck program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    ROTfuck rotates the program after every command, which defeats the
    brainfuck decision-tree strategy (a firing bracket seeks its partner in
    the rotated program).  The generator instead lays out one ``[ body ]``
    block per guard, where the body is a straight-line ``+-><`` walk that
    moves the pointer from the tested cell to a target, applies one
    ``+``/``-``, and returns.  The closing ``]`` is a *phantom*: its source
    character is the inverse rotation of ``]`` at the ``[``-fire seek state,
    so the skip path (tested cell == 0) finds it and jumps past the block,
    while the body path (tested cell != 0) sees it as a non-firing ``[``.
    Both paths re-converge after the block in the same rotation state because
    every body length is ``7 (mod 8)``.

    Rows are visited in binary-reflected Gray order.  ``mc`` is the number
    of bits differing from the current row; one expected bit flips per
    step, changing it by ``+1 - 2b`` or ``-1 + 2b``.  A reusable one-cell
    flag increments the result exactly when ``mc == 0`` and the row's table
    entry is one.  Thus each row emits a constant number of blocks.

    Low bits flip most often and already sit nearest the three work cells,
    so the sum of unary guard-to-target walks is geometric and O(T).  The
    construction is one direct Gray pass, with no BFS or DFS.
    """
    n = _validate_truth_table(truth_table)

    # Ignored inputs are still read but do not enter the Gray walk.
    used = essential_inputs(truth_table, n) or [0]
    table = truth_table if len(used) == n else read_at(truth_table, used, n)
    width = len(used)

    b = list(range(n))
    r = n
    mc = n + 1
    m = n + 2

    eff: list[str] = []
    pos = 0
    phantoms: dict[int, int] = {}

    def emit(text: str) -> None:
        nonlocal pos
        eff.append(text)
        pos += len(text)

    # Read and normalize the bits, then seed the reusable match flag.
    for i in range(n):
        emit(",")
        emit("-" * _ASCII_ZERO)
        if i < n - 1:
            emit(">")
    emit(">" * (m - (n - 1)))
    emit("+")

    ptr = m

    def block(guard: int, target: int, op: str) -> None:
        """Emit one preserving phantom conditional."""
        nonlocal ptr
        if ptr < guard:
            emit(">" * (guard - ptr))
        elif ptr > guard:
            emit("<" * (ptr - guard))
        ptr = guard
        p = pos
        emit("[")
        body = _rotfuck_body(guard, target, op)
        emit(body)
        emit("]")
        phantoms[p + len(body) + 1] = p

    # Row zero expects every used bit to be zero, so its mismatch count is
    # the sum of those bits.
    for original in used:
        block(b[original], mc, "+")

    # Consecutive binary-reflected Gray rows differ in one expected bit.
    # Flipping 0 -> 1 changes that bit's mismatch contribution by 1 - 2b;
    # flipping back changes it by -1 + 2b.
    for step in range(2**width):
        row = step ^ (step >> 1)
        if table[row] == "1":
            block(mc, m, "-")
            block(m, r, "+")
            block(mc, m, "+")
        if step + 1 == 2**width:
            continue
        trailing = ((step + 1) & -(step + 1)).bit_length() - 1
        slot = width - 1 - trailing
        guard = b[used[slot]]
        next_row = (step + 1) ^ ((step + 1) >> 1)
        op = "+" if (next_row >> trailing) & 1 else "-"
        if ptr < mc:
            emit(">" * (mc - ptr))
        elif ptr > mc:
            emit("<" * (ptr - mc))
        ptr = mc
        emit(op)
        block(guard, mc, "-" if op == "+" else "+")
        block(guard, mc, "-" if op == "+" else "+")

    if ptr < r:
        emit(">" * (r - ptr))
    elif ptr > r:
        emit("<" * (ptr - r))
    emit("+" * _ASCII_ZERO)
    emit(".")

    program = "".join(eff).encode()
    rotated = bytearray(program)
    for res, table_ in enumerate(_ROT_TABLES):
        rotated[res::8] = program[res::8].translate(table_)
    for i, p in phantoms.items():
        rotated[i] = _PHANTOM[(p + 1) % 8]
    return rotated.decode()
