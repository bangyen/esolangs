"""Boolean generator for collatz multiverse."""

import re
from collections import Counter

from esolangs.registry._language import Language
from esolangs.tools.helpers import (
    _ASCII_ZERO,
    _cm_constants,
    _validate_truth_table,
    essential_inputs,
    read_at,
)

__all__ = ["balance_collatz_multiverse", "collatz_multiverse"]


#: Table rows a Collatz Multiverse cell carries, and so its decoder's stride.
#: A cell costs one line whatever its width and the decoder ``c`` lines per
#: distinct cell: at most 64 for four, but up to 2048 for eight, more than
#: the ``T / 8`` lines eight saves below fourteen inputs.
_CM_CHUNK = 4

#: Cell-constant names: one character, and none a register spelled elsewhere.
#: Fifteen, one per nonzero code a four-row cell can take.
_CM_ALIAS = "abcefghijlmnpqr"

#: The shortest line that does nothing -- ``z`` is the zero register.
_CM_PAD = "z=zx+z,NOT PRINT."


def _span(text: str) -> int:
    """Return the longest line's length."""
    return max(map(len, text.splitlines()), default=0)


#: Renamable registers in a laid-out program.
_CM_REGISTER = r"k\d+|w\d+|b\d+|\bout\b|\bzero\b"


def _cm_cells(
    lines: list[str], array: str, values: list[str | None], capture: str
) -> None:
    """Append a block placing ``values`` at consecutive cells of ``array``.

    ``capture`` takes the address one below the first cell -- a line rather
    than a built constant, padded odd so the reader can sum even weights into
    it.  A ``None`` value is left at its default, free in a trailing run.
    """
    if (len(lines) + 1) % 2 == 0:
        lines.append(_CM_PAD)
    lines.append(f"{capture}=zx+lineNumber,NOT PRINT.")
    block = [
        f"{array}[lineNumber]=zx+{value},NOT PRINT." if value else _CM_PAD
        for value in values
    ]
    while block and block[-1] == _CM_PAD:
        block.pop()
    lines += block


def _cm_codes(counts: Counter[int]) -> dict[int, int]:
    """Return codes ``0, 1, ...`` for the distinct cells: the decoder spans them.

    A cell's code, not its bits, is what the table stores and the decoder is
    indexed by, so a table with ``m`` distinct cells needs ``4 m`` decoder
    lines whatever their values -- ``1000`` is value 1 but ``0001`` is 8,
    and a decoder spanning the values paid 32 lines to reach it.  Code 0 is
    the cell nothing writes, so it goes to the empty cell when there is one
    (its cells cost a pad) and else to the most frequent.  The top code's
    decoder entries past its highest set bit are trailing pads and drop, so
    it goes to the cell whose highest set bit is lowest.  Putting the empty
    cell on top instead saves 1.09% at n=8, under the 10% bar.
    """
    ranked = sorted(counts, key=lambda v: (-counts[v], v))
    head = []
    if 0 in counts:
        ranked.remove(0)
        head = [0]
    top = min(ranked, key=lambda v: (v.bit_length(), -counts[v]))
    ranked.remove(top)
    return {value: code for code, value in enumerate([*head, *ranked, top])}


def _cm_narrow_constants(needed: set[int]) -> list[str]:
    """Capture constants at their numbered lines; intervening pads are inert."""
    needed |= {1, 2, 3, 4}  # k1..k4: the cursor and address code reads them
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
    ``numbered`` False stores each cell's own value as its code, the build
    before :func:`_cm_codes` numbered cells.
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
    lines = _cm_narrow_constants(needed) if narrow else _cm_constants(needed, zero="z")
    # A cell names its code's constant, or a one-letter alias of it when the
    # alias line is cheaper than the characters the alias saves.
    # The narrow cursor owns r throughout both array blocks.
    alias_pool = _CM_ALIAS.replace("r", "u") if narrow else _CM_ALIAS
    names: dict[int, str] = {}
    aliased = 0
    for code, value in stored:
        constant = f"k{address_scale * _CM_CHUNK * code}"
        alias = alias_pool[aliased]
        line = f"{alias}=zx+{constant},NOT PRINT."
        if uses[value] * (len(constant) - 1) > len(line) + 1:
            lines.append(line)
            aliased += 1
            names[value] = alias
        else:
            names[value] = constant
    decoder: list[str | None] = [None] * (_CM_CHUNK * (max(codes.values()) + 1))
    for value, code in codes.items():
        for j in range(_CM_CHUNK):
            if (value >> j) & 1:
                decoder[_CM_CHUNK * code + j] = "k1"
    cells_builder = _cm_narrow_cells if narrow else _cm_cells
    cells_builder(lines, "D", decoder, "t")
    cells_builder(lines, "A", [names.get(value) for value in chunks], "s")

    for i in range(n):
        lines.append(f"w{i}=zx+input,NOT PRINT.")
    # ``s`` sits one below the first cell, so the address wants the missing
    # one -- folded into the only odd weight, which has to be added last.
    cells, select = order[:high], order[high:]
    for k, i in enumerate(cells[:-1]):
        lines.append(f"w{i}=k{address_scale * 2 ** (high - 1 - k)}x+z,NOT PRINT.")
        lines.append(f"s=k1x+w{i},NOT PRINT.")
    if cells:
        lines.append(f"w{cells[-1]}=k{address_scale}x+k{address_scale},NOT PRINT.")
        lines.append(f"s=k1x+w{cells[-1]},NOT PRINT.")
    else:
        lines.append(f"s=k1x+k{address_scale},NOT PRINT.")
    lines.append("t=k1x+A[s],NOT PRINT.")
    if len(select) == 2:
        lines.append(f"w{select[0]}=k{2 * address_scale}x+z,NOT PRINT.")
        lines.append(f"t=k1x+w{select[0]},NOT PRINT.")
    one = f"k{address_scale}x+k{address_scale}"
    lines.append(f"w{select[-1]}={one},NOT PRINT.")
    lines.append(f"t=k1x+w{select[-1]},NOT PRINT.")
    lines.append("o=zx+D[t],NOT PRINT.")
    # ``o`` holds the bit: ``0 * a + b`` for a zero, ``1 * a + b`` for a one.
    lines.append(f"o=k1x+k{_ASCII_ZERO},DO PRINT.")
    return "\n".join(lines)


