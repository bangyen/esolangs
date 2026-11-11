"""Smallfuck Boolean templates: banded prefix and two-input Davio coefficients.

For suffix inputs y,z, write f=K xor yA xor zB xor yzC.  Prefix leaves
XOR K into the result and A/B/C into three spare band-five cells; one
shared tail applies y and z.  Deferred residuals and the complemented
paired-root decoder share this coefficient engine. Definitions advance in
depth; an affine table retains its XOR chain.

Size:
    O(T) dense; n=10 random 1847: 9,595 chars, n=10 parity: 170 chars,
    n=10 and: 365 chars. Constants: zero 4n; one min(7n - 1, 4n + 5).

Decisions:
    Two-input Davio saves 32.13/29.84% at n=7/8; small tables grow and
    execute more commands ([ablations.davio_two_inputs]). Three weights
    require five-level bands. One-input Davio and local ANF fail admission.
    Existing input/output polarity twins and the affine chain remain;
    all candidates use the coefficient engine, never an old-program fallback.
"""

from collections.abc import Callable, Sequence
from functools import partial
from itertools import pairwise
from typing import Any

from esolangs.generation.algebraic import affine_form
from esolangs.generation.anf import anf_coefficients
from esolangs.generation.helpers import (
    _validate_truth_table,
    constant_span_test,
    in_input_order,
    move_text,
    same_up_to_wrapping,
    subtree_ids,
)
from esolangs.generation.lookup import constant_output
from esolangs.generation.requests import BalanceRequest, GenerationRequest
from esolangs.generation.shared_block import ContinuationCost as _Cost
from esolangs.generation.shared_block import (
    _repeated_blocks,
    repeated_bank,
    repeated_blocks,
)
from esolangs.generation.template import InputSlot, TemplateLayout, layout_fragments
from esolangs.generation.wrap import TokenWrapper, balance_score

# Each input cell is fresh; zero needs no clear and one needs one flip.
PAIR = ("x>>>", "*>>>")
_INPUT = InputSlot(len(PAIR[0]))
_NARROW_INPUT = InputSlot(1)
_WRAPPER = TokenWrapper(r"[\s\S]")

#: Five-level bands leave three top result cells free for Davio coefficients.
BAND = 5

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
    return _layout(truth_table, width).source


def _layout(truth_table: str, width: int | None) -> TemplateLayout:
    natural = in_input_order(truth_table, _smallfuck_ordered)
    n = _validate_truth_table(truth_table)
    # A chain of ifs is cheap and an else is not, so AND-like tables beat their
    # OR-like duals; the reversed table behind a prologue that flips every
    # input cell once (the setters stay as they are) reaches the cheap polarity.
    # Likewise the complement behind a closing flip of cell 2.
    flipped = "".join("10"[int(bit)] for bit in truth_table)
    twins = [
        in_input_order(
            table[::-1] if negate else table,
            partial(_smallfuck_ordered, negate=negate, complement=complement),
        )
        for table, complement in ((truth_table, False), (flipped, True))
        for negate in (False, True)
        if negate or complement
    ]
    natural = min(natural, *twins, key=lambda layout: len(layout.source))
    if n >= 3 and constant_output(truth_table) == "1":
        # Cell 2 is outside the input walk: set it before walking away.
        natural = layout_fragments((">>*<<", *(_INPUT,) * n))
    if (form := affine_form(truth_table, n)) is not None and any(form.coefficients):
        natural = min(
            natural,
            _xor_chain(n, form.bias, form.coefficients),
            key=lambda layout: len(layout.source),
        )
    if width is None or width <= 0:
        return natural
    if width < len(_INPUT):
        natural = _narrow(natural)
    return _WRAPPER.wrap_template(natural, width)


def _narrow(layout: TemplateLayout) -> TemplateLayout:
    """Move the pointer walk out of each four-character slot."""
    start, end = layout.spans[0][0], layout.spans[-1][1]
    inputs = (_NARROW_INPUT, ">>>") * len(layout.spans)
    return layout_fragments((layout.source[:start], *inputs, layout.source[end:]))


