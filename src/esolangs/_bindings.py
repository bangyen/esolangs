"""Ordered source-template bindings, independent of Boolean synthesis."""

from collections.abc import Sequence

#: One ``(zero, one)`` pair per input, in name order: what a template's
#: runs are filled with.  Each pair is equal width, checked by
#: :func:`check_setters`, so the constant-width convention is a property
#: of the object rather than of every caller.
Setters = tuple[tuple[str, str], ...]


def check_setters(setters: Sequence[tuple[str, str]]) -> Setters:
    """Return ``setters`` as a tuple, refusing a pair of unequal width."""
    checked = tuple((zero, one) for zero, one in setters)
    for i, (zero, one) in enumerate(checked):
        if len(zero) != len(one):
            raise ValueError(
                f"input {i}'s setters differ in width ({len(zero)} against "
                f"{len(one)}), so the program's length would carry the bit"
            )
    return checked


#: The character a public template spells its inputs with, unless a
#: language declares another: outside every embedding language's alphabet.
TEMPLATE_CHAR = "$"


#: The first of the private-use characters a template is spelled with
#: while it is wrapped: input ``i`` is a run of ``chr(MARK + i)``, so a
#: wrapper sees every input as its own unbreakable token, even beside the
#: next, and the marks become the language's character afterwards.
MARK = 0xE000

#: The most inputs a template can carry marks for.
MOST_INPUTS = 64


def mark(i: int) -> str:
    """Return the character input ``i`` is spelled with while wrapping."""
    return chr(MARK + i)


def mark_runs(template: str, char: str, setters: Setters) -> str:
    """Return the template as a wrapper is handed it.

    Runs of ``char`` are each as long as their input's setters, so no
    separator is needed; each is re-spelled as its own :func:`mark`, the form
    a wrapper keeps whole.  ``char`` is the *language's* template character
    and cannot default to :data:`TEMPLATE_CHAR`: a language may embed on a
    character the global template uses, so scanning for the global one
    found an operator and read it as a one-character run.
    """
    out, position = [], 0
    for i, (start, end) in enumerate(runs(template, char, setters)):
        out.append(template[position:start] + mark(i) * (end - start))
        position = end
    return "".join(out) + template[position:]


def unmark(text: str, char: str, inputs: int) -> str:
    """Return ``text`` with every input's mark replaced by ``char``."""
    return text.translate({MARK + i: char for i in range(inputs)})


def runs(text: str, char: str, setters: Setters) -> list[tuple[int, int]]:
    """Return the ``[start, end)`` of each input's run in ``text``.

    Runs are consumed left to right in setter widths, and every ``char``
    must belong to one; a width-zero setter (an ignored input) has
    an empty run where the previous ended.
    """
    widths = [len(zero) for zero, _one in setters]
    spans: list[tuple[int, int]] = []
    position = 0
    for i, width in enumerate(widths):
        if width == 0:
            spans.append((position, position))
            continue
        start = text.find(char, position)
        if start < 0:
            raise ValueError(
                f"template has {i} run(s) of {char!r}, setters name {len(widths)}"
            )
        end = start + width
        if text[start:end] != char * width:
            raise ValueError(
                f"input {i}'s run of {char!r} at {start} is shorter than its "
                f"setter width {width}"
            )
        spans.append((start, end))
        position = end
    stray = text.find(char, position)
    if stray >= 0:
        raise ValueError(
            f"{char!r} at {stray} belongs to no input: {len(widths)} setter(s), "
            f"more runs than that"
        )
    return spans


def validate_spans(
    text: str,
    char: str,
    setters: Setters,
    spans: tuple[tuple[int, int], ...],
) -> None:
    """Check ordered, fixed-width source slots supplied by a renderer or file."""
    if not isinstance(spans, tuple) or len(spans) != len(setters):
        raise ValueError("template needs one span per input")
    position = covered = 0
    for span, (zero, _) in zip(spans, setters, strict=True):
        if not isinstance(span, tuple) or len(span) != 2:
            raise ValueError("template spans must be pairs of offsets")
        start, end = span
        width = len(zero)
        if (
            type(start) is not int
            or type(end) is not int
            or not position <= start <= end <= len(text)
            or end - start != width
            or text[start:end] != char * width
        ):
            raise ValueError(f"invalid template span {span!r}")
        position = end
        covered += width
    if text.count(char) != covered:
        raise ValueError("template has an unbound placeholder")


def fill_runs(
    text: str,
    char: str,
    setters: Setters,
    bits: Sequence[int],
    *,
    spans: Sequence[tuple[int, int]] | None = None,
) -> str:
    """Fill runs; supplied spans must already be validated for this source."""
    if len(bits) != len(setters):
        raise ValueError(f"expected {len(setters)} bits, got {len(bits)}")
    out: list[str] = []
    position = 0
    for (start, end), (zero, one), bit in zip(
        runs(text, char, setters) if spans is None else spans,
        setters,
        bits,
        strict=True,
    ):
        out.append(text[position:start])
        out.append(one if bit else zero)
        position = end
    out.append(text[position:])
    return "".join(out)
