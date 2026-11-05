"""Worst lengths and commands after run counting and macro expansion."""


def _scaling(n: int, _: str) -> int:
    # At n=3 a one-ignored-input four-entry table costs one extra character.
    return {1: 76, 2: 95, 3: 107}.get(n, 5 * (1 << n) // 2 + n + 83)


def _execution(n: int, _: str) -> int:
    # One sweep at n=1 is shorter without the macro; otherwise c<=T/2.
    return 28 if n == 1 else 9 * (1 << n) // 2 + n + 21
