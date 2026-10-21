"""Executed command bounds."""


def execution(n: int, _: str) -> int:
    """The stated execution bound, evaluated for n and the program."""
    # The envelope of the two raced builds.  The diagram executes one
    # path, at most min(12n + 69, 10n + 99); 12n + 69 is the smaller of
    # the two at every arity this formula is checked.  An expression
    # program is straight-line and executes its whole text, so its steps
    # are at most its length: the body is at most 11T - 10 (the mux
    # combine adds 10 over the two halves, the constant base is 1), the
    # prologue at most 5 an input, and the masked print 3.
    return max(11 * (1 << n) + 5 * n - 7, 12 * n + 69)
