"""Text generator for Super SNUSP."""

from esolangs.tools.text.helpers import _require_bytes

__all__ = ["super_snusp"]


def super_snusp(text: str) -> str:
    """Build a Super SNUSP program that emits the byte string ``text``.

    Letter opcodes already load their ASCII value, so alphabetic bytes cost
    just the opcode and ``.``.  Every other byte is loaded by its decimal
    literal.  Each output resets the literal parser, which makes adjacent
    decimal values independent.  The explicit START marker also gives an
    empty string a runnable, immediately-halting program.
    """
    _require_bytes(text, "Super SNUSP")
    program = ['"']
    for char in text:
        program.append(char if char.isascii() and char.isalpha() else str(ord(char)))
        program.append(".")
    return "".join(program)
