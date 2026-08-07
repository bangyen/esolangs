"""Generate programs that compute a boolean function from a truth table.

Like tools/binary.py (which targets Dig), each generator builds a program
that reads n boolean inputs and prints the truth-table result for the
combination it is given.
"""

from collections.abc import Sequence


def sophie(truth_table: str, n: int) -> str:
    """Build a Sophie program computing the given truth table.

    ``truth_table`` is a binary string of length 2**n indexed by the inputs
    (most significant first), and ``n`` is the number of inputs.

    Sophie reads a character with ``;`` and branches on the accumulator with
    ``@$48{then}{else}`` -- the else block runs flat after a failed check, so
    consecutive conditionals must use the block form. Each leaf sets the
    result with ``#$48``/``#$49`` and prints it before halting.
    """

    def build(path: list[int]) -> str:
        depth = len(path)
        if depth == n:
            row = 0
            for bit in path:
                row = row * 2 + bit
            return f"#${48 + int(truth_table[row])},&"
        return ";" + "@$48{" + build([*path, 0]) + "}" + "{" + build([*path, 1]) + "}"

    return build([])


def modulous(truth_table: str, n: int) -> str:
    """Build a Modulous program computing the given truth table.

    ``truth_table`` is a binary string of length 2**n indexed by the inputs
    (most significant first), and ``n`` is the number of inputs.

    Modulous reads the inputs onto the stack with ``[INP INT]`` (top is the
    last input), then a decision tree branches on the top with
    ``[JMP F n IF 0/1]``, popping each checked bit. Each leaf pushes the
    result with ``[PSH INT]`` and prints it.
    """

    def build(S: list[int], k: int) -> str:
        if len(S) == 1:
            return f"[PSH INT {truth_table[S[0]]}][PRT INT][END]"
        g0 = [r for r in S if ((r >> (n - k)) & 1) == 0]
        g1 = [r for r in S if ((r >> (n - k)) & 1) == 1]
        sub0 = build(g0, k - 1)
        sub1 = build(g1, k - 1)
        d = 2 + sub0.count("[")
        return f"[JMP F 2 IF 0][JMP F {d} IF 1][POP]{sub0}[POP]{sub1}"

    return "[INP INT]" * n + build(list(range(2**n)), n)


def brainif(truth_table: str, n: int) -> str:
    """Build a BrainIf program computing the given truth table.

    ``truth_table`` is a binary string of length 2**n indexed by the inputs
    (most significant first), and ``n`` is the number of inputs.

    BrainIf reads each input into a cell with ``if 0 input``, then a
    recursive decision tree checks each cell with ``if 48/49 goto`` (the
    groups' checks sit adjacent so a failed check falls through to the next
    candidate). Each leaf moves to a fresh cell, increments it to 48+r, and
    outputs it.
    """

    entries: list = []
    for i in range(n):
        entries.append(("cmd", "if 0 input"))
        if i < n - 1:
            entries.append(("cmd", "if 48 move right"))
            entries.append(("cmd", "if 49 move right"))
    for _ in range(n - 1):
        entries.append(("cmd", "if 48 move left"))
        entries.append(("cmd", "if 49 move left"))

    counter = [0]

    def build(rows: list[int], k: int) -> list:
        if len(rows) == 1:
            r = int(truth_table[rows[0]])
            block: list = [("cmd", "if 48 move right"), ("cmd", "if 49 move right")]
            block += [("cmd", f"if {v} increment") for v in range(48 + r)]
            block.append(("cmd", f"if {48 + r} output"))
            block.append(("if_goto", 48 + r))
            return block
        g0 = [row for row in rows if ((row >> (n - k)) & 1) == 0]
        g1 = [row for row in rows if ((row >> (n - k)) & 1) == 1]
        l0, l1 = counter[0], counter[0] + 1
        counter[0] += 2
        sub0 = build(g0, k + 1)
        sub1 = build(g1, k + 1)
        return [
            ("if", 48, l0),
            ("if", 49, l1),
            ("mr", 48, l0),
            *sub0,
            ("mr", 49, l1),
            *sub1,
        ]

    entries += build(list(range(2**n)), 1)
    entries.append(("end",))
    labels = {entry[2]: i + 1 for i, entry in enumerate(entries) if entry[0] == "mr"}
    end_line = len(entries)

    lines = []
    for entry in entries:
        if entry[0] == "cmd":
            lines.append(entry[1])
        elif entry[0] == "if":
            lines.append(f"if {entry[1]} goto {labels[entry[2]]}")
        elif entry[0] == "mr":
            lines.append(f"if {entry[1]} move right")
        elif entry[0] == "if_goto":
            lines.append(f"if {entry[1]} goto {end_line}")
        else:
            lines.append("")
    return "\n".join(lines)


