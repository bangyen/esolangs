"""Full decision-tree witnesses for Factor's leading-constant bound."""

from esolangs.tools.helpers import _validate_truth_table, move_text

_SPAN = 6
_STEP = 8


def _body(table: str, n: int, start: int, result: int, zero: int) -> str:
    cells: list[str] = []
    pos = start

    def move(target: int) -> None:
        nonlocal pos
        cells.append(move_text(pos, target, ">", "<"))
        pos = target

    def node(i: int, offset: int) -> None:
        bit = 2 * i
        if i == n - 1:
            if table[offset] == table[offset + 1]:
                move(zero)
                if table[offset] == "1":
                    cells.append("+")
            else:
                move(bit)
                if table[offset] == "1":
                    cells.append("[-")
                    move(result)
                    cells.append("-")
                    move(bit)
                    cells.append("]")
                    move(result)
            cells.append(".")
            return
        flag = bit + 1
        move(bit)
        cells.append("[-")
        move(bit + 2)
        node(i + 1, offset + 2 ** (n - 1 - i))
        move(bit)
        cells.append("]")
        move(flag)
        cells.append("[-")
        move(bit + 2)
        node(i + 1, offset)
        move(flag)
        cells.append("]")

    move(0)
    node(0, 0)
    return "".join(cells)


def printed_program(truth_table: str, *, reverse_last: bool = False) -> str:
    """Print raw or complemented final input, with one fixed inversion variant."""
    n = _validate_truth_table(truth_table)
    result, zero, scratch, multiplier = 2 * n - 1, 2 * n, 2 * n + 1, 2 * n + 2
    build = (
        ">" * multiplier
        + "+" * _SPAN
        + "[-<"
        + "+" * _STEP
        + "<"
        + "+" * _STEP
        + "<"
        + "+" * (2 * _STEP)
        + ">>>]<<<+"
        + "<" * result
    )
    reads = "".join("," + (">>" if k < n - 1 else "") for k in range(n))
    inversion = ""
    if reverse_last:
        truth_table = "".join(
            truth_table[i + 1] + truth_table[i] for i in range(0, len(truth_table), 2)
        )
        inversion = "[->-<]>[-<+>]" + "+" * 97 + "<"
    after_reads = 2 * (n - 1)
    back = scratch - after_reads
    dedent = ""
    if n > 1:
        dedent = (
            ">" * back
            + "[-"
            + "<" * scratch
            + "-"
            + ">>-" * (n - 2)
            + ">" * (scratch - 2 * (n - 2))
            + "]"
            + "<" * back
        )
    prepared: list[str] = []
    pos = after_reads
    temp = multiplier + 1
    for i in range(n - 1):
        bit, flag = 2 * i, 2 * i + 1
        prepared.append(move_text(pos, flag, ">", "<") + "+<[->-")
        prepared.append(">" * (temp - flag) + "+" + "<" * (temp - bit) + "]")
        prepared.append(
            ">" * (temp - bit)
            + "[-"
            + "<" * (temp - bit)
            + "+"
            + ">" * (temp - bit)
            + "]"
        )
        pos = temp
    body = _body(truth_table, n, pos, result, zero)
    return build + reads + inversion + dedent + "".join(prepared) + body
