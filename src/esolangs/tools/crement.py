"""Prototype Boolean-function generator for Crement."""

from esolangs.exceptions import TruthTableError
from esolangs.tools.helpers import _validate_truth_table

__all__ = ["crement", "instantiate_crement"]

_PREFIX = "* Crement Boolean prototype"


def crement(truth_table: str) -> str:
    """Build a template specialized by :func:`instantiate_crement`.

    Crement has no input instruction, so the template records the table and
    one ``{Xi}`` slot per input.  Instantiation selects the row and emits a
    false jump for 0 or a self-jump for 1.
    """
    n = _validate_truth_table(truth_table)
    slots = "".join(f"{{X{i}}}" for i in range(n))
    return f"{_PREFIX}\n* {truth_table}\n* {slots}"


def instantiate_crement(template: str, bits: list[int]) -> str:
    """Specialize a Crement prototype template for ``bits``."""
    lines = template.splitlines()
    if len(lines) != 3 or lines[0] != _PREFIX:
        raise ValueError("not a Crement Boolean prototype template")
    table_line, slots_line = lines[1:]
    if not table_line.startswith("* ") or not slots_line.startswith("* "):
        raise ValueError("malformed Crement Boolean prototype template")
    truth_table = table_line[2:]
    n = _validate_truth_table(truth_table)
    if slots_line[2:] != "".join(f"{{X{i}}}" for i in range(n)):
        raise ValueError("malformed Crement input slots")
    if len(bits) != n or any(bit not in (0, 1) for bit in bits):
        raise TruthTableError(f"expected {n} Boolean input bits, got {bits!r}")

    row = sum(bit << (n - 1 - index) for index, bit in enumerate(bits))
    return "+J 0 1" if truth_table[row] == "1" else "+J 0 0"
