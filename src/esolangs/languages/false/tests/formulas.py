"""FALSE's stack, variables, frames and input progress by construction."""

import re

bl = int.bit_length


def workspace(n: int, program: str) -> int:
    """Cover 32-bit lookup alternatives and cached expression lambda calls.

    ``b`` bounds each source position. A cached expression call can nest
    inside its parent's conditional frame, so allow two frames per input.
    """
    b = bl(len(program))
    compact = "".join(program.split())
    if compact.endswith("*0\\>1&."):
        return 34 * n + 67 + 2 * b * (n + 2) + bl(n)
    if compact.endswith("1&."):
        inputs = len(re.findall(r"\^1&[a-z]:", compact))
        stores = compact.count(":") - inputs
        return 5 * n + 6 + 2 * b * (stores + 2 * n + 2) + bl(n)
    if "[" in compact:
        return n + 1 + 2 * b * (compact.count(":") + n + 2) + bl(n)
    return 6 * n + 1 + 2 * b + bl(n)
