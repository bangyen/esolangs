"""Collatz Multiverse Boolean program generator: a coded cell table and a decoder.

Each input is read into a register; the essential ones are summed into an
address that indexes an array ``A`` of four-row cells, and the last two inputs
select a bit inside the decoded cell.  A constant table reads every input and
prints one constant.  The shortest build over the essential inputs wins.

Size:
    O(T): one line per four-row cell plus four decoder lines per distinct
    cell.  n=10 parity: 8,374 chars, n=10 and: 6,684 chars, n=10 random 1847:
    12,466 chars.

Decisions:
    Cells of eight rows: more decoder lines than the ``T / 8`` they save
    below fourteen inputs.  A decoder indexed by cell value rather than
    code, and the empty cell on top code, lose or fall under the 10% bar
    (:func:`_cm_codes`).
"""

import re
from collections import Counter
from collections.abc import Iterable

from esolangs.generation.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    essential_inputs,
    grid_width,
    read_at,
)
from esolangs.generation.wrap import balance_score
from esolangs.languages.collatz_multiverse.proof_formulas import execution, workspace
from esolangs.registry._language import Language

__all__ = ["balance_collatz_multiverse", "collatz_multiverse"]


#: Table rows a Collatz Multiverse cell carries, and so its decoder's stride.
#: A cell costs one line whatever its width and the decoder ``c`` lines per
#: distinct cell: at most 64 for four, but up to 2048 for eight.
_CM_CHUNK = 4

#: The shortest line that does nothing -- ``z`` is the zero register.
_CM_PAD = "z=zx+z,NOT PRINT."

#: The fold line ``{dst}=k1x+{src}``: ``d = A x + B`` is ``d := B + d*A``
#: for a destination holding zero and ``d := d // 2`` for an even one, so
#: folding ``src`` into ``dst`` accumulates without a separate add line.
_CM_FOLD = "{dst}=k1x+{src},NOT PRINT."


#: Renamable registers in a laid-out program.
_CM_REGISTER = r"k\d+|w\d+|b\d+|\bout\b|\bzero\b"


def _cm_cells(
    lines: list[str], array: str, values: list[str | None], capture: str
) -> None:
    """Append a block placing ``values`` at consecutive cells of ``array``.

    An array subscript may name ``lineNumber``, so ``A[lineNumber] = z x + v``
    drops ``v`` into the cell the writing line's own number addresses: one
    line a cell, no pointer to advance.  ``capture`` takes the address one
    below the first cell -- a line rather than a built constant, padded odd so
    the reader can sum even weights into it.  A ``None`` value gets a pad
    line, trailing runs included: dropping a block's trailing pads saved a
    fixed ~74 chars a program, a share that tends to zero
    ([ablations.trailing_pad_drop]).
    """
    if (len(lines) + 1) % 2 == 0:
        lines.append(_CM_PAD)
    lines.append(f"{capture}=zx+lineNumber,NOT PRINT.")
    lines += [
        f"{array}[lineNumber]=zx+{value},NOT PRINT." if value else _CM_PAD
        for value in values
    ]


def _cm_codes(counts: Counter[int]) -> dict[int, int]:
    """Return codes ``0, 1, ...`` for the distinct cells: the decoder spans them.

    A cell's code, not its bits, is what the table stores and the decoder is
    indexed by, so a table with ``m`` distinct cells needs ``4 m`` decoder
    lines whatever their values -- ``1000`` is value 1 but ``0001`` is 8,
    and a decoder spanning the values paid 32 lines to reach it.  The top
    code goes to the non-empty cell whose highest set bit is lowest; the
    remaining codes follow the frequency ranking, code 0 first.
    Preferring the empty cell for code 0 lost on every corpus measured
    ([ablations.coded_cells]).  Putting the empty cell on top instead loses 2.6% at
    n=8 (13 random tables).
    """
    ranked = sorted(counts, key=lambda v: (-counts[v], v))
    pool = [value for value in ranked if value != 0] or ranked
    top = min(pool, key=lambda v: (v.bit_length(), -counts[v]))
    ranked.remove(top)
    return {value: code for code, value in enumerate([*ranked, top])}


def _cm_narrow_constants(needed: set[int]) -> list[str]:
    """Capture constants at their numbered lines; intervening pads are inert."""
    needed = needed | {1, 2, 3, 4}  # k1..k4: the cursor and address code reads them
    return [
        f"k{value}=zx+lineNumber,NOT PRINT." if value in needed else _CM_PAD
        for value in range(1, max(needed) + 1)
    ]


