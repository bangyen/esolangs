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
