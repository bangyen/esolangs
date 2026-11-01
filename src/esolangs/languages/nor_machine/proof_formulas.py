"""Direct constants and the unchanged packed-mux envelopes."""


def _constant(n: int, program: str) -> bool:
    return program in ("V" * (n - 1) + "AAVVV", "V" * (n - 1) + "AAVVAVLAVV")


def execution(n: int, program: str) -> int:
    """Constant commands execute once; other tables keep the mux bound."""
    if _constant(n, program):
        return len(program)
    return 15 * (1 << n) + 12 * n * n + 93 * n - 20


def workspace(n: int, program: str) -> int:
    """NOR keeps magnitudes at most two; normalization duplicates at most thrice."""
    if _constant(n, program):
        return (
            max(3 * n, 9) + (len(program) - 1).bit_length() + 1 + (2 * n).bit_length()
        )
    return 3 * (1 << n) + 4 * n + len(program).bit_length() + 24
