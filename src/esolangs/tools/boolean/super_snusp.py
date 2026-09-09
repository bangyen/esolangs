"""Boolean-function generator for Super SNUSP.

The generator reads ASCII ``0``/``1`` values, normalizes them to bits, then
evaluates the truth table's algebraic normal form (ANF).  ANF is an XOR of
input products, which maps directly to Super SNUSP's ``^`` and ``&`` stack
operations and avoids the language's random ``=`` opcode entirely.
"""

from esolangs.tools.boolean.helpers import (
    _validate_truth_table,
    essential_inputs,
    read_at,
)

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


def _emit_anf(
    n: int, truth_table: str, used: list[int], *, coefficients: list[int] | None = None
) -> str:
    """Emit an ANF evaluator over ``used`` stream inputs."""
    program = ['"', "48{"]
    for input_index in range(n):
        program.extend([",", "-"])
        if input_index in used:
            program.append(">")

    # A trailing ignored input occupies the accumulator cell.  Inputs that
    # are ignored earlier are overwritten by the next retained input, so a
    # clear is needed only when the last stream input is ignored (or none are
    # retained at all).
    if not used or used[-1] != n - 1:
        program.append("0")
    product = len(used) + 1
    coefficients = (
        _anf_coefficients(truth_table) if coefficients is None else coefficients
    )
    if coefficients[0]:
        program.append(")")

    for mask, coefficient in enumerate(coefficients[1:], start=1):
        if not coefficient:
            continue
        program.extend([">", "1"])
        for input_index in range(len(used)):
            table_bit = 1 << (len(used) - 1 - input_index)
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


def _anf_cost(
    n: int,
    truth_table: str,
    used: list[int],
    *,
    coefficients: list[int] | None = None,
) -> int:
    """Return the rendered length of :func:`_emit_anf` without emitting it."""
    cost = 4 + 2 * n + len(used) + 7
    if not used or used[-1] != n - 1:
        cost += 1
    coefficients = (
        _anf_coefficients(truth_table) if coefficients is None else coefficients
    )
    cost += coefficients[0]
    product = len(used) + 1
    for mask, coefficient in enumerate(coefficients[1:], start=1):
        if not coefficient:
            continue
        cost += 5  # ``>1`` then ``{<^`` around the product.
        for input_index in range(len(used)):
            table_bit = 1 << (len(used) - 1 - input_index)
            if mask & table_bit:
                cost += 2 * (product - input_index) + 2
    return cost


def super_snusp(truth_table: str) -> str:
    """Build a deterministic Super SNUSP program for ``truth_table``.

    Only essential inputs are retained, compactly, while every original input
    is still consumed in stream order.  The ANF is built over that projection:
    for every nonzero coefficient the construction forms its input product
    beside the accumulator and xors it in.  Both reads happen before any
    evaluation, so every path consumes exactly ``n`` input lines, including
    constant and reduced functions.
    """
    n = _validate_truth_table(truth_table)
    if n == 2 and truth_table in _TWO_INPUT_SHORT:
        # An explicit START marker removes the spec's undocumented default
        # heading from generated programs; it is a no-op once execution begins.
        return '"' + _TWO_INPUT_SHORT[truth_table]

    used = essential_inputs(truth_table, n)
    full = list(range(n))
    if len(used) == n:
        return _emit_anf(n, truth_table, full)
    reduced = read_at(truth_table, used, n)
    full_coefficients = _anf_coefficients(truth_table)
    reduced_coefficients = _anf_coefficients(reduced)
    return (
        _emit_anf(n, truth_table, full, coefficients=full_coefficients)
        if _anf_cost(n, truth_table, full, coefficients=full_coefficients)
        <= _anf_cost(n, reduced, used, coefficients=reduced_coefficients)
        else _emit_anf(n, reduced, used, coefficients=reduced_coefficients)
    )
