"""Boolean generator for collatz multiverse."""

import re

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


def _cm_codes(chunks: list[int], *, zero_top: bool) -> dict[int, int] | None:
    """Return codes ``0, 1, ...`` for the distinct cells: the decoder spans them.

    A cell's code, not its bits, is what the table stores and the decoder is
    indexed by, so a table with ``m`` distinct cells needs ``4 m`` decoder
    lines whatever their values -- ``1000`` is value 1 but ``0001`` is 8,
    and a decoder spanning the values paid 32 lines to reach it.  Code 0 is
    the cell nothing writes, so it goes to the empty cell when there is one
    (its cells cost a pad) and else to the most frequent.  The top code's
    decoder entries past its highest set bit are trailing pads and drop, so
    it goes to the cell whose highest set bit is lowest.

    ``zero_top`` instead puts the empty cell on top, where its four decoder
    entries all drop, and pays for its cells with an alias; ``None`` when
    there is no empty cell to move.
    """
    counts: dict[int, int] = {}
    for value in chunks:
        counts[value] = counts.get(value, 0) + 1
    if zero_top and 0 not in counts:
        return None
    ranked = sorted(counts, key=lambda v: (-counts[v], v))
    head = []
    if 0 in counts and not zero_top:
        ranked.remove(0)
        head = [0]
    top = 0 if zero_top else min(ranked, key=lambda v: (v.bit_length(), -counts[v]))
    ranked.remove(top)
    return {value: code for code, value in enumerate([*head, *ranked, top])}


def _cm_narrow_constants(needed: set[int]) -> list[str]:
    """Capture constants at their numbered lines; intervening pads are inert."""
    needed |= {1, 2, 3, 4}
    return [
        f"k{value}=zx+lineNumber,NOT PRINT." if value in needed else _CM_PAD
        for value in range(1, max(needed) + 1)
    ]


def _cm_narrow_cells(
    lines: list[str], array: str, values: list[str | None], capture: str
) -> None:
    """Write at odd indices 3+2i; an odd cursor advances without halving."""
    lines += [f"{capture}=zx+k1,NOT PRINT.", "r=zx+k3,NOT PRINT."]
    last = max((i for i, value in enumerate(values) if value), default=-1)
    for value in values[: last + 1]:
        if value:
            lines.append(f"{array}[r]=zx+{value},NOT PRINT.")
        lines.append("r=k1x+k2,NOT PRINT.")


def _cm_build(
    truth_table: str,
    n: int,
    order: list[int],
    *,
    zero_top: bool | None,
    narrow: bool = False,
) -> str | None:
    """Emit the cell-and-decoder program over ``order``'s inputs.

    ``order`` names the inputs the address is built from, most significant
    first; its last two select a row within a cell and the rest index the
    cells.  An input it leaves out is still read, and never added.
    ``zero_top`` picks :func:`_cm_codes`'s numbering; ``None`` stores each
    cell's own value as its code, the build before cells were numbered.
    ``narrow`` uses odd indices ``3 + 2 i`` and doubles address offsets.
    """
    address_scale = 2 if narrow else 1
    table = read_at(truth_table, order, n)
    padded = table + "0" * (-len(table) % _CM_CHUNK)
    chunks = [
        sum(int(bit) << j for j, bit in enumerate(padded[base : base + _CM_CHUNK]))
        for base in range(0, len(padded), _CM_CHUNK)
    ]
    if zero_top is None:
        codes: dict[int, int] | None = {value: value for value in chunks}
    else:
        codes = _cm_codes(chunks, zero_top=zero_top)
    if codes is None:
        return None
    uses: dict[int, int] = {}
    for value in chunks:
        uses[value] = uses.get(value, 0) + 1

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
    names: dict[int, str] = {}
    for code, value in stored:
        constant = f"k{address_scale * _CM_CHUNK * code}"
        # The narrow cursor owns r throughout both array blocks.
        alias_pool = _CM_ALIAS.replace("r", "u") if narrow else _CM_ALIAS
        alias = alias_pool[sum(len(name) == 1 for name in names.values())]
        line = f"{alias}=zx+{constant},NOT PRINT."
        if uses[value] * (len(constant) - 1) > len(line) + 1:
            lines.append(line)
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
    last = f"k{address_scale}x+k{address_scale}"
    lines.append(f"w{select[-1]}={last},NOT PRINT.")
    lines.append(f"t=k1x+w{select[-1]},NOT PRINT.")
    lines.append("o=zx+D[t],NOT PRINT.")
    # ``o`` holds the bit: ``0 * a + b`` for a zero, ``1 * a + b`` for a one.
    lines.append(f"o=k1x+k{_ASCII_ZERO},DO PRINT.")
    return "\n".join(lines)