def _xor_chain(n: int, bias: int, coefficients: tuple[int, ...]) -> TemplateLayout:
    """Fold each counted input cell down into the next, ending in cell 2.

    ``[*...*...]`` clears a set cell and flips the one below, so the chain
    leaves the XOR of the counted inputs in cell 2; the bias flips it once
    more ([ablations.xor_chain]).
    """
    cells = [3 * i for i, c in enumerate(coefficients) if c]
    out = ["<" * (3 * n - cells[-1])]
    for here, below in pairwise([*reversed(cells), 2]):
        down, up = move_text(here, below, ">", "<"), move_text(below, here, ">", "<")
        out.append(f"[*{down}*{up}]{down}")
    return layout_fragments((*(_INPUT,) * n, "".join(out), "*" if bias else ""))


def smallfuck_setters(template: str, n: int) -> tuple[tuple[str, str], ...]:
    """Keep the pointer walk outside narrow one-character input slots."""
    clean = template.replace("\n", "").removeprefix(">>*<<")
    pair = ("x", "*") if clean.startswith("$>>>") else PAIR
    return (pair,) * n


def _smallfuck_ordered(
    table: str,
    perm: tuple[int, ...],
    *,
    negate: bool = False,
    complement: bool = False,
) -> TemplateLayout:
    """Compare the plain tree, deferred residuals and paired roots.

    Deferred plans are the per-level residuals and the unranked same-level
    bank.  The single-residual and ranked-bank forms were retired at 1.2%
    jointly (n=8..12, 40 to 250 tables per class); dropping the per-level
    plan too costs 10.4% on a tiled n=6 table.  A plan above the command
    bound is a cost-model bug and aborts.
    """
    n = len(perm)
    forms = []
    # Historical pre-Davio measurements.
    # The bank: random 0%, majority +14.1% at n=10; per-level: parity +40-130%.
    plans = dict.fromkeys(
        [(repeated_blocks(table), ()), repeated_bank(table, ranked=False)]
    )
    # Paired roots: random +15.9/+20.5/+23.2% at n=9/10/11 (12 tables),
    # +5.7% at n=8, 0% below.
    paired = _paired_roots(table)
    band = BAND
    forms.append(
        _smallfuck_tree(table, perm, band=band, negate=negate, complement=complement)
    )
    for blocks, flags in plans:
        if blocks:
            forms.append(
                _smallfuck_tree(
                    table,
                    perm,
                    shared_blocks=blocks,
                    flag_levels=flags,
                    band=band,
                    negate=negate,
                    complement=complement,
                )
            )
    if paired:
        forms.append(
            _smallfuck_tree(
                table,
                perm,
                paired_roots=paired,
                band=band,
                negate=negate,
                complement=complement,
            )
        )
    bound = 9 * n * n + 100 * n + 20
    for _, cost in forms:
        if cost > bound:
            raise AssertionError(f"worst-case cost {cost} exceeds {bound}")
    return min((layout for layout, _ in forms), key=lambda layout: len(layout.source))


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
        ids: Sequence[Sequence[int]],
        builder: _Builder,
        pending_levels: tuple[int, ...],
        selected: dict[tuple[int, int], int],
        pairs: dict[int, int],
        band: int,
        head: int,
    ) -> None:
        self.n = n
        self.head = head
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
        # Last actual band owner is n-6; these three result cells are untouched.
        # At n=2/3 the prefix has no deferred guards, so flags supply the rest.
        self.weights = tuple(_band_cell(k) for k in range(max(1, n - 3), n))
        if len(self.weights) < 3:
            self.weights += tuple(_flag_cell(k) for k in reversed(range(n)))[
                : 3 - len(self.weights)
            ]

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
        if level == self.n - 2:
            start = self.builder.count
            bias, z, y, yz = anf_coefficients(self.truth_table[lo:hi])
            if bias ^ (on == "0"):
                self.builder.flip(result)
            for cell, coefficient in zip(self.weights, (y, z, yz), strict=True):
                if coefficient:
                    self.builder.flip(cell)
            return _Cost(self.builder.count - start)
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

    def emit_paired_roots(self, prefix: _Cost[int]) -> int:
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
        return self.head + prefix.evaluate(decoder.pair_tails) + 1


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
    negate: bool = False,
    complement: bool = False,
) -> tuple[TemplateLayout, int]:
    """Emit one order's template; level ``k`` tests input ``perm[k]``.

    ``truth_table`` is already permuted.  Level ``k`` keeps its flag in
    cell ``3 k + 1``.  Answers are XORed into one cell per band of
    ``band`` levels, counted up from the leaves: a band's top level
    ``k`` owns cell ``3 k + 2`` and transfers it into its parent's cell
    when done, so a flip travels at most ``3 band`` cells and a node costs
    O(1) either way.  An arm whose lower half is constant needs no flag:
    that constant is flipped in first and the upper arm built inverted, so
    a four-row leaf emits the Davio coefficients instead of splitting its
    last two inputs. ``negate`` flips every input cell once first;
    ``complement`` flips cell 2 last, so the tree's table is the answer's complement.
    """
    n = _validate_truth_table(truth_table)
    if band != BAND:
        raise ValueError("Davio coefficients require five-level bands")
    ids = subtree_ids(truth_table)
    builder = _Builder(STRIDE * n)
    builder.count = len(_INPUT) * n
    if negate:
        for cell in reversed(range(n)):
            builder.flip(STRIDE * cell)
    head = builder.count
    if paired_roots and (n < 4 or shared_blocks):
        raise ValueError(
            "paired roots need two retired levels and no other definitions"
        )
    _check_definitions(n, shared_blocks, flag_levels)
    all_keys = {(depth, ids[depth][row >> (n - depth)]) for depth, row in shared_blocks}
    if len(all_keys) != len(shared_blocks):
        raise ValueError("deferred definitions must name distinct residuals")
    if n < 4:
        # The short prefix needs no deferred stage; its weights use level flags.
        shared_blocks = ()
        flag_levels = ()
        paired_roots = ()
    blocks = shared_blocks
    pending_levels = flag_levels or tuple(depth for depth, _ in blocks)
    selected = {
        (depth, ids[depth][row >> (n - depth)]): i
        for i, (depth, row) in enumerate(blocks)
    }
    pairs = dict(paired_roots)
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
        head,
    )

    def tail() -> int:
        # y adds A and moves C into B; z then adds B. All loops clear on entry.
        start = builder.count
        if n >= 2 and constant_output(truth_table) is None:
            a, b, c = tree.weights
            y, z = (STRIDE * perm[-2], STRIDE * perm[-1])
            builder.loop(y)
            builder.loop(a)
            builder.flip(ANSWER)
            builder.end(a)
            builder.loop(c)
            builder.flip(b)
            builder.end(c)
            builder.end(y)
            builder.loop(z)
            builder.loop(b)
            builder.flip(ANSWER)
            builder.end(b)
            builder.end(z)
            for cell in (a, b, c):
                builder.loop(cell)
                builder.end(cell)
        return builder.count - start

    prefix = tree.arm(-1, 0, len(truth_table), ANSWER, "1")
    if pairs:
        cost = tree.emit_paired_roots(prefix)
        cost += tail()
        return _closed(builder, n, cost, complement=complement)
    empty_tails = dict.fromkeys([None, *range(len(blocks))], 0)
    cost = head + prefix.evaluate(empty_tails)
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
        cost = head + prefix.evaluate(tails) + 1
    cost += tail()
    return _closed(builder, n, cost, complement=complement)


