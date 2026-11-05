"""Collatz Multiverse Boolean program generator: a coded cell table and a decoder.

Packed builds read inputs into registers; the essential ones are summed into an
address that indexes an array ``A`` of packed cells; the last two or three
inputs select a bit inside the decoded cell. Affine tables stream through
two registers instead. A constant table reads every input and
prints one constant, deriving its ASCII byte by signed halving with odd
precursors. The shortest build over the essential inputs wins.

Size:
    O(T) for packed tables, O(n) for affine ones.
    n=10 parity: 1,531 chars, n=10 and: 3,689 chars,
    n=10 random 1847: 11,408 chars. Constants use 23n+228+20bit chars;
    n=8 zero: 412 chars.

Decisions:
    Eight-row cells serve endpoint products from seven inputs; other
    packed tables pay for too many distinct decoders
    ([ablations.eight_row_cells]).
    A decoder indexed by cell value rather than code, and the empty cell on
    top code, lose or fall under the 10% bar
    (:func:`_cm_codes`).
"""

import re
from collections import Counter
from collections.abc import Iterable

from esolangs.generation.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    affine_form,
    essential_inputs,
    grid_width,
    read_at,
)
from esolangs.generation.wrap import balance_score
from esolangs.languages.collatz_multiverse.proof_formulas import execution, workspace
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

__all__ = ["balance_collatz_multiverse", "collatz_multiverse"]


#: Table rows a Collatz Multiverse cell carries, and so its decoder's stride.
#: A cell costs one line whatever its width and the decoder ``c`` lines per
#: distinct cell: at most 64 for four, but up to 2048 for eight.
_CM_CHUNK = 4

#: The shortest line that does nothing -- ``z`` is the zero register.
_CM_PAD = "z=z x+z,NOT PRINT."

#: The fold line ``{dst}=k1 x+{src}``: ``d = A x + B`` is ``d := B + d*A``
#: for a destination holding zero and ``d := d // 2`` for an even one, so
#: folding ``src`` into ``dst`` accumulates without a separate add line.
_CM_FOLD = "{dst}=k1 x+{src},NOT PRINT."


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
    if len(lines) % 2:
        lines.append(_CM_PAD)
    lines.append(f"{capture}=z x+lineNumber,NOT PRINT.")
    lines += [
        f"{array}[lineNumber]=z x+{value},NOT PRINT." if value else _CM_PAD
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
        f"k{value}=z x+lineNumber,NOT PRINT." if value in needed else _CM_PAD
        for value in range(1, max(needed) + 1)
    ]


def _cm_narrow_cells(
    lines: list[str], array: str, values: list[str | None], capture: str
) -> None:
    """Write at odd indices 3+2i; an odd cursor advances without halving."""
    lines += [f"{capture}=z x+k1,NOT PRINT.", "r=z x+k3,NOT PRINT."]
    end = max((i for i, value in enumerate(values) if value), default=-1) + 1
    for value in values[:end]:
        if value:
            lines.append(f"{array}[r]=z x+{value},NOT PRINT.")
        lines.append("r=k1 x+k2,NOT PRINT.")


