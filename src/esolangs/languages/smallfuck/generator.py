"""Smallfuck Boolean program generator: a decision tree with banded result cells.

Input ``i`` is stored in cell ``3 i``; each level splits on its bit with a
flag cell, XORing the answer into one result cell per band of three levels,
which transfers to the parent band.  Cell 2 holds the answer.  Repeated
residuals are deferred behind level flags or same-level banks and run after
the band transfers, and repeated two-input functions share a decoder
(complements share a three-bit code; a retired zero-arm input holds its high
bit).

An affine table folds its counted input cells down a chain into cell 2
([ablations.xor_chain]).

Size:
    O(T) for dense tables, linear in n for parity and ``and``; n=10 random
    1847: 11,076 chars, n=10 parity: 170 chars, n=10 and: 213 chars.

Decisions:
    Splits stay in input order: a greedy order saves 1.1% at n=8, under the
    10% bar.  A tiled n=16 table shrinks 1,747 -> 803 characters (-54%)
    against the plain tree; the test executes it on 128 rows.  Inline text and
    the existing command bound guard the admission of deferred residuals.
"""

import re
from collections.abc import Callable
from itertools import pairwise
from typing import Any

from esolangs.generation.helpers import (
    TEMPLATE_CHAR,
    _validate_truth_table,
    affine_form,
    constant_span_test,
    in_input_order,
    mark_runs,
    move_text,
    same_up_to_wrapping,
    subtree_ids,
    unmark,
)
from esolangs.generation.shared_block import ContinuationCost as _Cost
from esolangs.generation.shared_block import (
    _repeated_blocks,
    repeated_bank,
    repeated_blocks,
)
from esolangs.generation.token_balance import balanced_token_width
from esolangs.generation.wrap import _RUN, balance_score, wrap_chars, wrap_program
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Example, Language

# Each input cell is fresh; zero needs no clear and one needs one flip.
PAIR = ("x>>>", "*>>>")

#: Levels sharing one result cell.  No closed form picks it: a leaf node's
#: result flip travels ~3 band cells while band transfers fall as 1/(2**band-1)
#: an entry, an interior optimum near 3, but the sharing of deferred residuals
#: removes leaf flips at n >= 8 and the argmin then depends on the class.
#: Measured chars an entry over 1..6: random n=3..7 best 3; random n=8..11
#: best 5 (6.0, 10.2, 10.2, 10.0% under 3); parity n=8, 10, tiled n=10 and
#: sparse n=10 best 3, and majority n=8 best 3 but n=10 best 4.  The build
#: is the smaller of the two named bands, so it is never worse than 3;
#: below n=8, 5 still wins parity n=4..6 (8-14%).
BAND = 3
BANDS = (BAND, 5)

#: Cells per level: input ``3 i``, flag ``3 k + 1``, band result ``3 k + 2``.
STRIDE = len(PAIR[0]) - 1
ANSWER = 2


def _flag_cell(level: int) -> int:
    return STRIDE * level + 1


def _band_cell(level: int) -> int:
    return STRIDE * level + 2


def _owns_band_cell(n: int, level: int, band: int) -> bool:
    """Whether ``level`` opens a new band of result cells.

    Bands of ``band`` levels are counted up from the leaves, so the
    band-owning levels are ``n - 1``, ``n - 1 - band``, and so on: exactly
    those with ``(n - band - level - 1) % band == 0``.  The virtual root
    (level -1) owns no cell.
    """
    return level >= 0 and (n - band - level - 1) % band == 0


class _Builder:
    """Emit pointer-tracked macros over initially zero cells."""

    def __init__(self, start: int = 0) -> None:
        self.at = start
        self.code: list[str] = []
        self.count = 0

    def emit(self, code: str) -> None:
        self.code.append(code)
        self.count += len(code)

    def move(self, cell: int) -> None:
        self.emit(move_text(self.at, cell, ">", "<"))
        self.at = cell

    def flip(self, cell: int) -> None:
        self.move(cell)
        self.emit("*")

    def loop(self, cell: int) -> None:
        self.move(cell)
        self.emit("[*")

    def end(self, cell: int) -> None:
        self.move(cell)
        self.emit("]")


