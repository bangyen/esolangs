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

from collections.abc import Callable
from functools import cache, partial
from itertools import pairwise

from esolangs.generation.helpers import (
    _validate_truth_table,
    in_input_order,
    move_text,
)
from esolangs.generation.lookup import constant_output
from esolangs.generation.requests import BalanceRequest, GenerationRequest, TruthTable
from esolangs.generation.shared_block import (
    FoldedTree,
    RepeatedSpans,
    _repeated_blocks,
    repeated_bank,
    repeated_blocks,
)
from esolangs.generation.template import InputSlot, TemplateLayout, layout_fragments
from esolangs.generation.wrap import TokenWrapper, balance_score
from esolangs.languages.smallfuck._tree import _INPUT, BAND, PAIR, _smallfuck_tree

_NARROW_INPUT = InputSlot(1, ("x", "*"))
_WRAPPER = TokenWrapper(r"[\s\S]")


def smallfuck(truth_table: str, width: int | None = None) -> str:
    """Return a Smallfuck template whose final tape cell 2 is the answer."""
    return _layout(TruthTable(truth_table), width).source


def _layout(table: TruthTable, width: int | None) -> TemplateLayout:
    truth_table = table.bits
    analyze = cache(partial(FoldedTree.build, include_single=True))
    natural = in_input_order(truth_table, partial(_smallfuck_ordered, analyze=analyze))
    n = table.arity
    # A chain of ifs is cheap and an else is not, so AND-like tables beat their
    # OR-like duals; the reversed table behind a prologue that flips every
    # input cell once (the setters stay as they are) reaches the cheap polarity.
    # Likewise the complement behind a closing flip of cell 2.
    flipped = "".join("10"[int(bit)] for bit in truth_table)
    twins = [
        in_input_order(
            polarity[::-1] if negate else polarity,
            partial(
                _smallfuck_ordered,
                analyze=analyze,
                negate=negate,
                complement=complement,
            ),
        )
        for polarity, complement in ((truth_table, False), (flipped, True))
        for negate in (False, True)
        if negate or complement
    ]
    natural = min(natural, *twins, key=lambda layout: len(layout.source))
    if n >= 3 and constant_output(truth_table) == "1":
        # Cell 2 is outside the input walk: set it before walking away.
        natural = layout_fragments((">>*<<", *(_INPUT,) * n))
    if (form := table.affine()) is not None and any(form.coefficients):
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
    analyze: Callable[[str], FoldedTree] | None = None,
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
    analysis = (
        FoldedTree.build(table, include_single=True)
        if analyze is None
        else analyze(table)
    )
    repeats = [block for block in analysis.repeats if block[2] > 0]
    forms = []
    # Historical pre-Davio measurements.
    # The bank: random 0%, majority +14.1% at n=10; per-level: parity +40-130%.
    plans = dict.fromkeys(
        [
            (repeated_blocks(table, repeats=repeats), ()),
            repeated_bank(table, ranked=False, repeats=repeats),
        ]
    )
    # Paired roots: random +15.9/+20.5/+23.2% at n=9/10/11 (12 tables),
    # +5.7% at n=8, 0% below.
    paired = _paired_roots(table, spans=analysis.repeats)
    band = BAND
    forms.append(
        _smallfuck_tree(
            table,
            perm,
            band=band,
            negate=negate,
            complement=complement,
            analysis=analysis,
        )
    )
    for blocks, flags in plans:
        if blocks:
            forms.append(
                _smallfuck_tree(
                    table,
                    perm,
                    analysis=analysis,
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
                analysis=analysis,
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


def _paired_roots(
    table: str, *, spans: RepeatedSpans | None = None
) -> tuple[tuple[int, int], ...]:
    """Return repeated two-input functions, identifying complements."""
    n = _validate_truth_table(table)
    if n < 4:
        return ()
    pairs: dict[int, tuple[int, int]] = {}
    found = _repeated_blocks(table, include_single=True) if spans is None else spans
    for depth, row, saving in found:
        if depth == n - 2:
            word = int(table[row : row + 4], 2)
            canonical = min(word, word ^ 15)
            previous, first = pairs.get(canonical, (0, row))
            pairs[canonical] = (previous + saving // 4 + 1, first)
    return tuple((code, row) for code, (copies, row) in pairs.items() if copies > 1)


def _same_layout(template: str, plain: str, _layout: object) -> bool:
    """Compare commands after removing layout newlines."""
    return template.replace("\n", "") == plain.replace("\n", "")


def smallfuck_request(request: GenerationRequest) -> TemplateLayout:
    """Emit source through the declared generation request interface."""
    return _layout(request.truth_table, request.width)


def smallfuck_balance_request(request: BalanceRequest) -> TemplateLayout:
    """Compare fits using the full and narrow setter layouts."""
    default = request.template_source()
    return min(
        default,
        _WRAPPER.fit_template(default, minimum=len(_INPUT)),
        _WRAPPER.fit_template(_narrow(default), maximum=len(_INPUT) - 1),
        key=lambda layout: balance_score(layout.source),
    )
