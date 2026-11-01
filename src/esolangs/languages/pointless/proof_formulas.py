"""Direct constants and the unchanged decision-diagram envelopes."""


def execution(n: int, program: str) -> int:
    """Constants are straight-line commands; other tables keep the tree bound."""
    if program.startswith(","):
        return len(program)
    return 26 * n + 309


def workspace(n: int, program: str) -> int:
    """Constants write fifty bytes, a frame, pointer, bang flag and input cursor."""
    if program.startswith(","):
        return 408 + len(program).bit_length() + n.bit_length()
    return (n + 1) * (2 * len(program).bit_length() + 4) + 16 * n + 430
