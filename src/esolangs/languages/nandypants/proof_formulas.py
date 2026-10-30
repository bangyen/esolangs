"""Snapshot-bit bounds."""

import re

_TOKEN = re.compile(r"\d+|[{}<>^v\\/]")


def workspace(n: int, p: str) -> int:
    """The stated workspace bound, evaluated for n and the program."""
    bl = int.bit_length
    return bl(len(_TOKEN.findall(p)) - 1) + bl(n) + 16
