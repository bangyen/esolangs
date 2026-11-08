"""Shared Balik page-diagram source construction."""


def _page_loop(before: str, body: str, after: str) -> str:
    """The page's ``abc[def]ghi`` diagram at depth 0."""
    return "\n".join(
        [
            before + "**" + body + "**" + after,
            "   @@   @@",
            "  *       *",
            "  ***   ***",
        ]
    )
