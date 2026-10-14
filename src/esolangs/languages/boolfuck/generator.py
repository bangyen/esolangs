"""Native Boolfuck Boolean generator over single-bit cells.

Tape layout (head starts on cell 0, all cells start 0):

- cells ``2i`` / ``2i+1``: input bit ``x_i`` and its per-level flag
  (interleaved, so tests move the head only a couple of cells)
- cell ``2n``: result bit R; cell ``-1``: read scratch for the 7
  non-value bits of each input byte

Reads: under the Boolean input contract each input byte is ``'0'`` or
``'1'``, and the interpreter streams bytes little-endian, so the first
bit read is the value bit; it lands on the byte's own cell and the
other seven are read into scratch and forgotten (bytes consumed whole).

Tree: a decision tree re-choreographed for flip-only bit cells. Node
``i`` sets ``flag_i``, then ``[+`` on the bit cell clears a set bit and
runs the one-side (which clears the flag); ``[+`` on the flag then runs
the zero-side only when the flag survived (the bit was 0). Both sides
clear what they test, so every flag is 0 again when the node returns.
Constant subtrees fold to a leaf, exactly as in
``helpers.decision_tree_body``; a ``"1"`` leaf flips R, and only one
leaf ever executes, so R flips at most once. Repeated residuals defer
to unused level flags and emit once in depth order after the prefix tree,
only when text shrinks and the unchanged command bound admits it.
At n>=9, two-input cofactors also normalize to shared AND/XOR gates;
input flips and output bias distinguish their functions without extra flags.
Affine tables stream through two data cells, toggling the accumulator once
per selected bit; ignored bytes are still consumed whole.

Print: R prints as bit 0 of the answer byte; bits 1..3 print from a
cleared flag cell, bits 4..5 after flipping it, bits 6..7 cleared
again -- the ASCII ``'0'``/``'1'`` byte in exactly 8 prints.
"""

from typing import Literal

from esolangs.generation.helpers import (
    _validate_truth_table,
    affine_form,
    constant_span_test,
    move_text,
    subtree_ids,
)
from esolangs.generation.shared_block import ContinuationCost as _Cost
from esolangs.generation.shared_block import repeated_blocks
from esolangs.generation.shared_flag import flag_tree_body
from esolangs.generation.wrap import wrap_chars
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language

type _Kind = Literal["and", "xor"]
type _Normal = tuple[_Kind | None, int, bool, bool, int | None]


def affine_stream(table: str) -> str | None:
    """Stream an affine truth table through one input and one accumulator."""
    n = _validate_truth_table(table)
    if n < 2:
        return None
    form = affine_form(table, n)
    if form is None:
        return None
    bias, coefficients = form
    # Selected bytes cost at most 17 commands, ignored ones 10, plus at
    # most 19 for bias/printing: 17*n+19 fits the existing bound for n>=2.
    # Cells -1/0/1 use at most four address bits; machine/cursor state
    # needs bl(L)+12+bl(n), below the existing workspace formula for n>=2.
    parts = [">+<" if bias else ""]
    for coefficient in coefficients:
        parts.append("," + ("[+>+<]" if coefficient else "") + "<,,,,,,,>")
    # Ignored reads can leave cell 0 set; clear it before the ASCII high bits.
    parts.append("[+]>;<;;;+;;+;;")
    return "".join(parts)


def _normal(word: str) -> _Normal:
    if word.count("1") in (0, 4):
        return None, int(word[0]), False, False, None
    if word[0] == word[3] and word[1] == word[2]:
        return "xor", int(word[0]), False, False, None
    if word.count("1") in (1, 3):
        bias = int(word.count("1") == 3)
        exceptional = next(i for i, bit in enumerate(word) if int(bit) != bias)
        return "and", bias, not exceptional & 2, not exceptional & 1, None
    return "and", int(word[0]), False, False, 1 if word[0] == word[1] else 0


class _Emitter:
    """Boolfuck text plus head position and command count."""

    def __init__(self, result: int, carrier: int) -> None:
        self.out: list[str] = []
        self.pos = 0
        self.count = 0
        self.result = result
        self.carrier = carrier

    def emit(self, code: str) -> None:
        self.out.append(code)
        self.count += len(code)

    def move(self, target: int) -> None:
        self.emit(move_text(self.pos, target, ">", "<"))
        self.pos = target

    def clear(self, cell: int) -> None:
        self.move(cell)
        self.emit("[+]")

    def printer(self) -> None:
        self.move(self.result)
        self.emit(";")
        self.move(self.carrier)
        self.emit(";;;+;;+;;")


