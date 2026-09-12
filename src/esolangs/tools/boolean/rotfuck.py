r"""Boolean-function generator for ROTFuck."""

from functools import cache

from esolangs.tools.boolean.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    essential_inputs,
    minterm_literals,
    read_at,
)

__all__ = ["rotfuck"]

# The eight-step rotation.
_ROTFUCK_CHAIN = "+-><,.[]"


def _rotfuck_rot(char: str, steps: int) -> str:
    r"""Advance ``char`` ``steps`` steps along the ROTfuck rotation cycle."""
    index = _ROTFUCK_CHAIN.index(char)
    return _ROTFUCK_CHAIN[(index + steps) % 8]


def _rotfuck_allowed(offset: int) -> list[str]:
    r"""Commands a body may place at relative offset ``offset``."""
    bad = {_rotfuck_rot("[", offset), _rotfuck_rot("]", offset)}
    return [c for c in "+-><" if c not in bad]


def _rotfuck_neutral(offset: int) -> str:
    r"""Return a two-char net-neutral pair usable at ``offset``."""
    for pair in ("+-", "-+", "><", "<>"):
        if all(c in _rotfuck_allowed(offset + i) for i, c in enumerate(pair)):
            return pair
    raise ValueError(  # pragma: no cover - a neutral pair exists at every offset
        "ROTfuck body padding is impossible at this offset"
    )


@cache
def _rotfuck_move_cycle(state: int, direction: str) -> tuple[tuple[str, ...], int, str]:
    r"""Tile the move pattern from offset state ``state`` (mod 8)."""
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
    r"""Emit ``>``/``<`` to move ``ptr`` toward ``goal``."""
    dist = goal - ptr if direction == ">" else ptr - goal
    texts, start, cycle = _rotfuck_move_cycle(offset % 8, direction)
    if dist <= len(texts):
        return "".join(texts[:dist])
    reps, rem = divmod(dist - start, len(texts) - start)
    return "".join(texts[:start]) + cycle * reps + "".join(texts[start : start + rem])


@cache
def _rotfuck_body_for(delta: int, op: str) -> str:
    r"""Build the body for a guard-relative target at offset ``delta``."""
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
            # padding always shifts a +/-.
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
    r"""Build a body that moves the pointer from ``guard`` to ``target``."""
    return _rotfuck_body_for(target - guard, op)


# Rotating the finished.
# ``rot^{-i}`` of itself, so.
_ROT_TABLES = tuple(
    bytes.maketrans(
        _ROTFUCK_CHAIN.encode(),
        "".join(_rotfuck_rot(c, -res) for c in _ROTFUCK_CHAIN).encode(),
    )
    for res in range(8)
)
_PHANTOM = tuple(ord(_rotfuck_rot("]", -res)) for res in range(8))


def rotfuck(truth_table: str) -> str:
    r"""Build a ROTfuck program computing the given truth table."""
    n = _validate_truth_table(truth_table)

    # A table that ignores some of.
    # cell layout and the block.
    # mismatch cell and one minterm.
    # (row, input) pair.
    # exponent to ``2**width``.
    # its own cell -- the reads are.
    # normalized like the rest and.
    used = essential_inputs(truth_table, n) or [0]
    table = truth_table if len(used) == n else read_at(truth_table, used, n)
    width = len(used)

    b = list(range(n))
    c = list(range(n, 2 * n))
    r = 2 * n
    mc = 2 * n + 1
    m = 2 * n + 2

    eff: list[str] = []
    pos = 0
    phantoms: dict[int, int] = {}

    def emit(text: str) -> None:
        nonlocal pos
        eff.append(text)
        pos += len(text)

    # Read the bits (each on its.
    # complements to 1, and set the.
    # cell starts 0).
    for i in range(n):
        emit(",")
        emit("-" * _ASCII_ZERO)
        if i < n - 1:
            emit(">")
    emit(">" * (c[0] - (n - 1)))
    for i in range(n):
        emit("+")
        if i < n - 1:
            emit(">")
    emit(">" * (m - c[-1]))
    emit("+")

    # Block layout: the complements.
    # literals guard the mismatch.
    # iff that count is nonzero,.
    # result, and two undo passes.
    # .
    # The undo is what lets the two.
    # the same ``mc`` guard that.
    # clear did; ``mc`` is restored.
    # ``-``, which fires on exactly.
    # needs to know the runtime.
    # holds a mismatch *count*.
    block_specs: list[tuple[int, int, str]] = []
    for i in range(n):
        block_specs.append((b[i], c[i], "-"))  # complement c_i = 1 - b_i.
    for k in range(2**width):
        if table[k] != "1":
            continue
        guards = [
            b[used[slot]] if negated else c[used[slot]]
            for slot, negated in minterm_literals(k, width)
        ]
        for guard in guards:
            block_specs.append((guard, mc, "+"))  # mismatch count.
        block_specs.append((mc, m, "-"))  # zero the minterm on any.
        block_specs.append((m, r, "+"))  # accumulate a matching 1-row.
        block_specs.append((mc, m, "+"))  # restore the minterm cell.
        for guard in guards:
            block_specs.append((guard, mc, "-"))  # restore the mismatch count.

    ptr = m
    for guard, target, op in block_specs:
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

    # Every block is guarded on an.
    # exactly the cells below.
    # whatever the table holds --.
    # block is the final complement.
    emit(">" * (r - ptr))
    emit("+" * _ASCII_ZERO)
    emit(".")

    program = "".join(eff).encode()
    rotated = bytearray(program)
    for res, table_ in enumerate(_ROT_TABLES):
        rotated[res::8] = program[res::8].translate(table_)
    for i, p in phantoms.items():
        rotated[i] = _PHANTOM[(p + 1) % 8]
    return rotated.decode()
