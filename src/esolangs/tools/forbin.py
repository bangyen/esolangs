"""Boolean-function generator for Forbin."""

from collections.abc import Callable

from esolangs.tools.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    constant_span_test,
)

_FORBIN_ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


_FORBIN_RESERVED = {"for", "in", "main", "out", "return"}


#: Inputs answered by the shift register rather than by a branch.  A block
#: costs two characters an entry (the literal and its comma) against the
#: twenty-odd a tree leaf costs, so the per-entry constant falls as this
#: rises while the register's fixed prologue doubles with it: 2.78 at five,
#: 2.39 at six, 2.22 at seven.  Seven is the last value that still measures
#: cleanly -- at eight the block is wider than the whole table at ``n = 7``,
#: which is a rung ``tests/proofs/deep/linearity.py`` fits a line through.
_BLOCK_BITS = 7


def _forbin_name(index: int) -> str:
    """Return the ``index``th shortest non-keyword identifier."""
    base = len(_FORBIN_ALPHABET)
    candidate = 0
    while True:
        value = candidate + 1
        chars = []
        while value:
            value, digit = divmod(value - 1, base)
            chars.append(_FORBIN_ALPHABET[digit])
        name = "".join(reversed(chars))
        if name not in _FORBIN_RESERVED:
            if index == 0:
                return name
            index -= 1
        candidate += 1


class _Names:
    """The identifiers one program uses, shortest where they repeat most."""

    def __init__(self, n: int, block: int) -> None:
        taken = 0

        def take(count: int) -> list[str]:
            nonlocal taken
            names = [_forbin_name(taken + k) for k in range(count)]
            taken += count
            return names

        # The tree names an input bit once a node and calls ``table`` or a
        # constant printer once a leaf, so those repeat with the table
        # length and take the one-character names first.
        self.bits = take(n)
        self.table, self.zero, self.one = take(3)
        (self.junk,) = take(1)
        self.cells = take(block)


def _byte(bit: int) -> str:
    """Return an ``out`` argument list printing the digit ``bit``."""
    return ",".join(format(_ASCII_ZERO + bit, "08b"))


def forbin(truth_table: str) -> str:
    """Build a Forbin program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Forbin's ``in`` reads one bit (most significant first), so each input
    byte contributes 8 reads and only the last bit (the LSB, which is what
    distinguishes ``'0'`` from ``'1'``) is used.  One assignment collects
    all ``8n`` of them: a single right-hand side is re-evaluated once per
    target, so ``a,a,a,a,a,a,a,b=(in 0)`` drops seven bits into a scratch
    name and keeps the eighth.

    The table is *painted*, not walked.  Its last :data:`_BLOCK_BITS`
    inputs address a block of ``2 ** _BLOCK_BITS`` entries, and each block
    is handed to ``table`` as a literal argument list -- two characters an
    entry.  ``table``'s parameters are a shift register: for each of those
    inputs in turn, one multi-assignment slides the upper half of the live
    window down over the lower half when the bit is 1, so the first
    parameter ends up holding the addressed entry, which is printed.  The
    remaining ``n - _BLOCK_BITS`` inputs pick the block with a range-loop
    if (``for _:1..b`` runs once when ``b`` is 1 and not at all when it is
    0, and every leaf returns), and a constant span anywhere in that tree
    collapses to a call to one of the two printers.
    """
    n = _validate_truth_table(truth_table)
    low = min(n, _BLOCK_BITS)
    high = n - low
    block = 1 << low
    names = _Names(n, block)

    used: set[str] = set()
    tree = _tree(truth_table, n, high, names, used)
    lines = ["main{", _reads(n, names), *tree, "}"]
    # A table that folds everywhere paints no block, so the register would
    # be dead prologue.
    if names.table in used:
        lines.append(_register(names, block, high, n))
    for bit, name in ((0, names.zero), (1, names.one)):
        if name in used:
            lines.append(f"{name}{{out {_byte(bit)};}}")
    return "\n".join(lines)


def _reads(n: int, names: _Names) -> str:
    """Return the one assignment that reads every input's low bit."""
    targets: list[str] = []
    for bit in names.bits[:n]:
        targets.extend([names.junk] * 7)
        targets.append(bit)
    return f"{','.join(targets)}=(in 0);"


def _tree(
    truth_table: str,
    n: int,
    high: int,
    names: _Names,
    used: set[str],
) -> list[str]:
    """Return the block-selecting branch tree, recording the callees used."""
    constant: Callable[[int, int], bool] = constant_span_test(truth_table)

    def emit(level: int, row: int) -> list[str]:
        span = 2 ** (n - level)
        if constant(row, row + span):
            name = names.one if truth_table[row] == "1" else names.zero
            used.add(name)
            return [f"return({name})"]
        if level == high:
            # The literal block goes on a line of its own: it is one
            # unbreakable token, and the wrapper holds a line to its width
            # unless a single token already overruns it.
            used.add(names.table)
            block = ",".join(truth_table[row : row + span])
            return [f"return({names.table}", f"{block})"]
        return [
            f"for _:1..{names.bits[level]}{{",
            *emit(level + 1, row + span // 2),
            "}",
            *emit(level + 1, row),
        ]

    return emit(0, 0)


def _register(names: _Names, block: int, high: int, n: int) -> str:
    """Return the ``table`` function: a shift register over one block."""
    cells = names.cells
    body: list[str] = []
    live = block
    for level in range(high, n):
        half = live // 2
        slide = f"{','.join(cells[:half])}={','.join(cells[half:live])}"
        body.append(f"for _:1..{names.bits[level]}{{{slide}}}")
        live = half
    body.append(f"out 0,0,1,1,0,0,0,{cells[0]};")
    return f"{names.table} {','.join(cells)}{{{''.join(body)}}}"
