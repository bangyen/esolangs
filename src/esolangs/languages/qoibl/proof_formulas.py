"""Straight-line commands and generated variable/cursor bit ceilings."""


def execution(_n: int, program: str) -> int:
    """Count three assignment markers per store and the one final print."""
    # Width-1 01 executes 40 statements, not the unexpanded n+6 = 7.
    return program.count("w") // 3 + 1


def workspace(n: int, program: str) -> int:
    """Bound generated stores, including Horner scratch and both cursors."""
    commands = execution(n, program)
    if "".join(program.split()).startswith("weeweetwe"):
        # Key 0 and its input byte cost 7; scratch key 2 plus byte add 8.
        variables = 7 if commands == n + 1 else 15
    else:
        rows = 1 << n
        # Keys 0,1,48,49 cost 14 bits; the two lookup factors cost 3.
        # Power plus quotient need rows+1 bits before, or 2*rows-2 after
        # parity extraction: polarity keeps the packed literal below 2**(rows-1).
        variables = 17 + max(rows + 1, 2 * rows - 2)
        if commands > n + 6:
            # Key 2 and either the packed literal or a six-bit ASCII constant.
            variables += 2 + max(rows - 1, 6)
    return variables + commands.bit_length() + n.bit_length()