def _cm_build(
    truth_table: str,
    n: int,
    order: list[int],
    *,
    numbered: bool = True,
    narrow: bool = False,
    invert: bool = False,
    chunk: int = _CM_CHUNK,
) -> str:
    """Emit the cell-and-decoder program over ``order``'s inputs.

    ``order`` names the inputs the address is built from, most significant
    first; its last log2(chunk) select a row within a cell and the rest index the
    cells.  An input it leaves out is still read, and never added.
    A cell's code ``c`` has constant ``chunk * c`` (:func:`_cm_codes`); the decoder
    holds its bit ``j`` at ``chunk * c + j``.  ``numbered`` False stores each cell's
    own value as its code, the build before :func:`_cm_codes` numbered cells.
    ``narrow`` uses odd indices ``3 + 2 i`` and doubles address offsets.
    ``invert`` stores the complemented table -- an empty cell is a cheap pad
    line, so the sparser polarity costs less -- and prints ``49 - bit``.
    """
    address_scale = 2 if narrow else 1
    if invert:
        truth_table = "".join("10"[int(bit)] for bit in truth_table)
    table = read_at(truth_table, order, n)
    padded = table + "0" * (-len(table) % chunk)
    chunks = [
        sum(int(bit) << j for j, bit in enumerate(padded[base : base + chunk]))
        for base in range(0, len(padded), chunk)
    ]
    uses = Counter(chunks)
    codes = _cm_codes(uses) if numbered else {value: value for value in chunks}

    high = max(len(order) - (chunk.bit_length() - 1), 0)
    weights = {address_scale * 2 ** (high - 1 - k) for k in range(high)}
    stored = sorted((code, value) for value, code in codes.items() if code)
    needed = {
        _ASCII_ZERO + invert,
        *weights,
        *(address_scale * chunk * code for code, _ in stored),
    }
    needed.update(address_scale * (1 << j) for j in range(len(order) - high))
    # Decoder/cell pads can capture constants before their first use. Keep the
    # odd-index narrow reader for its column floor ([ablations.pad_constants]).
    pending = set(_cm_chain(needed)) if not narrow else set()
    lines = _cm_narrow_constants(needed) if narrow else _cm_constants(())
    names = {value: f"k{address_scale * chunk * code}" for code, value in stored}
    start = len(lines)
    _cm_emit_decoder(lines, codes, narrow=narrow, chunk=chunk)
    if not narrow:
        _cm_host_constants(lines, start, pending)
        lines += _cm_constants({chunk * code for code, _ in stored}, pending=pending)
    start = len(lines)
    _cm_emit_cells(lines, chunks, names, narrow=narrow)
    if not narrow:
        _cm_host_constants(lines, start, pending)
        lines += _cm_constants(needed, pending=pending)
    _cm_emit_address(lines, n, order, high, address_scale, invert=invert)
    if not narrow:
        _cm_prune_captures(lines)
    return "\n".join(lines)


def _cm_host_constants(lines: list[str], start: int, pending: set[int]) -> None:
    """Replace pads by useful numbered constants, recording their availability."""
    for index in range(start, len(lines)):
        value = index + 1
        if lines[index] == _CM_PAD and value in pending:
            lines[index] = f"k{value}=z x+lineNumber,NOT PRINT."
            pending.remove(value)


def _cm_prune_captures(lines: list[str]) -> None:
    """Restore a pad where capturing a child made its captured ancestor dead."""
    reads = {
        name
        for line in lines
        for name in re.findall(r"\bk\d+\b", line.partition("=")[2])
    }
    for index, line in enumerate(lines):
        name, _, rhs = line.partition("=")
        if name.startswith("k") and "x+lineNumber," in rhs and name not in reads:
            lines[index] = _CM_PAD


def _cm_emit_decoder(
    lines: list[str], codes: dict[int, int], *, narrow: bool, chunk: int
) -> None:
    """Decoder phase: write the decoder cells ``D`` the lookup reads back."""
    decoder: list[str | None] = [None] * (chunk * (max(codes.values()) + 1))
    for value, code in codes.items():
        for j in range(chunk):
            if (value >> j) & 1:
                decoder[chunk * code + j] = "k1"
    cells_builder = _cm_narrow_cells if narrow else _cm_cells
    cells_builder(lines, "D", decoder, "t")


def _cm_emit_cells(
    lines: list[str], chunks: list[int], names: dict[int, str], *, narrow: bool
) -> None:
    """Cells phase: write each chunk's code name into array ``A``."""
    cells_builder = _cm_narrow_cells if narrow else _cm_cells
    cells_builder(lines, "A", [names.get(value) for value in chunks], "s")


