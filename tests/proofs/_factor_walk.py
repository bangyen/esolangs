"""Factor witness with an input-directed walk through literal truth bits."""

from esolangs.tools.helpers import _validate_truth_table


def walked_program(truth_table: str) -> str:
    """Read bits in order, moving left on zero, then print the addressed cell."""
    n = _validate_truth_table(truth_table)
    data = ">" + ">>".join("+" if bit == "1" else "" for bit in truth_table) + "<"
    address = "".join(
        "," + "-" * 49 + "[+" + "<" * (1 << (n - i)) + "]" for i in range(n)
    )
    return data + address + ">" + "+" * 48 + "."


def packed_program(truth_table: str) -> str:
    """Walk to a two-bit payload and select its final bit with fixed code."""
    n = _validate_truth_table(truth_table)
    values = [int(truth_table[i : i + 2], 2) for i in range(0, len(truth_table), 2)]
    reflected = 2 * sum(values) > 3 * len(values)
    if reflected:
        values = [3 - value for value in values]
    data = ">" + ">>".join("+" * value for value in values) + "<"
    address = "".join(
        "," + "-" * 49 + "[+" + "<" * (1 << (n - 1 - i)) + "]" for i in range(n - 1)
    )
    # Divide the payload by two: cell one is remainder, cell two quotient.
    divide = ">[-]>[-]>[-]<<<[->>>+<<[->+>-<<]>>[-<<+>>]<<<]"

    def output(cell: int) -> str:
        if not reflected:
            return "+" * 48 + "."
        move = ">" * (4 - cell)
        back = "<" * (4 - cell)
        return (
            move
            + "[-]"
            + back
            + "[-"
            + move
            + "-"
            + back
            + "]"
            + move
            + "+" * 49
            + "."
            + back
        )

    select = ">>>+<<<," + "-" * 48
    select += "[->>>-<<" + output(1) + "<]"
    select += ">>>[-<" + output(2) + ">]"
    return data + address + ">" + divide + select
