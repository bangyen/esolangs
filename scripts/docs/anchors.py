"""GitHub heading slugs and the link targets a Markdown file offers.

Shared by the docs gate (``checks/check_docs.py``) and the proof
manifest's evidence check, so the two agree on what an anchor is.
"""

from __future__ import annotations

import re

_MARKUP = re.compile(
    r"(?P<fenced>^(?P<fence>```|~~~)[\s\S]*?^(?P=fence))"
    r"|(?P<comment><!--[\s\S]*?(?:-->|\Z))"
    r"|(?P<inline>(?<!`)(?P<ticks>`+)(?!`)[^\n]*?(?<!`)(?P=ticks)(?!`))"
    r"|(?P<escape>\\[\\<`])",
    re.MULTILINE,
)
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

    def mask(match: re.Match[str]) -> str:
        kind = match.lastgroup
        if kind in {"fenced", "comment"} or (inline_code and kind == "inline"):
            return re.sub(r"[^\n]", " " if keep_columns else "", match[0])
        return match[0]

    # Match constructs in source order so a literal opener inside a code
    # span or fenced block never starts a comment outside it.
    return _MARKUP.sub(mask, text)


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
