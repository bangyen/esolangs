"""Lay out literal source tokens and ordered Boolean input slots."""

from collections.abc import Iterable, Iterator, Sequence
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

    def fragments(self) -> Iterator[TemplateToken]:
        """Recover literal fragments and slots using their known positions."""
        position = 0
        for start, end in self.spans:
            yield self.source[position:start]
            yield InputSlot(end - start)
            position = end
        yield self.source[position:]

    def lines(self) -> Iterator["TemplateLayout"]:
        """Yield layouts for individual lines with offsets local to each line."""
        first = offset = 0
        for line in self.source.splitlines(keepends=True):
            end = offset + len(line)
            last = first
            while last < len(self.spans) and self.spans[last][0] < end:
                last += 1
            spans = tuple(
                (start - offset, stop - offset)
                for start, stop in self.spans[first:last]
            )
            yield TemplateLayout(line.removesuffix("\n"), spans)
            first, offset = last, end

    def tokens(self) -> Iterator[TemplateToken]:
        """Split only the literal fragments on whitespace."""
        for fragment in self.fragments():
            if isinstance(fragment, InputSlot):
                yield fragment
            else:
                yield from fragment.split()


def layout_fragments(
    parts: Iterable[TemplateToken], *, char: str = TEMPLATE_CHAR
) -> TemplateLayout:
    """Render literal fragments and record the positions of their input slots."""
    fragments: list[str] = []
    spans: list[tuple[int, int]] = []
    offset = 0
    for part in parts:
        end = offset + len(part)
        if isinstance(part, InputSlot):
            spans.append((offset, end))
            fragments.append(char * len(part))
        else:
            fragments.append(part)
        offset = end
    return TemplateLayout("".join(fragments), tuple(spans))


def layout_tokens(
    tokens: Sequence[TemplateToken],
    width: int | None = None,
    *,
    char: str = TEMPLATE_CHAR,
    separator: str = " ",
) -> TemplateLayout:
    """Wrap whole tokens and record slot positions as source is written."""
    fragments: list[str] = []
    spans: list[tuple[int, int]] = []
    offset = column = 0
    gap = len(separator)
    for token in tokens:
        size = len(token)
        if column:
            wrap = width is not None and column + gap + size > width
            fragments.append("\n" if wrap else separator)
            offset += 1 if wrap else gap
            column = 0 if wrap else column + gap
        if isinstance(token, InputSlot):
            spans.append((offset, offset + size))
            fragments.append(char * size)
        else:
            fragments.append(token)
        column += size
        offset += size
    return TemplateLayout("".join(fragments), tuple(spans))