def _cm_layout(program: str, width: int) -> str:
    """Narrow complete assignments; an even prefix preserves address parity."""
    if max(map(len, program.splitlines()), default=0) <= width:
        return program
    compact = program.replace(" ", "").replace("NOTPRINT", "NOT PRINT")
    compact = compact.replace("DOPRINT", "DO PRINT")
    if max(map(len, compact.splitlines()), default=0) <= width:
        return compact
    # Generated names exclude '_'.  Captured lineNumber addresses shift
    # together; two prefix lines keep the odd capture used by weighted sums.
    if "negativeOne" in compact:
        aliased = "_=zx+negativeOne,NOT PRINT.\n" + "z=zx+z,NOT PRINT.\n"
        aliased += compact.replace("negativeOne", "_")
        if max(map(len, aliased.splitlines())) < max(map(len, compact.splitlines())):
            compact = aliased
    if max(map(len, compact.splitlines())) <= width:
        return compact
    # A bijective rename changes no lines, so captured addresses and parity stay.
    # Uppercase names other than A/D are absent from the generated cell decoder.
    registers = list(
        dict.fromkeys(re.findall(r"k\d+|w\d+|b\d+|\bout\b|\bzero\b", compact))
    )
    alphabet = "BCEFGHIJKLMNOPQRSTUVWXYZ"
    aliases = {
        name: alphabet[i] if i < len(alphabet) else f"B{i - len(alphabet)}"
        for i, name in enumerate(registers)
    }
    return re.sub(
        r"k\d+|w\d+|b\d+|\bout\b|\bzero\b",
        lambda match: aliases[match.group()],
        compact,
    )


def _cm_orders(essential: list[int], *, expanded: bool) -> list[list[int]]:
    """Return the selector orders, including the width-only first pair."""
    orders = [essential]
    if len(essential) >= 3:
        if expanded:
            orders.append(essential[2:] + essential[:2])
        orders.append([*essential[1:-1], essential[0], essential[-1]])
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
        key=lambda code: (max(map(len, code.splitlines())), len(code)),
    )


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
    constant is ``4 c``, and the last two inputs select within it through a
    decoder holding the cell's bit ``j`` at ``4 c + j``.  ``d = A x + B`` is
    ``d := B + d*A`` for a destination holding zero and ``d := d // 2`` for an
    even one, so an address takes its odd weight last: nothing halves it.

    Numbered builds store codes ``0 .. m`` (:func:`_cm_codes`),
    which halves the three-input total, over the essential inputs only (an
    ignored input is read and never added). The last two or the first and
    last inputs select; width requests also try the first two.  Only which input a
    level tests moves; the reads stay in name order. Both code numberings
    are tried: the empty chunk stays at code zero or moves to the top,
    where its decoder pads drop.
    """
    n = _validate_truth_table(truth_table)
    if all(c == truth_table[0] for c in truth_table):
        # A constant table needs no evaluation, but the reads are the
        # interface: skipping them strands the caller's bits and the prompts.
        const = _ASCII_ZERO + int(truth_table[0])
        program = _cm_constant_program(n, const)
        if width is None or width <= 0:
            return program
        fitted = _cm_layout(program, width)
        if max(map(len, fitted.splitlines())) <= width:
            return fitted
        narrow = _cm_layout(_cm_constant_program(n, const, narrow=True), width)
        return _cm_narrow_choice(fitted, [narrow])

    orders = _cm_orders(essential_inputs(truth_table, n), expanded=width is not None)
    candidates = [
        _cm_build(truth_table, n, order, zero_top=zero_top)
        for order in orders
        for zero_top in (False, True)
    ]
    program = min((c for c in candidates if c is not None), key=len)
    if width is None or width <= 0:
        return program
    fitted = _cm_layout(program, width)
    if max(map(len, fitted.splitlines())) <= width:
        return fitted
    narrow_candidates = [
        _cm_build(truth_table, n, order, zero_top=zero_top, narrow=True)
        for order in orders
        for zero_top in (False, True)
    ]
    layouts = [_cm_layout(c, width) for c in narrow_candidates if c is not None]
    return _cm_narrow_choice(fitted, layouts)


def _cm_layout_versions(program: str) -> tuple[str, ...]:
    """Return reachable original, compact, aliased and renamed spellings."""
    compact = _cm_layout(program, max(1, max(map(len, program.splitlines())) - 1))
    aliased = _cm_layout(program, max(1, max(map(len, compact.splitlines())) - 1))
    return program, compact, aliased, _cm_layout(program, 1)


def balance_collatz_multiverse(truth_table: str, default: str) -> str:
    """Balance the finite statement-spelling regimes at their fit thresholds."""
    from esolangs.tools.wrap import balance_score

    n = _validate_truth_table(truth_table)
    wide = collatz_multiverse(truth_table, len(default))
    if len(set(truth_table)) == 1:
        narrow = [
            _cm_constant_program(n, _ASCII_ZERO + int(truth_table[0]), narrow=True)
        ]
    else:
        orders = _cm_orders(essential_inputs(truth_table, n), expanded=True)
        narrow = [
            source
            for order in orders
            for zero_top in (False, True)
            if (
                source := _cm_build(
                    truth_table, n, order, zero_top=zero_top, narrow=True
                )
            )
            is not None
        ]
    versions = [
        [
            (max(map(len, source.splitlines())), source)
            for source in _cm_layout_versions(program)
        ]
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
        if max(map(len, program.splitlines())) > width:
            program = _cm_narrow_choice(
                program, [fitted(item, width) for item in versions[1:]]
            )
        candidates.append(program)
    return min(candidates, key=balance_score)