def _cm_narrow_cells(
    lines: list[str], array: str, values: list[str | None], capture: str
) -> None:
    """Write at odd indices 3+2i; an odd cursor advances without halving."""
    lines += [f"{capture}=zx+k1,NOT PRINT.", "r=zx+k3,NOT PRINT."]
    end = max((i for i, value in enumerate(values) if value), default=-1) + 1
    for value in values[:end]:
        if value:
            lines.append(f"{array}[r]=zx+{value},NOT PRINT.")
        lines.append("r=k1x+k2,NOT PRINT.")


def _cm_build(
    truth_table: str,
    n: int,
    order: list[int],
    *,
    numbered: bool = True,
    narrow: bool = False,
) -> str:
    """Emit the cell-and-decoder program over ``order``'s inputs.

    ``order`` names the inputs the address is built from, most significant
    first; its last two select a row within a cell and the rest index the
    cells.  An input it leaves out is still read, and never added.
    A cell's code ``c`` has constant ``4 c`` (:func:`_cm_codes`); the decoder
    holds its bit ``j`` at ``4 c + j``.  ``numbered`` False stores each cell's
    own value as its code, the build before :func:`_cm_codes` numbered cells.
    ``narrow`` uses odd indices ``3 + 2 i`` and doubles address offsets.
    """
    address_scale = 2 if narrow else 1
    table = read_at(truth_table, order, n)
    padded = table + "0" * (-len(table) % _CM_CHUNK)
    chunks = [
        sum(int(bit) << j for j, bit in enumerate(padded[base : base + _CM_CHUNK]))
        for base in range(0, len(padded), _CM_CHUNK)
    ]
    uses = Counter(chunks)
    codes = _cm_codes(uses) if numbered else {value: value for value in chunks}

    high = max(len(order) - 2, 0)
    weights = {address_scale * 2 ** (high - 1 - k) for k in range(high)}
    stored = sorted((code, value) for value, code in codes.items() if code)
    needed = {
        _ASCII_ZERO,
        *weights,
        *(address_scale * _CM_CHUNK * code for code, _ in stored),
    }
    lines = _cm_emit_constants(needed, narrow=narrow)
    names = {value: f"k{address_scale * _CM_CHUNK * code}" for code, value in stored}
    _cm_emit_decoder(lines, codes, narrow=narrow)
    _cm_emit_cells(lines, chunks, names, narrow=narrow)
    _cm_emit_address(lines, n, order, high, address_scale)
    return "\n".join(lines)


def _cm_emit_constants(needed: set[int], *, narrow: bool) -> list[str]:
    """Constants phase: return the lines building every needed constant."""
    if narrow:
        return _cm_narrow_constants(needed)
    return _cm_constants(needed, zero="z")


def _cm_emit_decoder(lines: list[str], codes: dict[int, int], *, narrow: bool) -> None:
    """Decoder phase: write the decoder cells ``D`` the lookup reads back."""
    decoder: list[str | None] = [None] * (_CM_CHUNK * (max(codes.values()) + 1))
    for value, code in codes.items():
        for j in range(_CM_CHUNK):
            if (value >> j) & 1:
                decoder[_CM_CHUNK * code + j] = "k1"
    cells_builder = _cm_narrow_cells if narrow else _cm_cells
    cells_builder(lines, "D", decoder, "t")


def _cm_emit_cells(
    lines: list[str], chunks: list[int], names: dict[int, str], *, narrow: bool
) -> None:
    """Cells phase: write each chunk's code name into array ``A``."""
    cells_builder = _cm_narrow_cells if narrow else _cm_cells
    cells_builder(lines, "A", [names.get(value) for value in chunks], "s")


