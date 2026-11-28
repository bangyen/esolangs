"""Consume source-bound bits with a prefix tree or a parity state.

Root rewrites select a child, discard an ignored input, or unwrap the leaf.
A parity state flips on a selected one. Only the root matches a rule.

Size:
    At most 146 + 2T + 2n characters for T rows and n inputs.
    Parity uses 121 + 2n characters. n=4 parity: 129 chars.
"""

from collections.abc import Iterator

from esolangs.generation.algebraic import parity_bias
from esolangs.generation.helpers import _validate_truth_table, constant_span_test
from esolangs.generation.projection import essential_inputs, read_at
from esolangs.generation.requests import GenerationRequest
from esolangs.generation.template import (
    InputSlot,
    TemplateLayout,
    TemplateToken,
    layout_fragments,
)
from esolangs.languages.trml.descriptor import PAIR

_INPUT_TERMS = "0;1;N;C(b)(r);D(b)(r);"
_TREE_HEADER = _INPUT_TERMS + (
    "P(a)(b);Z(r)(t);"
    "ZC0(r)P(a)(b):Z(r)(a);ZC1(r)P(a)(b):Z(r)(b);ZD(b)(r)(t):Z(r)(t);ZC(b)(r)0:Z(r)0;ZC(b)(r)1:Z(r)1;ZN(a):(a);$"
)

_PARITY_HEADER = _INPUT_TERMS + (
    "E(r);O(r);"
    "EC0(r):E(r);EC1(r):O(r);OC0(r):O(r);OC1(r):E(r);"
    "ED(b)(r):E(r);OD(b)(r):O(r);EN:0;ON:1;$"
)


def _fragments(table: str) -> Iterator[TemplateToken]:
    arity = len(table).bit_length() - 1
    used = essential_inputs(table, arity)
    if len(used) != arity:
        table = read_at(table, used, arity)
    bias = parity_bias(table) if used else None
    selected = set(used)
    yield _TREE_HEADER + "Z" if bias is None else _PARITY_HEADER + "EO"[bias]
    for slot in range(arity):
        yield "C" if slot in selected else "D"
        yield InputSlot(1, PAIR)
    yield "N"
    if bias is not None:
        return

    is_constant = constant_span_test(table)

    def write(start: int, stop: int) -> Iterator[str]:
        if is_constant(start, stop):
            yield table[start]
            return
        mid = (start + stop) // 2
        yield "P"
        yield from write(start, mid)
        yield from write(mid, stop)

    yield from write(0, len(table))


def trml(truth_table: str) -> TemplateLayout:
    """Render an ordered slot per input and the selected root rules."""
    _validate_truth_table(truth_table)
    return layout_fragments(_fragments(truth_table), char="@")


def trml_request(request: GenerationRequest) -> TemplateLayout:
    """Render the requested Boolean table."""
    return trml(request.table)