def _closed(
    builder: _Builder, inputs: int, cost: int, *, complement: bool
) -> tuple[TemplateLayout, int]:
    """Render input slots and append the optional closing answer flip."""
    tail = move_text(builder.at, ANSWER, ">", "<") + "*" if complement else ""
    layout = layout_fragments((*(_INPUT,) * inputs, "".join(builder.code), tail))
    return layout, cost + len(tail)


def _same_layout(template: str, plain: str, layout: Callable[[int], Any]) -> bool:
    """Newlines carry no commands: compare the narrow layouts without them."""
    for width in (1, 4):
        if template.replace("\n", "") == str(layout(width)).replace("\n", ""):
            return True
    return same_up_to_wrapping(template, plain)


def smallfuck_request(request: GenerationRequest) -> TemplateLayout:
    """Emit source through the declared generation request interface."""
    return _layout(request.table, request.width)


def smallfuck_balance_request(request: BalanceRequest) -> TemplateLayout:
    """Compare fits using the full and narrow setter layouts."""
    default = request.source
    if not isinstance(default, TemplateLayout):
        raise TypeError("balancing needs a rendered template with slots")
    return min(
        default,
        _WRAPPER.fit_template(default, minimum=len(_INPUT)),
        _WRAPPER.fit_template(_narrow(default), maximum=len(_INPUT) - 1),
        key=lambda layout: balance_score(layout.source),
    )