def nevermind(truth_table: str, n: int) -> str:
    """Build a Nevermind program computing the given truth table.

    ``truth_table`` is a binary string of length 2**n indexed by the inputs
    (most significant first), and ``n`` is the number of inputs.

    Nevermind reads each input with ``input,?`` into its own variable, then a
    decision tree of nested ``if``/``endif`` blocks prints the result for the
    matching combination.
    """
    lines = []
    for i in range(n):
        lines.append("input,?")
        lines.append(f"make,{chr(ord('a') + i)},$answer")

    def build(k: int, row: int) -> None:
        if k == n:
            lines.append(f"print,{truth_table[row]}")
            return
        for bit in (0, 1):
            lines.append(f"if,${chr(ord('a') + k)},==,{bit}")
            build(k + 1, row * 2 + bit)
            lines.append("endif")

    build(0, 0)
    return "\n".join(lines)


def circlefuck(truth_table: str, n: int) -> str:
    """Build a CircleFuck program computing the given truth table.

    ``truth_table`` is a binary string of length 2**n indexed by the inputs
    (most significant first), and ``n`` is the number of inputs.

    CircleFuck reads each input with ``,`` and normalizes it to 0/1 with 48
    ``-``s, then a decision tree branches on the cells from the last input
    down. Each leaf starts from a cleared cell, so it sets the result with
    ``+``s, prints it, and halts with ``@`` -- halting at the leaf means the
    tree never needs to skip the sibling branch.
    """

    def emit(c: str) -> None:
        prog.append(c)

    prog: list[str] = []
    for _ in range(n):
        emit(",")
        prog.extend("-" * 48)
        emit(">")
    prog.pop()  # the trailing ">" would leave the pointer past the last input

    def build(k: int, row: int) -> None:
        if k < 0:
            prog.extend("+" * (48 + int(truth_table[row])))
            emit(".")
            emit("@")
            return
        emit("[")
        emit("[-]")
        if k:
            emit("<")
        build(k - 1, row + 2 ** (n - 1 - k))
        emit("]")
        if k:
            emit("<")
        build(k - 1, row)

    build(n - 1, 0)
    return "".join(prog)


def circlefuck_byte(truth_table: Sequence[int], n: int) -> str:
    """Build a CircleFuck program computing a byte-valued function.

    ``truth_table`` is a sequence of ``2**n`` byte values (0-255) indexed by
    the inputs (most significant first), and ``n`` is the number of bit
    inputs.  This is the boolean generator generalized to arbitrary byte
    outputs: each leaf prints ``chr(value)`` instead of ``chr(48 + bit)``.
    """

    prog: list[str] = []

    def emit(c: str) -> None:
        prog.append(c)

    for _ in range(n):
        emit(",")
        prog.extend("-" * 48)
        emit(">")
    prog.pop()  # the trailing ">" would leave the pointer past the last input

    def build(k: int, row: int) -> None:
        if k < 0:
            value = truth_table[row]
            if value:
                prog.extend("+" * value)
            emit(".")
            emit("@")
            return
        emit("[")
        emit("[-]")
        if k:
            emit("<")
        build(k - 1, row + 2 ** (n - 1 - k))
        emit("]")
        if k:
            emit("<")
        build(k - 1, row)

    build(n - 1, 0)
    return "".join(prog)
