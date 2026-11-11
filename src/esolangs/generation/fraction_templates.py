"""Templates with input exponents in a whitespace-delimited fraction program."""

from collections.abc import Iterable

from esolangs.generation.template import (
    InputSlot,
    TemplateLayout,
    TemplateToken,
    layout_fragments,
)
from esolangs.generation.wrap import wrap_space_delimited

_EXPONENT = InputSlot(1)


def fraction_template(
    inputs: Iterable[int],
    fractions: list[str],
    *,
    root: str = "",
    factors: Iterable[str] = (),
) -> TemplateLayout:
    """Emit the initial product followed by its fractions."""
    parts: list[TemplateToken] = [root] if root else []
    for prime in inputs:
        parts.extend((f"*{prime}^" if parts else f"{prime}^", _EXPONENT))
    parts.extend(f"*{factor}" for factor in factors)
    if fractions:
        parts.append(" " + " ".join(fractions))
    return layout_fragments(parts)


def wrap_fractions(layout: TemplateLayout, width: int | None) -> TemplateLayout:
    """Replace separators in a single-space layout, preserving slot offsets."""
    if width is None:
        return layout
    return TemplateLayout(wrap_space_delimited(layout.source, width), layout.spans)
