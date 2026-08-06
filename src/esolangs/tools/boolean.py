"""Generate programs that compute a boolean function from a truth table.

Like tools/binary.py (which targets Dig), each generator builds a program
that reads n boolean inputs and prints the truth-table result for the
combination it is given.
"""


def sophie(truth_table, n):
    """Build a Sophie program computing the given truth table.

    ``truth_table`` is a binary string of length 2**n indexed by the inputs
    (most significant first), and ``n`` is the number of inputs.

    Sophie reads a character with ``;`` and branches on the accumulator with
    ``@$48{then}{else}`` -- the else block runs flat after a failed check, so
    consecutive conditionals must use the block form. Each leaf sets the
    result with ``#$48``/``#$49`` and prints it before halting.
    """

    def build(path):
        depth = len(path)
        if depth == n:
            row = 0
            for bit in path:
                row = row * 2 + bit
            return f"#${48 + int(truth_table[row])},&"
        return ";" + "@$48{" + build(path + [0]) + "}" + "{" + build(path + [1]) + "}"

    return build([])


def modulous(truth_table, n):
    """Build a Modulous program computing the given truth table.

    ``truth_table`` is a binary string of length 2**n indexed by the inputs
    (most significant first), and ``n`` is the number of inputs.

    Modulous reads the inputs onto the stack with ``[INP INT]`` (top is the
    last input), then a decision tree branches on the top with
    ``[JMP F n IF 0/1]``, popping each checked bit. Each leaf pushes the
    result with ``[PSH INT]`` and prints it.
    """

    def build(S, k):
        if len(S) == 1:
            return f"[PSH INT {truth_table[S[0]]}][PRT INT][END]"
        g0 = [r for r in S if ((r >> (n - k)) & 1) == 0]
        g1 = [r for r in S if ((r >> (n - k)) & 1) == 1]
        sub0 = build(g0, k - 1)
        sub1 = build(g1, k - 1)
        d = 2 + sub0.count("[")
        return f"[JMP F 2 IF 0][JMP F {d} IF 1][POP]{sub0}[POP]{sub1}"

    return "[INP INT]" * n + build(list(range(2**n)), n)
