"""Text generator for Super SNUSP."""

from esolangs.tools.text.helpers import _require_bytes
from esolangs.tools.wrap import shortest

__all__ = ["super_snusp"]


def super_snusp(text: str) -> str:
    """Build a Super SNUSP program that emits the byte string ``text``.

    Letter opcodes already load their ASCII value, so alphabetic bytes cost
    just the opcode and ``.``.  For every byte, choose the shorter of that
    direct load (a letter opcode or decimal literal) and a signed delta from
    the retained output cell.  The explicit START marker also gives an empty
    string a runnable, immediately-halting program.
    """
    _require_bytes(text, "Super SNUSP")
    program = ['"']
    current = 0
    for char in text:
        value = ord(char)
        direct = (char if char.isascii() and char.isalpha() else str(value)) + "."
        delta = ")" * (value - current) if value >= current else "(" * (current - value)
        program.append(shortest(direct, delta + "."))
        current = value
    return "".join(program)
