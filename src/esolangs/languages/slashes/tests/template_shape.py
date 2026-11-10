"""Recognize the canonical source shapes emitted by the generator."""

import re

from esolangs._bindings import TEMPLATE_CHAR
from esolangs.languages.slashes.generator import (
    _CONSTANT,
    _DECODE,
    _IGNORE,
    _UNARY,
    _sweep_rules,
)


def _is_unfilled_template(code: str) -> bool:
    """Recognize canonical templates without reserving literal dollars in ///."""
    if TEMPLATE_CHAR in code and re.fullmatch(r"/[$ab]+//[01]", code):
        return True
    if code.startswith(_CONSTANT):
        data = code[len(_CONSTANT) :]
        return (
            len(data) > 1
            and data[-1] in "01"
            and TEMPLATE_CHAR in data[:-1]
            and not data[:-1].strip(TEMPLATE_CHAR + "ab")
        )
    prefix, delimiter, data = code.partition(_DECODE)
    slots, cursor, table = data.partition(">")
    if (
        not delimiter
        or not cursor
        or TEMPLATE_CHAR not in slots
        or not re.fullmatch(r"(?:X?[$ab])+", slots)
    ):
        return False
    if not re.fullmatch(r"(?:q[AB])*", table):
        return False
    ignored = slots.count("X")
    head = _IGNORE if ignored else ""
    read = len(slots) - 2 * ignored  # negative: more X than slots, not ours
    if read < 0 or len(table) != 2 << read:
        return False
    bits = table.replace("qA", "0").replace("qB", "1")
    return prefix == head + _UNARY + _sweep_rules(bits)
