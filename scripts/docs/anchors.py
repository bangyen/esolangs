"""GitHub heading slugs and the link targets a Markdown file offers.

Shared by the docs gate (``checks/check_docs.py``) and the proof
manifest's evidence check, so the two agree on what an anchor is.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

_MARKUP = re.compile(
    r"(?P<fenced>^ {0,3}(?:(?P<backticks>`{3,})[^`\n]*|(?P<tildes>~{3,})[^\n]*)$)"
    r"|(?P<comment><!--)"
    r"|(?P<inline>(?<!`)(?P<ticks>`+)(?!`)[^\n]*?(?<!`)(?P=ticks)(?!`))"
    r"|(?P<escape>\\[\\<`])",
    re.MULTILINE,
)
_FENCE_END = re.compile(r"^ {0,3}(`{3,}|~{3,})[ \t]*\r?$", re.MULTILINE)
_HEADING = re.compile(r" {0,3}#{1,6}(?:[ \t]+(.*?)[ \t]*#*[ \t]*)?")
_UNDERLINE = re.compile(r" {0,3}(?:=+|-+)[ \t]*")
_THEMATIC = re.compile(r" {0,3}(?:(?:-[ \t]*){3,}|(?:\*[ \t]*){3,}|(?:_[ \t]*){3,})")
_BLOCK_START = re.compile(
    r" {0,3}(?:>|(?:[-+*]|[0-9]{1,9}[.)])(?:[ \t]|$)|\[[^\]]+\]:|<(?:/?[a-zA-Z]|[!?]))"
)
_LIST_ITEM = re.compile(r" {0,3}(?:[-+*]|[0-9]{1,9}[.)])(?P<padding> +|$)")
_EXPLICIT_ANCHOR = re.compile(r"<a\s+(?:id|name)=\"([^\"]+)\"")


def slug(heading: str) -> str:
    """Return GitHub's anchor slug for a heading.

    Lowercase; drop everything but letters, digits, underscores, hyphens and
    spaces; turn spaces into hyphens.  ``&`` and the like vanish rather than
    becoming ``amp``, which is what ``github-slugger`` does.
    """
    text = heading.strip().lower()
    text = re.sub(r"[^\w\- ]", "", text, flags=re.UNICODE)
    return text.replace(" ", "-")


class _IndentedBlocks:
    """Track paragraph and list indentation before reading inline markup."""

    def __init__(self) -> None:
        self.paragraph = False
        self.margins: list[int] = []

    def code(self, line: str) -> bool:
        line = line.removesuffix("\r").expandtabs(4)
        content = line.lstrip(" ")
        if not content:
            self.paragraph = False
            return False
        indent = len(line) - len(content)
        depth = len(self.margins)
        while depth and self.margins[depth - 1] > indent:
            depth -= 1
        margin = self.margins[depth - 1] if depth else 0
        content = line[margin:]
        if indent >= margin + 4 and not self.paragraph:
            del self.margins[depth:]
            return True
        if (
            _HEADING.fullmatch(content)
            or _THEMATIC.fullmatch(content)
            or (self.paragraph and _UNDERLINE.fullmatch(content))
            or (indent < margin + 4 and content.lstrip(" ").startswith("<!--"))
        ):
            del self.margins[depth:]
            self.paragraph = False
        elif item := _LIST_ITEM.match(content):
            del self.margins[depth:]
            padding = len(item["padding"])
            has_body = bool(content[item.end() :])
            offset = (
                item.end() if has_body and padding <= 4 else item.start("padding") + 1
            )
            self.margins.append(margin + offset)
            self.paragraph = has_body and padding <= 4
            return has_body and padding > 4
        else:
            if not self.paragraph:
                del self.margins[depth:]
            self.paragraph = True
        return False


def _markup_spans(text: str) -> Iterator[tuple[int, int, str]]:
    """Find opaque spans in source order, including literal comment openers."""
    blocks = _IndentedBlocks()
    position = 0
    while position < len(text):
        newline = text.find("\n", position)
        line_end = len(text) if newline == -1 else newline
        if (position == 0 or text[position - 1] == "\n") and blocks.code(
            text[position:line_end]
        ):
            yield position, line_end, "block"
            position = line_end + 1
            continue
        match = _MARKUP.search(text, position, line_end)
        if match is None:
            position = line_end + 1
            continue
        kind = match.lastgroup
        position = match.end()
        if kind == "fenced":
            fence = match["backticks"] or match["tildes"]
            # Shorter runs and runs with trailing text are literal code.
            position = next(
                (
                    end.end()
                    for end in _FENCE_END.finditer(text, position)
                    if end[1][0] == fence[0] and len(end[1]) >= len(fence)
                ),
                len(text),
            )
            blocks.paragraph = False
            yield match.start(), position, "block"
        elif kind == "comment":
            end = text.find("-->", position)
            position = len(text) if end == -1 else end + 3
            yield match.start(), position, kind
        elif kind == "inline":
            yield match.start(), position, kind


def mask_hidden(
    text: str,
    *,
    code_blocks: bool = True,
    inline_code: bool = False,
    keep_columns: bool = True,
) -> str:
    """Hide comments and selected code while retaining line boundaries."""
    parts: list[str] = []
    cursor = 0
    for start, end, kind in _markup_spans(text):
        if kind == "comment" or (code_blocks if kind == "block" else inline_code):
            parts.append(text[cursor:start])
            parts.append(re.sub(r"[^\n]", " " if keep_columns else "", text[start:end]))
            cursor = end
    parts.append(text[cursor:])
    return "".join(parts)


def _heading_titles(text: str) -> Iterator[str]:
    """Read ATX and Setext headings in document order."""
    paragraph: list[str] = []
    in_block = False
    for line in text.splitlines():
        if match := _HEADING.fullmatch(line):
            yield match[1] or ""
        elif paragraph and _UNDERLINE.fullmatch(line):
            yield "\n".join(paragraph)
        elif not line.strip() or _THEMATIC.fullmatch(line):
            pass
        elif _BLOCK_START.match(line):
            paragraph.clear()
            in_block = True
            continue
        else:
            if not in_block and (paragraph or not line.startswith(("    ", "\t"))):
                paragraph.append(line.strip())
            continue
        paragraph.clear()
        in_block = False


def anchors(text: str) -> set[str]:
    """Return every heading and explicit anchor a reader can link to in ``text``."""
    text = mask_hidden(text, keep_columns=False)
    headings: set[str] = set()
    next_suffix: dict[str, int] = {}
    for title in _heading_titles(text):
        base = heading = slug(title)
        suffix = next_suffix.get(base, 1)
        while heading in headings:
            heading = f"{base}-{suffix}"
            suffix += 1
        next_suffix[base] = suffix
        headings.add(heading)
    # Explicit anchors do not take part in heading suffix allocation.
    return headings | {m.group(1) for m in _EXPLICIT_ANCHOR.finditer(text)}
