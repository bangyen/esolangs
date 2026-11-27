"""moar cheese :3 Boolean program generator: input bits filter a queued table.

The program enqueues the first essential bit, then the lookup bytes. Each
queued bit configures the next pass. The next input is enqueued behind
the table and reaches the front when that pass ends.

- Lookup: each byte holds two answers. A pass keeps one half, using
  doubling names to count dequeues. The final bit decodes the sole byte.
- Symmetric tables: each 1 drops one popcount entry. A marker ends each
  pass, and the last pass keeps only the front byte.

Ignored input instructions run before dispatch and can redefine the byte
rules. The queued bit sets the rules again before any table byte runs.

Size:
    Two characters per table bit plus O(n) setup and passes: O(T);
    n=4 parity: 163 chars, n=10 random 1847: 2,352 chars

Decisions:
    The screening probe's tree, which redefines the dispatch at each node,
    emitted 846 characters at n=6 against 446.
"""

from collections.abc import Callable
from itertools import pairwise

from esolangs.generation.helpers import _validate_truth_table
from esolangs.generation.projection import (
    WeightedLookup,
    input_weights,
    symmetric_lookup,
)
from esolangs.generation.requests import BalanceRequest, GenerationRequest
from esolangs.generation.template import InputSlot, TemplateLayout, layout_fragments
from esolangs.generation.token_balance import balanced_token_width
from esolangs.generation.wrap import balance_score
from esolangs.languages.moar_cheese_3.descriptor import PAIR

_SLOT = InputSlot(1, PAIR)
#: Names the doubling dequeues may use: none of the fixed ones, ``$`` or
#: a parenthesis.
_POOL = [
    c
    for c in "abcdefghijklmopqrstuvwxzABCDEGHIJLNOPQRSTUVWXY456789"
    if c not in "nyFKMZ0123"
]

_PACKED = "0123"
_KEEP = " ".join(f"{c}(({c}))" for c in _PACKED)
_DROP = " ".join(f"{c}()" for c in _PACKED)
_HALVE = f"K({_KEEP}) Z({_DROP}) n(K F(Z)) y(Z F(K))"
_DECODE = "0((0)) 3((1)) n(1((0)) 2((1))) y(1((1)) 2((0)))"


def _enqueue(chars: str) -> str:
    return " ".join(f"({c})" for c in chars)


def _passes(
    weights: tuple[int, ...], head: list[str], each: Callable[[int], str], tail: str
) -> TemplateLayout:
    """Lay out the slots and passes, essential inputs in order.

    ``head`` holds the setup after the first essential slot.  Pass k runs
    ``()`` (the dispatch), the next essential slot and ``each(k)``.
    ``tail`` follows the last pass.
    """
    essential = [i for i, w in enumerate(weights) if w]
    parts: list[str | InputSlot] = []
    for _ in range(essential[0]):
        parts += [_SLOT, " "]
    parts += ["(", _SLOT, ") ", *head]
    for k, i in enumerate(essential):
        nxt = essential[k + 1] if k + 1 < len(essential) else len(weights)
        # Ignored inputs between this one and the next run before this
        # dispatch, which redefines whatever they define.
        for _ in range(i + 1, nxt):
            parts += [" ", _SLOT]
        parts.append(" ()")
        if k + 1 < len(essential):
            parts += [" (", _SLOT, ")"]
        parts.append(" " + each(k))
    parts.append(tail)
    return layout_fragments(parts)


def _lookup(lookup: WeightedLookup) -> TemplateLayout:
    """Halve the packed queue and decode the last pair."""
    m = sum(bool(w) for w in lookup.weights)
    packed = "".join(
        _PACKED[int(lookup.table[at : at + 2], 2)]
        for at in range(0, len(lookup.table), 2)
    )
    names = ["()", *_POOL[: max(0, m - 2)]]
    head = [_enqueue(packed), " " + (_HALVE if m > 1 else _DECODE)]
    head.extend(f" {b}({a} {a})" for a, b in pairwise(names))

    def stage(k: int) -> str:
        if k == m - 1:
            return "()"
        unit = names[m - 2 - k]
        finish = " " + _DECODE if k == m - 2 else ""
        return f"{unit} F {unit}" + finish

    return _passes(lookup.weights, head, stage, "")


def _symmetric(lookup: WeightedLookup) -> TemplateLayout:
    """Each 1 drops the front byte; a last pass keeps only the front."""
    head = [
        _enqueue(lookup.table + "M"),
        " K(0((0) ()) 1((1) ())) M((M)) n(K) y(0(K ()) 1(K ()))",
    ]
    tail = " Z(0(()) 1(()) M()) 0((0) Z ()) 1((1) Z ()) ()"
    return _passes(lookup.weights, head, lambda _: "()", tail)


def _layout(truth_table: str) -> TemplateLayout:
    n = _validate_truth_table(truth_table)
    weighted = input_weights(truth_table, n)
    if not any(weighted.weights):
        bare: list[str | InputSlot] = [_SLOT, " "]
        return layout_fragments([*bare * n, f"({truth_table[0]})"])
    if (symmetric := symmetric_lookup(weighted)) is not None:
        return _symmetric(symmetric)
    return _lookup(weighted)


def moar_cheese_3_request(request: GenerationRequest) -> TemplateLayout:
    """Emit the template through the declared generation request interface."""
    return _layout(request.table)


def _fold(source: str, breaks: list[int], width: int) -> str:
    """Turn the last fitting separator of each over-wide line into a newline."""
    chars = list(source)
    start, last = 0, None
    for stop in [*breaks, len(source)]:
        if stop - start > width and last is not None:
            chars[last] = "\n"
            start = last + 1
        last = stop
    return "".join(chars)


def moar_cheese_3_balance_request(request: BalanceRequest) -> TemplateLayout:
    """Fold at separators, or keep the line if that is squarer.

    A newline replaces a space one for one, so every slot keeps its offset;
    the space inside ``( )`` is a byte, not a separator.
    """
    layout = request.template_source()
    source = layout.source
    breaks = [
        i for i, c in enumerate(source) if c == " " and source[i - 1 : i + 2] != "( )"
    ]
    words = [
        source[a + 1 : b]
        for a, b in zip([-1, *breaks], [*breaks, len(source)], strict=True)
    ]
    width = balanced_token_width(words, " ")
    folded = TemplateLayout(_fold(source, breaks, width), layout.spans, layout.setters)
    return min(layout, folded, key=lambda candidate: balance_score(candidate.source))
