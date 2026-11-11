"""Snapshot-bit bounds."""

import re

_TOKEN = re.compile(r"\d+|[{}<>^v\\/]")


def workspace_terms(n: int, program: str) -> dict[str, int]:
    """Count tokens and identify the constant-prefix workspace."""
    source = "".join(program.split())
    return {
        "R": len(_TOKEN.findall(program)),
        "C": int(source.startswith("/" * (8 * n))),
    }