def _cm_layout(program: str, width: int) -> str:
    """Narrow complete assignments; an even prefix preserves address parity."""
    if _span(program) <= width:
        return program
    compact = program.replace(" ", "").replace("NOTPRINT", "NOT PRINT")
    compact = compact.replace("DOPRINT", "DO PRINT")
    if _span(compact) <= width:
        return compact
    # Generated names exclude '_'.  Captured lineNumber addresses shift
    # together; two prefix lines keep the odd capture used by weighted sums.
    if "negativeOne" in compact:
        aliased = "_=zx+negativeOne,NOT PRINT.\n" + "z=zx+z,NOT PRINT.\n"
        aliased += compact.replace("negativeOne", "_")
        if _span(aliased) < _span(compact):
            compact = aliased
    if _span(compact) <= width:
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
        key=lambda code: (_span(code), len(code)),
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
    """Build a Collatz Multiverse program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.
    ``width`` selects complete statements with fixed odd-index cells when needed.

    The table is placed in cells and indexed, not walked.  An array subscript
    may name ``lineNumber``, so ``A[lineNumber] = z x + v`` drops ``v`` into
    the cell the writing line's own number addresses: such a block lays the
    table out at consecutive addresses for one line a cell, no pointer to
    advance.  Four rows ride in each cell, stored as a *code* ``c`` whose
    constant is ``4 c`` (:func:`_cm_codes`), and the last two inputs select
    within it through a decoder holding the cell's bit ``j`` at ``4 c + j``.
    ``d = A x + B`` is ``d := B + d*A`` for a destination holding zero and
    ``d := d // 2`` for an even one, so an address takes its odd weight last:
    nothing halves it.

    The shortest build over the essential inputs wins; an ignored input is
    read and never added.
    """
    n = _validate_truth_table(truth_table)
    program = min(
        _cm_candidates(truth_table, n, narrow=False, expanded=width is not None),
        key=len,
    )
    if width is None or width <= 0:
        return program
    fitted = _cm_layout(program, width)
    if _span(fitted) <= width:
        return fitted
    layouts = [
        _cm_layout(c, width)
        for c in _cm_candidates(truth_table, n, narrow=True, expanded=True)
    ]
    return _cm_narrow_choice(fitted, layouts)


def _cm_layout_versions(program: str) -> tuple[str, ...]:
    """Return reachable original, compact, aliased and renamed spellings."""
    compact = _cm_layout(program, max(1, _span(program) - 1))
    aliased = _cm_layout(program, max(1, _span(compact) - 1))
    return program, compact, aliased, _cm_layout(program, 1)


def balance_collatz_multiverse(truth_table: str, default: str) -> str:
    """Balance the finite statement-spelling regimes at their fit thresholds."""
    from esolangs.tools.wrap import balance_score

    n = _validate_truth_table(truth_table)
    wide = collatz_multiverse(truth_table, len(default))
    narrow = _cm_candidates(truth_table, n, narrow=True, expanded=True)
    versions = [
        [(_span(source), source) for source in _cm_layout_versions(program)]
        for program in [wide, *narrow]
    ]
    thresholds = {1}
    for spellings in versions:
        for span, _source in spellings:
            thresholds.update((span, max(1, span - 1)))

    def fitted(spellings: list[tuple[int, str]], width: int) -> str:
        return next(
            (source for span, source in spellings if span <= width), spellings[-1][1]
        )

    candidates = [default]
    for width in sorted(thresholds):
        program = fitted(versions[0], width)
        if _span(program) > width:
            program = _cm_narrow_choice(
                program, [fitted(item, width) for item in versions[1:]]
            )
        candidates.append(program)
    return min(candidates, key=balance_score)


LANGUAGE = Language(
    "Collatz Multiverse",
    "register_based.collatz_multiverse",
    boolean=collatz_multiverse,
    balance=balance_collatz_multiverse,
    no_wrap="each line is one complete register assignment",
)
