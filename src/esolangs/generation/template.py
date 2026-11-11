"""Lay out literal source tokens and ordered Boolean input slots."""

from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from esolangs._bindings import TEMPLATE_CHAR


@dataclass(frozen=True, slots=True)
class InputSlot:
    """An input represented by two equal-width substitutions."""

    width: int

    def __len__(self) -> int:
        """Return the rendered width."""
        return self.width


type TemplateToken = str | InputSlot
type Spans = tuple[tuple[int, int], ...]


@dataclass(frozen=True, slots=True)
class TemplateLayout:
    """Rendered source with the positions of the input slots."""

    source: str
    spans: Spans

    def tokens(self) -> Iterator[TemplateToken]:
        """Recover whitespace-delimited tokens using known slot positions."""
        position = 0
        for start, end in self.spans:
            yield from self.source[position:start].split()
            yield InputSlot(end - start)
            position = end
        yield from self.source[position:].split()


def layout_tokens(
    tokens: Sequence[TemplateToken],
    width: int | None = None,
    *,
    char: str = TEMPLATE_CHAR,
) -> TemplateLayout:
    """Wrap whole tokens and record slot positions as source is written."""
    fragments: list[str] = []
    spans: list[tuple[int, int]] = []
    offset = column = 0
    for token in tokens:
        size = len(token)
        if column:
            wrap = width is not None and column + 1 + size > width
            fragments.append("\n" if wrap else " ")
            offset += 1
            column = 0 if wrap else column + 1
        if isinstance(token, InputSlot):
            spans.append((offset, offset + size))
            fragments.append(char * size)
        else:
            fragments.append(token)
        column += size
        offset += size
    return TemplateLayout("".join(fragments), tuple(spans))