class _GateTree:
    """Prefix decision tree over the first ``n-2`` inputs, gates at the leaves."""

    def __init__(self, table: str, flags: dict[_Kind, int], emitter: _Emitter) -> None:
        self.table = table
        self.flags = flags
        self.e = emitter
        self.n = n = _validate_truth_table(table)
        self.depth = n - 2
        self.x = 2 * self.depth
        self.y = self.x + 2
        self.ids = subtree_ids(table)
        self.constant = constant_span_test(table)

    # Let M be the sum of the original input-address widths and b=bl(2n).
    # Read scratch and transient flags need at most M+2 bits. After the
    # prefix, four gate cells need at most 4b<=M+2 for n>=9. Constant exits
    # clear x/y before setting R/carrier, adding at most two address bits.
    # State and input cursor need bl(L)+max(12,b+11)+bl(n), so the total
    # fits the existing workspace formula, including power-of-two lengths.
    def leaf(self, value: int) -> None:
        e = self.e
        e.clear(self.x)
        e.clear(self.y)
        if value:
            e.move(e.result)
            e.emit("+")
        e.printer()

    def gate_leaf(self, lo: int, hi: int) -> _Cost[int]:
        e = self.e
        start = e.count
        kind, bias, flipx, flipy, forced = _normal(self.table[lo:hi])
        if kind is None:
            raise ValueError("constant cofactor reached a pending gate")
        if forced is not None:
            e.clear((self.x, self.y)[forced])
            e.emit("+")
        for cell, flip in ((self.x, flipx), (self.y, flipy)):
            if flip:
                e.move(cell)
                e.emit("+")
        if bias:
            e.move(e.result)
            e.emit("+")
        e.move(self.flags[kind])
        e.emit("+")
        return _Cost(e.count - start + int(forced is not None), target=self.flags[kind])

    def fork(self, i: int, lo: int, mid: int, hi: int, start: int) -> _Cost[int]:
        e = self.e
        bit, flag = 2 * i, 2 * i + 1
        e.move(flag)
        e.emit("+")
        e.move(bit)
        zero_entry = e.count - start + 1
        e.emit("[+")
        e.move(flag)
        e.emit("+")
        one_entry = e.count - start
        one = self.node(i + 1, mid, hi)
        finish = e.count
        e.move(bit)
        e.emit("]")
        one_finish = e.count - finish + 1  # the closing bracket rechecks [
        zero_start = e.count
        e.move(flag)
        e.emit("[+")
        one_finish += e.count - zero_start - 1  # the zero arm skips its +
        zero_entry += e.count - zero_start
        zero = self.node(i + 1, lo, mid)
        finish = e.count
        e.move(flag)
        e.emit("]")
        zero_finish = e.count - finish + 1
        return _Cost(
            0,
            (
                _Cost(one_entry + one_finish, (one,)),
                _Cost(zero_entry + zero_finish, (zero,)),
            ),
        )

    def node(self, i: int, lo: int, hi: int) -> _Cost[int]:
        e = self.e
        start = e.count
        if self.constant(lo, hi):
            self.leaf(int(self.table[lo]))
            # Each clear executes at most four commands, one more than text.
            return _Cost(e.count - start + 2)
        if i == self.depth:
            return self.gate_leaf(lo, hi)
        n = self.n
        mid = (lo + hi) // 2
        left = self.ids[i + 1][lo >> (n - i - 1)]
        right = self.ids[i + 1][mid >> (n - i - 1)]
        if left == right:
            e.clear(2 * i)
            prefix = e.count - start + 1
            return _Cost(prefix, (self.node(i + 1, lo, mid),))
        return self.fork(i, lo, mid, hi, start)


def _gate_tail(tree: _GateTree, kind: _Kind) -> tuple[int, int]:
    """Emit one pending-gate tail; return (head distance, active commands)."""
    e, x, y, result = tree.e, tree.x, tree.y, tree.e.result
    pending = tree.flags[kind]
    distance = abs(pending - e.pos)
    e.move(pending)
    e.emit("[+")
    start = e.count
    if kind == "and":
        e.move(x)
        e.emit("[+")
        e.move(y)
        e.emit("[+")
        e.move(result)
        e.emit("+")
        e.move(y)
        e.emit("]")
        e.move(x)
        e.emit("]")
        e.clear(y)
    else:
        for cell in (x, y):
            e.move(cell)
            e.emit("[+")
            e.move(result)
            e.emit("+")
            e.move(cell)
            e.emit("]")
    e.printer()
    e.move(pending)
    active = e.count - start + (2 if kind == "xor" else 0) + 4
    e.emit("]")
    return distance, active


