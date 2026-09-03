"""Boolean-function generator for Super SNUSP.

The generator reads ASCII ``0``/``1`` values, normalizes them to bits, then
evaluates the truth table's algebraic normal form (ANF).  ANF is an XOR of
input products, which maps directly to Super SNUSP's ``^`` and ``&`` stack
operations and avoids the language's random ``=`` opcode entirely.
"""

from esolangs.tools.boolean.helpers import _validate_truth_table

__all__ = ["super_snusp"]


_TWO_INPUT_SHORT = {
    # These executed forms reuse 48 both to decode each input and to encode
    # the answer.  They beat the general ANF construction by keeping the
    # literal at the bottom of the stack rather than rebuilding it at the end.
    "0000": "48{,-> ,-<}.",
    "0011": "48{,-> ,-<^.",
    "0101": "48{,-> ,-<>^.",
    "0110": "48{,-> ,-<^{>^.",
    "0111": "48{,-> ,-<^{>|.",
}


def _anf_coefficients(truth_table: str) -> list[int]:
    """Return ANF coefficients indexed by the ordinary truth-table rows."""
    coefficients = [int(bit) for bit in truth_table]
    n = len(truth_table).bit_length() - 1
    for bit in range(n):
        for mask in range(len(coefficients)):
            if mask & (1 << bit):
                coefficients[mask] ^= coefficients[mask ^ (1 << bit)]
    return coefficients


def _move(start: int, end: int) -> str:
    """Move the data pointer from ``start`` to ``end`` on the tape."""
    return (">" if end > start else "<") * abs(end - start)


def super_snusp(truth_table: str) -> str:
    """Build a deterministic Super SNUSP program for ``truth_table``.

    Input ``i`` is stored in cell ``i`` and the accumulator is cell ``n``.
    For every nonzero ANF coefficient the construction forms its input
    product in cell ``n + 1`` and xors it into the accumulator.  Both reads
    happen before any evaluation, so every path consumes exactly ``n`` input
    lines, including constant and folded functions.
    """
    n = _validate_truth_table(truth_table)
    if n == 2 and truth_table in _TWO_INPUT_SHORT:
        # An explicit START marker removes the spec's undocumented default
        # heading from generated programs; it is a no-op once execution begins.
        return '"' + _TWO_INPUT_SHORT[truth_table]

    program = ['"', "48{"]
    for input_index in range(n):
        program.extend([",", "-"])
        if input_index + 1 < n:
            program.append(">")

    product = n + 1
    program.append(">")  # from the final input to the zeroed accumulator
    coefficients = _anf_coefficients(truth_table)
    if coefficients[0]:
        program.append(")")

    for mask, coefficient in enumerate(coefficients[1:], start=1):
        if not coefficient:
            continue
        program.extend([">", "1"])
        for input_index in range(n):
            table_bit = 1 << (n - 1 - input_index)
            if mask & table_bit:
                program.extend(
                    [
                        _move(product, input_index),
                        "{",
                        _move(input_index, product),
                        "&",
                    ]
                )
        program.extend(["{", "<", "^"])

    # The stack top is a term by now, so build a fresh ASCII offset in the
    # product cell and push it.  The accumulator is then exactly 48 or 49.
    program.extend([">", "48", "{", "<", "+", "."])
    return "".join(program)