def _cm_emit_address(
    lines: list[str], n: int, order: list[int], high: int, address_scale: int
) -> None:
    """Address phase: read the inputs, sum the address, print the bit.

    Every input is read into its ``w`` register; the ones ``order`` names
    before ``high`` are weighted into ``s``, the rest select within the
    decoded cell.  The output lines follow the cells phase's arrays.
    """
    for i in range(n):
        lines.append(f"w{i}=zx+input,NOT PRINT.")
    # ``s`` sits one below the first cell, so the address wants the missing
    # one -- folded into the only odd weight, which has to be added last:
    # ``d = A x + B`` is ``d := B + d*A`` for a destination holding zero and
    # ``d := d // 2`` for an even one, so nothing may halve the address.
    cells, select = order[:high], order[high:]
    for k, i in enumerate(cells[:-1]):
        lines.append(f"w{i}=k{address_scale * 2 ** (high - 1 - k)}x+z,NOT PRINT.")
        lines.append(_CM_FOLD.format(dst="s", src=f"w{i}"))
    if cells:
        lines.append(f"w{cells[-1]}=k{address_scale}x+k{address_scale},NOT PRINT.")
        lines.append(_CM_FOLD.format(dst="s", src=f"w{cells[-1]}"))
    else:
        lines.append(f"s=k1x+k{address_scale},NOT PRINT.")
    lines.append("t=k1x+A[s],NOT PRINT.")
    if len(select) == 2:
        lines.append(f"w{select[0]}=k{2 * address_scale}x+z,NOT PRINT.")
        lines.append(_CM_FOLD.format(dst="t", src=f"w{select[0]}"))
    one = f"k{address_scale}x+k{address_scale}"
    lines.append(f"w{select[-1]}={one},NOT PRINT.")
    lines.append(_CM_FOLD.format(dst="t", src=f"w{select[-1]}"))
    lines.append("o=zx+D[t],NOT PRINT.")
    # ``o`` holds the bit: ``0 * a + b`` for a zero, ``1 * a + b`` for a one.
    lines.append(f"o=k1x+k{_ASCII_ZERO},DO PRINT.")


def _cm_layout(program: str, width: int) -> str:
    """Narrow complete assignments; an even prefix preserves address parity."""
    if grid_width(program) <= width:
        return program
    compact = program.replace(" ", "").replace("NOTPRINT", "NOT PRINT")
    compact = compact.replace("DOPRINT", "DO PRINT")
    if grid_width(compact) <= width:
        return compact
    # Generated names exclude '_'.  Captured lineNumber addresses shift
    # together; two prefix lines keep the odd capture used by weighted sums.
    if "negativeOne" in compact:
        aliased = "_=zx+negativeOne,NOT PRINT.\n" + "z=zx+z,NOT PRINT.\n"
        aliased += compact.replace("negativeOne", "_")
        if grid_width(aliased) < grid_width(compact):
            compact = aliased
    if grid_width(compact) <= width:
        return compact
    # A bijective rename changes no lines, so captured addresses and parity stay.
    # Uppercase names other than A/D are absent from the generated cell decoder.
    registers = list(dict.fromkeys(re.findall(_CM_REGISTER, compact)))
    alphabet = "BCEFGHIJKLMNOPQRSTUVWXYZ"
    aliases = {
        name: alphabet[i] if i < len(alphabet) else f"B{i - len(alphabet)}"
        for i, name in enumerate(registers)
    }
    return re.sub(_CM_REGISTER, lambda match: aliases[match.group()], compact)


def _cm_orders(essential: list[int], *, expanded: bool) -> list[list[int]]:
    """Return the selector orders; width requests (``expanded``) add a rotation.

    A middle-rotated order for the default call saves 0.46% at n=8, under
    the 10% bar.
    """
    orders = [essential]
    if expanded and len(essential) >= 3:
        orders.append(essential[2:] + essential[:2])
    return orders


def _cm_constant_program(n: int, value: int, *, narrow: bool = False) -> str:
    """Read every input and print one constant."""
    if narrow:
        lines = _cm_narrow_constants({value})
        lines += [f"b{i}=zx+input,NOT PRINT." for i in range(n)]
        lines.append(f"out=zx+k{value},DO PRINT.")
    else:
        lines = _cm_constants({value})
        lines += [f"b{i} = negativeOne x + input, NOT PRINT." for i in range(n)]
        lines.append(f"out = negativeOne x + k{value}, DO PRINT.")
    return "\n".join(lines)


def _cm_narrow_choice(fitted: str, layouts: list[str]) -> str:
    """Choose the narrowest fallback, retaining the existing length tie-break."""
    return min(
        [fitted, *layouts],
        key=lambda code: (grid_width(code), len(code)),
    )


def _cm_candidates(
    truth_table: str, n: int, *, narrow: bool, expanded: bool
) -> list[str]:
    """Return every build: one for a constant, else per order."""
    if len(set(truth_table)) == 1:
        # A constant table needs no evaluation, but the reads are the
        # interface: skipping them strands the caller's bits and the prompts.
        return [
            _cm_constant_program(n, _ASCII_ZERO + int(truth_table[0]), narrow=narrow)
        ]
    orders = _cm_orders(essential_inputs(truth_table, n), expanded=expanded)
    return [_cm_build(truth_table, n, order, narrow=narrow) for order in orders]


