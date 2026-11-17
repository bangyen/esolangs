"""moar cheese :3 Boolean program generator: input bits filter a queued table.

The program enqueues the first essential input's bit, ``n`` or ``y``, then
the essential inputs' table as bytes ``0``/``1``.  Each essential input is
dequeued and run.  Its body defines how the table bytes act when they run:
a kept byte enqueues itself and a dropped byte does nothing.  The next
input's bit is enqueued behind the table, so once the pass has run every
byte, that bit is at the front.  The final queue is the answer byte.

- Lookup: a bit keeps one half, ``F`` for the first and ``S`` for the
  second.  Doubling names run each half's dequeues, so a pass costs O(1)
  characters and the table 4 a byte.
- Symmetric tables (by popcount, m + 1 bytes and a marker ``M``): a bytes
  run the next one, so a pass runs itself up to the marker.  A 1 drops the
  first byte.  A last pass keeps the front byte and drops the rest.

An ignored input is a bare instruction, ``n`` or ``y``.  It runs just
before a dispatch, which redefines whatever it defines.

Size:
    4 characters a table byte plus 22 an input: O(T) characters;
    n=4 parity: 163 chars, n=10 random 1847: 4,374 chars

Decisions:
    The screening probe's tree, which redefines the dispatch at each node,
    emitted 846 characters at n=6 against 446.
"""

from collections.abc import Callable

from esolangs.generation.helpers import (
    WeightedLookup,
    _validate_truth_table,
    input_weights,
    symmetric_weights,
)
from esolangs.generation.requests import BalanceRequest, GenerationRequest
from esolangs.generation.template import InputSlot, TemplateLayout, layout_fragments

_SLOT = InputSlot(1)
#: Names the doubling dequeues may use: none of the fixed ones, ``$`` or
#: a parenthesis.
_POOL = [
    c
    for c in "abcdefghijklmopqrstuvwxzABCDEGHIJLNOPQRTUVWXY23456789"
    if c not in "nyFSKMZ01"
]


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
    """Halve the table once per essential input."""
    m = sum(1 for w in lookup.weights if w)
    keep, drop = "0((0)) 1((1))", "0() 1()"
    names = ["()", *_POOL[: m - 1]]
    doubling = [f"{names[j]}({names[j - 1]} {names[j - 1]})" for j in range(1, m)]
    head = [
        _enqueue(lookup.table),
        f" n(F({keep}) S({drop})) y(F({drop}) S({keep}))",
        *(" " + d for d in doubling),
    ]
    return _passes(
        lookup.weights, head, lambda k: f"F {names[m - 1 - k]} S {names[m - 1 - k]}", ""
    )


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
    candidates = [_lookup(weighted)]
    if (symmetric := symmetric_weights(truth_table, n)) is not None:
        candidates.append(_symmetric(symmetric))
    return min(candidates, key=lambda layout: len(layout.source))


def moar_cheese_3(truth_table: str) -> str:
    """Build a template whose final queue is ``truth_table[row]``."""
    return _layout(truth_table).source


def moar_cheese_3_request(request: GenerationRequest) -> TemplateLayout:
    """Emit the template through the declared generation request interface."""
    return _layout(request.table)


def moar_cheese_3_balance_request(request: BalanceRequest) -> TemplateLayout:
    """Keep the default: a program is one line, with no break to move."""
    if not isinstance(request.source, TemplateLayout):
        raise TypeError("moar cheese :3 balancing needs a rendered template")
    return request.source
