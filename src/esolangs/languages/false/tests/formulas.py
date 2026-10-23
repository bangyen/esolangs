"""FALSE's peak written state, summed over the build route's components."""

bl = int.bit_length


def workspace(n: int, program: str) -> int:
    """Stack + variables + frames + input count, by route (b = bl(L)).

    Constant: n unread-then-bare chars (6 bits each) on the stack, the root
    frame (pc, end) alone.  Expression: n stored bits, a stack of at most
    2(n - 1) values (a mux holds its zero half twice per level, 2 bits each).
    Diagram: one kept bit a level plus a lambda in flight on the stack,
    S stored lambdas (a start and an end, 2b bits), and the root plus one
    lambda frame a level.
    """
    b = bl(len(program))
    if "[" in program:
        stack, stored, frames = (
            n + 2 * b + 1,
            2 * b * program.count(":"),
            2 * b * (n + 1),
        )
    elif program.endswith("1&."):
        stack, stored, frames = 4 * n - 2, n, 2 * b
    else:
        stack, stored, frames = 6 * n, 0, 2 * b
    return stack + stored + frames + bl(n)


FORMULAS = {"workspace": (workspace, False, (3, 4, 5, 6, 8, 9))}