def smallfuck(truth_table: str, width: int | None = None) -> str:
    """Return a Smallfuck template whose final tape cell 2 is the answer."""
    natural = in_input_order(truth_table, _smallfuck_ordered)
    n = _validate_truth_table(truth_table)
    if (form := affine_form(truth_table, n)) is not None and any(form[1]):
        natural = min(natural, _xor_chain(n, *form), key=len)
    if width is None or width <= 0:
        return natural
    if width < len(PAIR[0]):
        natural = (TEMPLATE_CHAR + ">>>") * n + natural[len(PAIR[0]) * n :]
    marked = mark_runs(natural, TEMPLATE_CHAR, smallfuck_setters(natural, n))
    return unmark(wrap_program(marked, "smallfuck", width), TEMPLATE_CHAR, n)


def _xor_chain(n: int, bias: int, coefficients: list[int]) -> str:
    """Fold each counted input cell down into the next, ending in cell 2.

    ``[*...*...]`` clears a set cell and flips the one below, so the chain
    leaves the XOR of the counted inputs in cell 2; the bias flips it once
    more ([ablations.xor_chain]).
    """
    cells = [3 * i for i, c in enumerate(coefficients) if c]
    out = [TEMPLATE_CHAR * len(PAIR[0]) * n, "<" * (3 * n - cells[-1])]
    for here, below in pairwise([*reversed(cells), 2]):
        down, up = move_text(here, below, ">", "<"), move_text(below, here, ">", "<")
        out.append(f"[*{down}*{up}]{down}")
    return "".join(out) + ("*" if bias else "")


def smallfuck_setters(template: str, n: int) -> tuple[tuple[str, str], ...]:
    """Keep the pointer walk outside narrow one-character input slots."""
    pair = ("x", "*") if template.replace("\n", "").startswith("$>>>") else PAIR
    return (pair,) * n


def _smallfuck_ordered(table: str, perm: tuple[int, ...]) -> str:
    """Compare the plain tree, deferred residuals and paired roots.

    Deferred plans are the per-level residuals and the unranked same-level
    bank.  The single-residual and ranked-bank forms were retired at 1.2%
    jointly (n=8..12, 40 to 250 tables per class); dropping the per-level
    plan too costs 10.4% on a tiled n=6 table.  A plan above the command
    bound is a cost-model bug and aborts.
    """
    n = len(perm)
    forms = []
    # The bank: random 0%, majority +14.1% at n=10; per-level: parity +40-130%.
    plans = dict.fromkeys(
        [(repeated_blocks(table), ()), repeated_bank(table, ranked=False)]
    )
    # Paired roots: random +15.9/+20.5/+23.2% at n=9/10/11 (12 tables),
    # +5.7% at n=8, 0% below.
    paired = _paired_roots(table)
    for band in BANDS:
        forms.append(_smallfuck_tree(table, perm, band=band))
        for blocks, flags in plans:
            if blocks:
                forms.append(
                    _smallfuck_tree(
                        table, perm, shared_blocks=blocks, flag_levels=flags, band=band
                    )
                )
        if paired:
            forms.append(_smallfuck_tree(table, perm, paired_roots=paired, band=band))
    bound = 9 * n * n + 100 * n + 20
    for _, cost in forms:
        if cost > bound:
            raise AssertionError(f"worst-case cost {cost} exceeds {bound}")
    return min((code for code, _ in forms), key=len)