def _cm_emit_address(
    lines: list[str],
    n: int,
    order: list[int],
    high: int,
    address_scale: int,
    *,
    invert: bool = False,
) -> None:
    """Address phase: read the inputs, sum the address, print the bit.

    Every input is read into its ``w`` register; the ones ``order`` names
    before ``high`` are weighted into ``s``, the rest select within the
    decoded cell.  The output lines follow the cells phase's arrays.
    """
    lines.extend(f"w{i}=z x+input,NOT PRINT." for i in range(n))
    # ``s`` sits one below the first cell, so the address wants the missing
    # one -- folded into the only odd weight, which has to be added last:
    # ``d = A x + B`` is ``d := B + d*A`` for a destination holding zero and
    # ``d := d // 2`` for an even one, so nothing may halve the address.
    cells, select = order[:high], order[high:]
    for k, i in enumerate(cells[:-1]):
        lines.append(f"w{i}=k{address_scale * 2 ** (high - 1 - k)} x+z,NOT PRINT.")
        lines.append(_CM_FOLD.format(dst="s", src=f"w{i}"))
    if cells:
        lines.append(f"w{cells[-1]}=k{address_scale} x+k{address_scale},NOT PRINT.")
        lines.append(_CM_FOLD.format(dst="s", src=f"w{cells[-1]}"))
    else:
        lines.append(f"s=k1 x+k{address_scale},NOT PRINT.")
    lines.append("t=k1 x+A[s],NOT PRINT.")
    for k, i in enumerate(select[:-1]):
        weight = address_scale * 2 ** (len(select) - 1 - k)
        lines.append(f"w{i}=k{weight} x+z,NOT PRINT.")
        lines.append(_CM_FOLD.format(dst="t", src=f"w{i}"))
    one = f"k{address_scale} x+k{address_scale}"
    lines.append(f"w{select[-1]}={one},NOT PRINT.")
    lines.append(_CM_FOLD.format(dst="t", src=f"w{select[-1]}"))
    lines.append("o=z x+D[t],NOT PRINT.")
    # ``o`` holds the bit: ``0 * a + b`` for a zero, ``1 * a + b`` for a one.
    if invert:
        lines.append(f"o=negativeOne x+k{_ASCII_ZERO + 1},DO PRINT.")
    else:
        lines.append(f"o=k1 x+k{_ASCII_ZERO},DO PRINT.")


def _cm_layout(program: str, width: int) -> str:
    """Narrow complete assignments; an even prefix preserves address parity."""
    if grid_width(program) <= width:
        return program
    compact = program.replace(" ", "").replace("x+", " x+")
    compact = compact.replace("NOTPRINT", "NOT PRINT")
    compact = compact.replace("DOPRINT", "DO PRINT")
    if grid_width(compact) <= width:
        return compact
    # Generated names exclude '_'.  Captured lineNumber addresses shift
    # together; two prefix lines keep the odd capture used by weighted sums.
    # Numbered constants cannot shift, including after a bijective rename.
    if "negativeOne" in compact and "x+lineNumber," not in compact:
        aliased = "_=z x+negativeOne,NOT PRINT.\n" + "z=z x+z,NOT PRINT.\n"
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
        # Line-number constants retain the 27-column floor without negativeOne.
        lines = _cm_narrow_constants({value})
        lines += ["r=z x+input,NOT PRINT."] * n
        lines.append(f"out=z x+k{value},DO PRINT.")
        return "\n".join(lines)
    # All reads leave r in {0, 1}, so its next assignment takes the affine arm.
    lines = ["r=z x+input,NOT PRINT."] * n
    lines += [
        "a=negativeOne x+negativeOne,NOT PRINT.",
        "a=negativeOne x+z,NOT PRINT.",
        "b=z x+a,NOT PRINT.",
        "c=z x+a,NOT PRINT.",
        "b=a x+a,NOT PRINT.",
    ]
    # Signed halving keeps each precursor odd: m = 2b + d, -1 <= d <= 2.
    # The same accumulator can therefore double at every step, without copies.
    addends = []
    while value > 1:
        delta = -1 if value % 4 == 1 else 1 if value % 4 == 3 else 2 - value % 4
        addends.append({-1: "negativeOne", 0: "z", 1: "c", 2: "b"}[delta])
        value = (value - delta) // 2
    if not addends:
        lines.append(f"o=z x+{'a' if value else 'z'},DO PRINT.")
    for index, addend in enumerate(reversed(addends)):
        flag = "DO" if index == len(addends) - 1 else "NOT"
        lines.append(f"a=b x+{addend},{flag} PRINT.")
    return "\n".join(lines)


def _cm_narrow_choice(fitted: str, layouts: list[str]) -> str:
    """Choose the narrowest fallback, retaining the existing length tie-break."""
    return min(
        [fitted, *layouts],
        key=lambda code: (grid_width(code), len(code)),
    )


def _cm_chunk(table: str) -> int:
    """Use eight-row cells for endpoint products from seven inputs."""
    if len(table) < 128:
        return _CM_CHUNK
    ones = table.count("1")
    if ones in (1, len(table) - 1) and table[0] != table[-1]:
        return 8
    return _CM_CHUNK