_SCRATCH = -1


def _command_bound(n: int) -> int:
    """Return the most commands a Boolfuck candidate over ``n`` inputs may take."""
    return 2 * n * n + 27 * n + 8


def normal_gates(table: str) -> str | None:
    """Return shared normalized gates where both existing ledgers admit them."""
    n = _validate_truth_table(table)
    # Prefix forks cost at most 15 commands per input. The AND/XOR tails
    # give 2*n*n + 25*n + 26, at most the existing bound exactly when n>=9.
    # Native extreme paths attain it at n=9 (413) and n=16 (938).
    if n < 9:
        return None
    x = 2 * (n - 2)
    kinds = {_normal(table[row : row + 4])[0] for row in range(0, len(table), 4)} - {
        None
    }
    gates = [kind for kind in ("and", "xor") if kind in kinds]
    flags = {kind: x + 1 + 2 * i for i, kind in enumerate(gates)}
    e = _Emitter(result=2 * n, carrier=x + 1)
    for i in range(n):
        e.move(2 * i)
        e.emit(",")
        e.move(_SCRATCH)
        e.emit("," * 7)
    header_cost = e.count
    tree = _GateTree(table, flags, e)
    prefix = tree.node(0, 0, len(table))
    tails: dict[int | None, int] = dict.fromkeys((None, *flags.values()), 0)
    for kind in gates:
        distance, active = _gate_tail(tree, kind)
        for target in tails:
            tails[target] += distance + (active if target == flags[kind] else 1)
    commands = header_cost + prefix.evaluate(tails)
    if commands > _command_bound(n):
        return None
    return "".join(e.out)


def boolfuck(truth_table: str) -> str:
    """Return a native Boolfuck program for an MSB-first truth table."""
    # Dropping the single-block, bank and mixed-bank candidates costs at most
    # 6.2% over 200 tables per class at n=9 and n=12 (repeat tables, jointly);
    # the per-level blocks form is kept: dropping it loses 19.8% (noisy affine).
    programs = [_boolfuck_tree(truth_table)[0]]
    for candidate in (affine_stream(truth_table), normal_gates(truth_table)):
        if candidate is not None:
            programs.append(candidate)
    blocks = repeated_blocks(truth_table)
    if blocks:
        program, commands = _boolfuck_tree(truth_table, shared_blocks=blocks)
        if commands <= _command_bound(_validate_truth_table(truth_table)):
            programs.append(program)
    return min(programs, key=len)


def _boolfuck_tree(
    truth_table: str,
    shared: tuple[int, int] | None = None,
    *,
    shared_blocks: tuple[tuple[int, int], ...] = (),
    flag_levels: tuple[int, ...] = (),
) -> tuple[str, int]:
    """Emit a tree, optionally deferring a block into its first unused flag."""
    n = _validate_truth_table(truth_table)
    # Cell 1 carries the answer's constant bits: every flag is 0 again there.
    out = _Emitter(result=2 * n, carrier=1)

    # Read phase: value bit of byte i to cell 2i, other 7 bits to scratch.
    for i in range(n):
        out.move(2 * i)
        out.emit(",")
        out.move(_SCRATCH)
        out.emit("," * 7)

    # Decision tree over the stored bits.
    read_cost = out.count
    body, tree_cost = flag_tree_body(
        truth_table,
        tuple(range(n)),
        out.pos,
        out.result,
        shared=shared,
        shared_blocks=shared_blocks,
        flag_levels=flag_levels,
        flip=True,
    )
    out.emit(body)
    out.pos = out.result
    tail_start = out.count

    # Print the ASCII answer byte: R, 0,0,0, 1,1, 0,0 (little-endian).
    out.printer()

    return "".join(out.out), read_cost + tree_cost + out.count - tail_start


LANGUAGE = Language(
    "Boolfuck",
    "boolfuck",
    category="tape_based",
    boolean=boolfuck,
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    wrap=wrap_chars,
    eof="EOF supplies zero bits",
)
