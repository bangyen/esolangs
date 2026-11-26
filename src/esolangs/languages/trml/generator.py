"""Select a leaf of a prefix tree by consuming source-bound input bits.

Root rewrites select a child, discard an ignored input, or unwrap the leaf.
No other position matches a rule.

Size:
    At most 146 + 2T + 2n characters for T rows and n inputs; n=4 parity: 186 chars.
"""

from collections.abc import Iterator

from esolangs.generation.helpers import _validate_truth_table, constant_span_test
from esolangs.generation.projection import essential_inputs, read_at
from esolangs.generation.requests import GenerationRequest
from esolangs.generation.template import (
    InputSlot,
    TemplateLayout,
    TemplateToken,
    layout_fragments,
)

_HEADER = (
    "0;1;N;C(b)(r);D(b)(r);P(a)(b);Z(r)(t);"
    "ZC0(r)P(a)(b):Z(r)(a);ZC1(r)P(a)(b):Z(r)(b);ZD(b)(r)(t):Z(r)(t);ZC(b)(r)0:Z(r)0;ZC(b)(r)1:Z(r)1;ZN(a):(a);$"
)


def _fragments(table: str) -> Iterator[TemplateToken]:
    arity = len(table).bit_length() - 1
    used = essential_inputs(table, arity)
    selected = set(used)
    yield _HEADER + "Z"
    for slot in range(arity):
        yield "C" if slot in selected else "D"
        yield InputSlot(1)
    yield "N"
    if len(used) != arity:
        table = read_at(table, used, arity)

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
    """Render one source slot per input and a leaf per row."""
    _validate_truth_table(truth_table)
    return layout_fragments(_fragments(truth_table), char="@")


def trml_request(request: GenerationRequest) -> TemplateLayout:
    """Render the requested Boolean table."""
    return trml(request.table)