def _paired_roots(table: str) -> tuple[tuple[int, int], ...]:
    """Return repeated two-input functions, identifying complements."""
    n = _validate_truth_table(table)
    if n < 4:
        return ()
    pairs: dict[int, tuple[int, int]] = {}
    for depth, row, saving in _repeated_blocks(table, include_single=True):
        if depth == n - 2:
            word = int(table[row : row + 4], 2)
            canonical = min(word, word ^ 15)
            previous, first = pairs.get(canonical, (0, row))
            pairs[canonical] = (previous + saving // 4 + 1, first)
    return tuple((code, row) for code, (copies, row) in pairs.items() if copies > 1)


class _Tree:
    """Emitter state and engines for one Smallfuck decision tree.

    Holds what the mutually recursive engines share: the table and split
    order, the constant-span test and subtree ids, the output builder, the
    deferred-block definitions, and the paired-roots decoder state.
    ``split``, ``clear_prefix``, ``transfer``, ``arm``, ``tree``, and
    ``emit_paired_roots`` are methods, so the decoder phase needs no
    ``nonlocal`` mutation.
    """

    def __init__(
        self,
        n: int,
        truth_table: str,
        perm: tuple[int, ...],
        constant: Callable[[int, int], bool],
        ids: list[list[int]],
        builder: _Builder,
        pending_levels: tuple[int, ...],
        selected: dict[tuple[int, int], int],
        pairs: dict[int, int],
        band: int,
    ) -> None:
        self.n = n
        self.band = band
        self.truth_table = truth_table
        self.perm = perm
        self.constant = constant
        self.ids = ids
        self.builder = builder
        self.pending_levels = pending_levels
        self.selected = selected
        self.pairs = pairs
        self.pair_depth = n - 2
        # The tree retires the last two levels while paired roots decode;
        # the decoder switches the shortcut off before pricing its bodies.
        self.pair_phase = bool(pairs)

    def split(
        self,
        bit: int,
        flag: int,
        one: Callable[[], _Cost[int]],
        zero: Callable[[], _Cost[int]],
    ) -> _Cost[int]:
        """Emit a two-arm split on ``bit`` and bound its worst-case cost.

        The one arm runs in ``[* ... ]`` on ``bit`` with ``flag`` flipped
        around it; the zero arm runs in a second ``[* ... ]`` on ``flag``.
        Each arm's bound separates the chars its body emitted itself from
        the loop scaffolding around it, so the returned cost adds the
        commands both arms execute once and takes the worse arm.
        """
        start = self.builder.count
        self.builder.flip(flag)
        self.builder.loop(bit)
        one_start = self.builder.count
        self.builder.flip(flag)
        body_start = self.builder.count
        one_cost = one()
        one_body = self.builder.count - body_start
        self.builder.end(bit)
        # Scaffolding around the one arm: the flag flip and the closing
        # bracket around its body, plus the loop's opening bracket.  The
        # loop's `*` clear runs only on entry, so it is the wrapper below.
        one_scaffold = self.builder.count - one_start - one_body + 1
        one_cost = _Cost(one_scaffold, (one_cost,))
        one_entered = _Cost(1, (one_cost,))
        between = self.builder.count
        self.builder.loop(flag)
        # Commands both arms execute: the flag flip and each loop's `[`
        # test with its moves, minus each loop's `*` clear (per-arm).
        common = (one_start - start - 1) + (self.builder.count - between - 1)
        zero_start = self.builder.count
        body_start = self.builder.count
        zero_cost = zero()
        zero_body = self.builder.count - body_start
        self.builder.end(flag)
        # Scaffolding around the zero arm: its "[*" opener and the
        # closing bracket around its body.
        zero_scaffold = self.builder.count - zero_start - zero_body + 2
        zero_cost = _Cost(zero_scaffold, (zero_cost,))
        return _Cost(common, (one_entered, zero_cost))

    def clear_prefix(self, level: int) -> None:
        """Clear the unread paired-roots inputs at or above ``level``."""
        for unread in range(level, self.pair_depth):
            bit = STRIDE * self.perm[unread]
            self.builder.loop(bit)
            self.builder.end(bit)

    def transfer(self, source: int, target: int) -> None:
        """XOR cell ``source`` into ``target`` and clear ``source``."""
        self.builder.loop(source)
        self.builder.flip(target)
        self.builder.end(source)

    def arm(
        self, level: int, lo: int, hi: int, result: int, on: str, free: int = -1
    ) -> _Cost[int]:
        """XOR into ``result`` whether the span's answer is ``on``."""
        start = self.builder.count
        if self.constant(lo, hi):
            if self.truth_table[lo] == on:
                self.builder.flip(result)
            if self.pair_phase:
                self.clear_prefix(level + 1)
            return _Cost(self.builder.count - start)
        if not _owns_band_cell(self.n, level, self.band):
            return self.tree(level + 1, lo, hi, result, on, free)
        own = _band_cell(level + 1)
        cost = self.tree(level + 1, lo, hi, own, on, free)
        tail = self.builder.count
        self.transfer(own, result)
        # The band transfer's own chars, plus one for the band cell the
        # subtree already priced.
        transfer_chars = self.builder.count - tail + 1
        return _Cost(transfer_chars, (cost,))

    def tree(
        self, level: int, lo: int, hi: int, result: int, on: str, free: int = -1
    ) -> _Cost[int]:
        """Emit level ``level`` of the tree over rows ``[lo, hi)``.

        Retired paired-roots levels emit their three-bit code, deferred
        definitions emit their flag flips, and everything else splits or
        arms recursively into ``result``.  Each regime is a named phase
        below, tried in this order; a phase that does not apply emits
        nothing and returns ``None``.
        """
        cost = self._retired_pair(level, lo, result, on, free)
        if cost is not None:
            return cost
        cost = self._deferred_residual(level, lo, result, on)
        if cost is not None:
            return cost
        mid = (lo + hi) // 2
        bit, flag = STRIDE * self.perm[level], _flag_cell(level)
        cost = self._agreed_halves(level, lo, result, on, free, bit, mid)
        if cost is not None:
            return cost
        cost = self._constant_half(level, lo, hi, result, on, free, bit, mid)
        if cost is not None:
            return cost
        return self._general_split(level, lo, hi, result, on, free, bit, flag, mid)

    def _retired_pair(
        self, level: int, lo: int, result: int, on: str, free: int
    ) -> _Cost[int] | None:
        """Emit a retired level's three-bit pair code, if it has one."""
        if not (self.pair_phase and level == self.pair_depth):
            return None
        start = self.builder.count
        # A zero arm has passed its input's only loop; an ignored input
        # is freed by clearing it. The nearest such cell holds bit 2.
        # Its weighted distances sum s*2**(d-s) = O(2**d), so marks stay O(T).
        word = int(self.truth_table[lo : lo + 4], 2)
        canonical = min(word, word ^ 15)
        if canonical not in self.pairs or (canonical & 4 and free < 0):
            return None
        if (self.truth_table[lo] == "1") != (on == "0"):
            self.builder.flip(result)
        for mask, cell in (
            (1, _flag_cell(self.pair_depth)),
            (2, _flag_cell(self.pair_depth + 1)),
            (4, STRIDE * self.perm[free]),
        ):
            if canonical & mask:
                self.builder.flip(cell)
        return _Cost(self.builder.count - start, target=canonical)

    def _deferred_residual(
        self, level: int, lo: int, result: int, on: str
    ) -> _Cost[int] | None:
        """Emit a deferred definition's flag flip, if this span is one."""
        key = (level, self.ids[level][lo >> (self.n - level)])
        if key not in self.selected:
            return None
        start = self.builder.count
        # A complemented arm contributes its constant now; the common
        # suffix contributes the function itself after band transfers.
        if on == "0":
            self.builder.flip(result)
        self.builder.flip(_flag_cell(self.pending_levels[self.selected[key]]))
        return _Cost(self.builder.count - start, target=self.selected[key])

    def _agreed_halves(
        self,
        level: int,
        lo: int,
        result: int,
        on: str,
        free: int,
        bit: int,
        mid: int,
    ) -> _Cost[int] | None:
        """Descend one half only, if both halves are the same subtree."""
        below = self.ids[level + 1]
        if below[lo >> (self.n - level - 1)] != below[mid >> (self.n - level - 1)]:
            return None
        start = self.builder.count
        if self.pair_phase and level < self.pair_depth:
            self.builder.loop(bit)
            self.builder.end(bit)
            free = level
        extra = self.builder.count - start
        return _Cost(extra, (self.arm(level, lo, mid, result, on, free),))

    def _constant_half(
        self,
        level: int,
        lo: int,
        hi: int,
        result: int,
        on: str,
        free: int,
        bit: int,
        mid: int,
    ) -> _Cost[int] | None:
        """Arm the upper half under the tested bit, if the lower is constant.

        The constant is flipped in first and the upper arm built inverted,
        so the node needs no flag of its own.
        """
        if not self.constant(lo, mid) or (self.pair_phase and level < self.pair_depth):
            return None
        start = self.builder.count
        if self.truth_table[lo] == on:
            self.builder.flip(result)
            on = "1" if on == "0" else "0"
        self.builder.loop(bit)
        body_start = self.builder.count
        cost = self.arm(level, mid, hi, result, on, free)
        arm_body = self.builder.count - body_start
        self.builder.end(bit)
        # Loop scaffolding around the arm: everything but its body,
        # plus the loop's opening bracket emitted before `start`.
        arm_scaffold = self.builder.count - start - arm_body + 1
        # Skipped path: the setup before the arm body, minus the
        # loop's `*` clear, which runs only on entry.
        skipped_setup = body_start - start - 1
        return _Cost(
            0,
            (
                _Cost(arm_scaffold, (cost,)),
                _Cost(skipped_setup),
            ),
        )

    def _general_split(
        self,
        level: int,
        lo: int,
        hi: int,
        result: int,
        on: str,
        free: int,
        bit: int,
        flag: int,
        mid: int,
    ) -> _Cost[int]:
        """Split on the level's bit, arming each half into ``result``."""
        zero_free = level if self.pair_phase and level < self.pair_depth else free
        return self.split(
            bit,
            flag,
            lambda: self.arm(level, mid, hi, result, on, free),
            lambda: self.arm(level, lo, mid, result, on, zero_free),
        )

    def emit_definition(
        self, i: int, depth: int, row: int
    ) -> tuple[_Cost[int], int, int]:
        """Emit deferred definition ``i``; return (body cost, scaffold, skipped).

        Only the first band of each definition transfers to distant cell 2.
        At most n definitions add O(n**2) movement, absorbed by T = 2**n.
        """
        builder = self.builder
        pending = _flag_cell(self.pending_levels[i])
        start = builder.count
        builder.loop(pending)
        skipped = builder.count - start - 1
        del self.selected[depth, self.ids[depth][row >> (self.n - depth)]]
        body_start = builder.count
        body_cost = self.tree(depth, row, row + (1 << (self.n - depth)), ANSWER, "1")
        deferred_body = builder.count - body_start
        builder.end(pending)
        # Loop scaffolding around the deferred body: everything but the
        # body itself, plus the loop's opening bracket.
        active = builder.count - start - deferred_body + 1
        return body_cost, active, skipped

    def emit_paired_roots(self, prefix: _Cost[int]) -> tuple[str, int]:
        """Emit the paired-roots decoder and price every pair tail.

        The tree above retires the last two levels and marks each used code's
        cells; the decoder replays the matching body into the answer cell.
        Emission and pricing stay together because the decoder's leaf prices
        are this function's own second engine.
        """
        # decode needs real subtrees here, not the pair shortcut.
        self.pair_phase = False
        collector = _flag_cell(self.pair_depth - 1)
        # Used inputs are zero; constant leaves clear the unused prefix.
        # Only the high code bit can survive, in at most one input cell.
        skipped = delta = 0
        for level in range(self.pair_depth):
            start = self.builder.count
            bit = STRIDE * self.perm[level]
            self.builder.loop(bit)
            empty = self.builder.count - start - 1
            self.builder.flip(collector)
            self.builder.end(bit)
            skipped += empty
            delta = max(delta, self.builder.count - start - empty)
        bits = (
            collector,
            _flag_cell(self.pair_depth + 1),
            _flag_cell(self.pair_depth),
        )
        guards = (
            _flag_cell(self.pair_depth - 2),
            STRIDE * self.perm[self.pair_depth - 1],
            STRIDE * self.perm[self.pair_depth - 2],
        )
        decoder = _PairDecoder(self, skipped, delta, bits, guards)
        model = decoder.decode(0, (0, *self.pairs))
        decoder.price(model)
        program = "".join(self.builder.code)
        return program, len(PAIR[0]) * self.n + prefix.evaluate(decoder.pair_tails) + 1


class _PairDecoder:
    """Price the paired-roots decoder's code-bit decision tree.

    Holds the decoder's shared state (the cleared-prefix ``skipped`` and
    worst-case ``delta`` costs, the code-bit and guard cells) so ``decode``
    and ``price`` can recurse as methods instead of nested closures.  Each
    leaf names a pair code; ``price`` folds the leaf costs into
    ``pair_tails``, the per-code tail table the tree prefix evaluates
    against.
    """

    def __init__(
        self,
        tree: _Tree,
        skipped: int,
        delta: int,
        bits: tuple[int, int, int],
        guards: tuple[int, int, int],
    ) -> None:
        self.tree = tree
        self.skipped = skipped
        self.delta = delta
        self.bits = bits
        self.guards = guards
        self.pair_tails: dict[int | None, int] = {}

    def decode(self, at: int, labels: tuple[int, ...]) -> _Cost[int]:
        """Build the decision tree over the three code bits.

        At ``at == 3`` the surviving label is the pair code; its body is
        priced with real subtrees (the pair shortcut is off by then) and
        the leaf is named by its code for ``price`` to tabulate.
        """
        tree = self.tree
        start = tree.builder.count
        if at == 3:
            code = labels[0]
            cost = 0
            if code in tree.pairs:
                row = tree.pairs[code]
                body = tree.tree(
                    tree.pair_depth,
                    row,
                    row + 4,
                    ANSWER,
                    "0" if tree.truth_table[row] == "1" else "1",
                )
                cost = body.evaluate({None: 0})
            return _Cost(cost, target=code or None)
        mask = 4 >> at
        zero = tuple(code for code in labels if not code & mask)
        one = tuple(code for code in labels if code & mask)
        if not zero or not one:
            if one:
                tree.builder.flip(self.bits[at])
            extra = tree.builder.count - start
            return _Cost(extra, (self.decode(at + 1, one or zero),))
        return tree.split(
            self.bits[at],
            self.guards[at],
            lambda: self.decode(at + 1, one),
            lambda: self.decode(at + 1, zero),
        )

    def price(self, cost: _Cost[int], extra: int = 0) -> None:
        """Fold the decoded leaf costs into the per-code tail table."""
        extra += cost.value
        if cost.children:
            for child in cost.children:
                self.price(child, extra)
        else:
            target = cost.target
            self.pair_tails[target] = (
                self.skipped + extra + (self.delta if target and target & 4 else 0)
            )


def _check_definitions(
    n: int, blocks: tuple[tuple[int, int], ...], flag_levels: tuple[int, ...]
) -> None:
    """Reject deferred definitions whose levels or flags collide."""
    depths = tuple(depth for depth, _ in blocks)
    if flag_levels:
        if (
            len(flag_levels) != len(blocks)
            or len(set(depths)) != 1
            or len(set(flag_levels)) != len(flag_levels)
            or any(level < depths[0] or level >= n for level in flag_levels)
        ):
            raise ValueError("a bank needs distinct unused flags at one level")
    elif any(left >= right for left, right in pairwise(depths)):
        raise ValueError("deferred levels must be distinct and increasing")
    if any(depth < 0 or depth >= n for depth in depths):
        raise ValueError("deferred levels must be distinct and increasing")


def _smallfuck_tree(
    truth_table: str,
    perm: tuple[int, ...],
    *,
    shared_blocks: tuple[tuple[int, int], ...] = (),
    flag_levels: tuple[int, ...] = (),
    paired_roots: tuple[tuple[int, int], ...] = (),
    band: int = BAND,
) -> tuple[str, int]:
    """Emit one order's template; level ``k`` tests input ``perm[k]``.

    ``truth_table`` is already permuted.  Level ``k`` keeps its flag in
    cell ``3 k + 1``.  Answers are XORed into one cell per band of
    ``band`` levels, counted up from the leaves: a band's top level
    ``k`` owns cell ``3 k + 2`` and transfers it into its parent's cell
    when done, so a flip travels at most ``3 band`` cells and a node costs
    O(1) either way.  An arm whose lower half is constant needs no flag:
    that constant is flipped in first and the upper arm built inverted, so
    a node over two leaves is ``result ^= bit`` alone.
    """
    n = _validate_truth_table(truth_table)
    ids = subtree_ids(truth_table)
    builder = _Builder(STRIDE * n)
    builder.emit(TEMPLATE_CHAR * (len(PAIR[0]) * n))
    blocks = shared_blocks
    _check_definitions(n, blocks, flag_levels)
    pending_levels = flag_levels or tuple(depth for depth, _ in blocks)
    selected = {
        (depth, ids[depth][row >> (n - depth)]): i
        for i, (depth, row) in enumerate(blocks)
    }
    if len(selected) != len(blocks):
        raise ValueError("deferred definitions must name distinct residuals")
    pairs = dict(paired_roots)
    if pairs and (n < 4 or blocks):
        raise ValueError(
            "paired roots need two retired levels and no other definitions"
        )
    tree = _Tree(
        n,
        truth_table,
        perm,
        constant_span_test(truth_table),
        ids,
        builder,
        pending_levels,
        selected,
        pairs,
        band,
    )
    prefix = tree.arm(-1, 0, len(truth_table), ANSWER, "1")
    if pairs:
        return tree.emit_paired_roots(prefix)
    empty_tails = dict.fromkeys([None, *range(len(blocks))], 0)
    cost = len(PAIR[0]) * n + prefix.evaluate(empty_tails)
    stages = [
        (i, *tree.emit_definition(i, depth, row))
        for i, (depth, row) in enumerate(blocks)
    ]
    if shared_blocks:
        tails: dict[int | None, int] = {None: 0}
        for i, body, active, skipped in reversed(stages):
            commands = active + body.evaluate(tails)
            tails = {target: value + skipped for target, value in tails.items()}
            tails[i] = commands
        cost = len(PAIR[0]) * n + prefix.evaluate(tails) + 1
    program = "".join(builder.code)
    return program, cost


def _balance(table: str, default: str) -> str:
    """Balance four-character setters and the one-character narrow setters."""
    n = _validate_truth_table(table)
    candidates = [default]
    for source, minimum, maximum in ((default, 4, None), (smallfuck(table, 3), 1, 3)):
        clean = source.replace("\n", "")
        marked = mark_runs(clean, TEMPLATE_CHAR, smallfuck_setters(clean, n))
        tokens = re.findall(f"{_RUN}|[\\s\\S]", marked)
        width = balanced_token_width(tokens, minimum=minimum, maximum=maximum)
        candidates.append(smallfuck(table, width))
    return min(candidates, key=balance_score)


def _same_layout(template: str, plain: str, layout: Callable[[int], Any]) -> bool:
    """Newlines carry no commands: compare the narrow layouts without them."""
    for width in (1, 4):
        if template.replace("\n", "") == str(layout(width)).replace("\n", ""):
            return True
    return same_up_to_wrapping(template, plain)


LANGUAGE = Language(
    "Smallfuck",
    "smallfuck",
    category="tape_based",
    boolean=smallfuck,
    same_layout=_same_layout,
    contract=BooleanContract(
        note="Smallfuck defines no I/O; this implementation prints final cell 2",
    ),
    wrap=wrap_chars,
    balance=_balance,
    example=Example(setters=smallfuck_setters),
)