def collatz_multiverse(truth_table: str, width: int | None = None) -> str:
    """Return a Collatz Multiverse program for ``truth_table`` (MSB first).

    ``width`` selects complete statements with fixed odd-index cells when needed.
    """
    n = _validate_truth_table(truth_table)
    program = min(
        _cm_candidates(truth_table, n, narrow=False, expanded=width is not None),
        key=len,
    )
    if width is None:
        return program
    fitted = _cm_layout(program, width)
    if grid_width(fitted) <= width:
        return fitted
    layouts = [
        _cm_layout(c, width)
        for c in _cm_candidates(truth_table, n, narrow=True, expanded=True)
    ]
    return _cm_narrow_choice(fitted, layouts)


def _cm_layout_versions(program: str) -> tuple[str, ...]:
    """Return reachable original, compact, aliased and renamed spellings."""
    compact = _cm_layout(program, max(1, grid_width(program) - 1))
    aliased = _cm_layout(program, max(1, grid_width(compact) - 1))
    return program, compact, aliased, _cm_layout(program, 1)


def balance_collatz_multiverse(truth_table: str, default: str) -> str:
    """Return the best-balanced spelling of the wide and narrow builds."""
    n = _validate_truth_table(truth_table)
    wide = collatz_multiverse(truth_table, len(default))
    narrow = _cm_candidates(truth_table, n, narrow=True, expanded=True)
    # Each build's four spellings are the finite regimes the old sweep over
    # fit thresholds selected among; scoring them directly needs no width.
    candidates = [default]
    for program in [wide, *narrow]:
        candidates.extend(_cm_layout_versions(program))
    return min(candidates, key=balance_score)


def _cm_plan(m: int) -> tuple[int, int]:
    """Return ``(b, c)`` with ``m = 2 b + c``, ``b`` odd and ``0 <= c <= 3``.

    ``v = a x + b`` applies the Collatz rule to ``v``: odd or zero becomes
    ``v * a + b``, even halves.  A fresh register copies ``b`` with
    ``v = negativeOne x + b``; ``b`` odd then makes ``b * k2 + c``.  Since
    ``2 b`` is 2 mod 4, ``c = (m - 2) mod 4`` forces ``b`` odd, so a constant
    needs its halving chain plus k3: O(log m) lines, within ~2 lines of the
    minimal exhaustive plan (test oracle).  Needs ``m >= 3``.
    """
    c = (m - 2) % 4
    return (m - c) // 2, c


def _cm_chain(need: Iterable[int]) -> dict[int, tuple[int, int]]:
    """Map every constant above 2 that building ``need`` takes to its ``(b, c)``."""
    plan: dict[int, tuple[int, int]] = {}
    todo = [n for n in need if n > 2]
    while todo:
        m = todo.pop()
        if m not in plan:
            plan[m] = _cm_plan(m)
            todo += [v for v in plan[m] if v > 2]
    return plan


def _cm_constants(needed: Iterable[int], zero: str = "zero") -> list[str]:
    """Lines building Collatz Multiverse constants for the values in ``needed``.

    ``k1``/``k2`` bootstrap from ``negativeOne``; the rest use
    :func:`_cm_plan`'s two-line trick.  Only referenced constants are built.

    ``zero`` names the never-written register the language reads as 0; the
    name is free (any never-assigned register reads as 0), so a caller that
    spells zero on most lines can pick the shortest.
    """
    plan = _cm_chain(needed)
    lines = [
        "k1 = negativeOne x + negativeOne, NOT PRINT.",
        f"k1 = negativeOne x + {zero}, NOT PRINT.",
        "k2 = negativeOne x + negativeOne, NOT PRINT.",
        "k2 = negativeOne x + k1, NOT PRINT.",
    ]
    for n, (b, c) in sorted(plan.items()):
        lines.append(f"k{n} = negativeOne x + k{b}, NOT PRINT.")
        addend = f"k{c}" if c else zero
        lines.append(f"k{n} = k2 x + {addend}, NOT PRINT.")
    return lines


LANGUAGE = Language(
    "Collatz Multiverse",
    "collatz_multiverse",
    category="register_based",
    boolean=collatz_multiverse,
    balance=balance_collatz_multiverse,
    no_wrap="each line is one complete register assignment",
    proof_execution=(execution, False, (3, 6)),
    proof_workspace=(workspace, False, (3, 6)),
)
