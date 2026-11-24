"""GitHub heading slugs and the link targets a Markdown file offers.

Shared by the docs gate (``checks/check_docs.py``) and the proof
manifest's evidence check, so the two agree on what an anchor is.
"""

from __future__ import annotations

import re

_MARKUP = re.compile(
    r"(?P<fenced>^ {0,3}(?:(?P<backticks>`{3,})[^`\n]*|(?P<tildes>~{3,})[^\n]*)$)"
    r"|(?P<comment><!--[\s\S]*?(?:-->|\Z))"
    r"|(?P<inline>(?<!`)(?P<ticks>`+)(?!`)[^\n]*?(?<!`)(?P=ticks)(?!`))"
    r"|(?P<escape>\\[\\<`])",
    re.MULTILINE,
)
_FENCE_END = re.compile(r"^ {0,3}(`{3,}|~{3,})[ \t]*\r?$", re.MULTILINE)
_HEADING = re.compile(r"^#{1,6}\s+(.*?)\s*#*\s*$", re.MULTILINE)
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


def mask_hidden(
    text: str, *, inline_code: bool = False, keep_columns: bool = True
) -> str:
    """Hide comments and code blocks while retaining line boundaries."""
    # Match constructs in source order so a literal opener inside a code
    # span or fenced block never starts a comment outside it.
    parts: list[str] = []
    cursor = 0
    while (match := _MARKUP.search(text, cursor)) is not None:
        parts.append(text[cursor : match.start()])
        kind = match.lastgroup
        cursor = match.end()
        if kind == "fenced":
            fence = match["backticks"] or match["tildes"]
            # Shorter runs and runs with trailing text are literal code.
            cursor = next(
                (
                    end.end()
                    for end in _FENCE_END.finditer(text, cursor)
                    if end[1][0] == fence[0] and len(end[1]) >= len(fence)
                ),
                len(text),
            )
        chunk = text[match.start() : cursor]
        if kind in {"fenced", "comment"} or (inline_code and kind == "inline"):
            chunk = re.sub(r"[^\n]", " " if keep_columns else "", chunk)
        parts.append(chunk)
    parts.append(text[cursor:])
    return "".join(parts)


def anchors(text: str) -> set[str]:
    """Return every heading and explicit anchor a reader can link to in ``text``."""
    text = mask_hidden(text, keep_columns=False)
    headings = [slug(m.group(1)) for m in _HEADING.finditer(text)]
    found = set(headings)
    found |= {m.group(1) for m in _EXPLICIT_ANCHOR.finditer(text)}
    # GitHub disambiguates a repeated heading, but a repeated anchor is a
    # document bug rather than a link target, so only headings get suffixes.
    seen: dict[str, int] = {}
    for base in headings:
        count = seen.get(base, 0)
        seen[base] = count + 1
        if count:
            found.add(f"{base}-{count}")
    return found
