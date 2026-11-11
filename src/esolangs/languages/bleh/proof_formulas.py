"""Command and written-state bounds for the short read alias."""


def workspace(n: int, _: str) -> int:
    """Heap cells, control/continuation peaks, fresh address and input cursor."""
    bl = int.bit_length
    # Node ids <2^(n+1), and 52>2^5. Constant names add a level suffix.
    width = max((n + 5) // 5, 1 + len(str(n - 1)))
    control = max(128, 8 * width + 16, 8 * width + bl(2 * n) + 1)
    kont = max(105, 8 * width + 17, 8 * width + 2 * bl(2 * n) + 1)
    # Each matched read forces two byte thunks: its argument and the
    # validator's. Statement reads retain only the validator's thunk; that
    # heap slack also covers the flat constant block's statement AST.
    heap = 128 * n + 1 + sum(map(bl, range(1, 2 * n)))
    return heap + control + kont + bl(2 * n) + bl(n)


def execution_terms(_: int, program: str) -> dict[str, int]:
    """Mark the statement-read construction."""
    return {"C": int("main:={" in program)}