def _cm_affine_program(table: str, n: int) -> str | None:
    """Stream XOR through two registers, using only positive coefficients."""
    form = affine_form(table, n)
    if form is None or not any(form[1]):
        return None
    bias, coefficients = form
    lines = _cm_constants({_ASCII_ZERO})
    if bias:
        lines.append("a=z x+k1,NOT PRINT.")
    for selected in coefficients:
        lines.append("r=z x+input,NOT PRINT.")
        if selected:
            # (2a+1)(2r+1)+1 is 2/4/10. Halving then zeroing odd values
            # yields XOR's 0/1/0. r stays odd until its next input overwrite.
            lines += [
                "a=k2 x+k1,NOT PRINT.",
                "r=k2 x+k1,NOT PRINT.",
                "a=r x+k1,NOT PRINT.",
                "a=z x+z,NOT PRINT.",
                "a=z x+z,NOT PRINT.",
            ]
    lines.append("a=k1 x+k48,DO PRINT.")
    return "\n".join(lines)


def _cm_candidates(
    truth_table: str, n: int, *, narrow: bool, expanded: bool
) -> list[str]:
    """Return one constant/affine stream, otherwise the selector orders."""
    if len(set(truth_table)) == 1:
        # A constant table needs no evaluation, but the reads are the
        # interface: skipping them strands the caller's bits and the prompts.
        return [
            _cm_constant_program(n, _ASCII_ZERO + int(truth_table[0]), narrow=narrow)
        ]
    if (affine := _cm_affine_program(truth_table, n)) is not None:
        return [affine]
    orders = _cm_orders(essential_inputs(truth_table, n), expanded=expanded)
    chunk = _cm_chunk(read_at(truth_table, orders[0], n))
    return [
        _cm_build(truth_table, n, order, narrow=narrow, invert=invert, chunk=chunk)
        for order in orders
        for invert in (False, True)
    ]


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
    ``v = z x + b``; ``b`` odd then makes ``b * k2 + c``.  Since
    ``2 b`` is 2 mod 4, ``c = (m - 2) mod 4`` forces ``b`` odd, so a constant
    needs its halving chain plus k3: O(log m) lines, within ~2 lines of the
    minimal exhaustive plan (test oracle).  Needs ``m >= 3``.
    """
    c = (m - 2) % 4
    return (m - c) // 2, c


def _cm_chain(
    need: Iterable[int], *, pending: set[int] | None = None
) -> dict[int, tuple[int, int]]:
    """Map missing constants above 2 to their odd-halving ``(b, c)`` plan."""
    plan: dict[int, tuple[int, int]] = {}
    todo = [n for n in need if n > 2]
    while todo:
        m = todo.pop()
        if m not in plan and (pending is None or m in pending):
            plan[m] = _cm_plan(m)
            todo += [v for v in plan[m] if v > 2]
    return plan


def _cm_constants(
    needed: Iterable[int], *, pending: set[int] | None = None
) -> list[str]:
    """Lines building Collatz Multiverse constants for the values in ``needed``.

    Without ``pending``, start at line 1 with captures of k1/k2. Otherwise
    consume only its uninitialized members using :func:`_cm_plan`.
    """
    plan = _cm_chain(needed, pending=pending)
    lines = (
        [
            "k1=z x+lineNumber,NOT PRINT.",
            "k2=z x+lineNumber,NOT PRINT.",
        ]
        if pending is None
        else []
    )
    for n, (b, c) in sorted(plan.items()):
        lines.append(f"k{n}=z x+k{b},NOT PRINT.")
        addend = f"k{c}" if c else "zero"
        lines.append(f"k{n}=k2 x+{addend},NOT PRINT.")
    if pending is not None:
        pending.difference_update(plan)
    return lines


LANGUAGE = Language(
    "Collatz Multiverse",
    RuntimeSpec("collatz_multiverse", category="register_based"),
    boolean=collatz_multiverse,
    balance=balance_collatz_multiverse,
    no_wrap="each line is one complete register assignment",
    proof_execution=(execution, False, (3, 5, 6, 8)),
    proof_workspace=(workspace, False, (3, 4, 5, 6, 7, 9)),
)
