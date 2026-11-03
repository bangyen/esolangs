"""Whitespace's exact source maximum, including its inline one-bit route."""


def _chars(n: int, _: str) -> int:
    """AND attains: one inline step at n=1, otherwise the shared step."""
    # With m>=2 essential inputs, L <= 2**m-4m+8n+70; convexity puts
    # the maximum at m=2 or n, and 2**n-4n+4 >= 0 for n>=2.
    # One essential bit costs 8n+57; constants cost at most 7n+12.
    return 65 if n == 1 else (1 << n) + 4 * n + 70


FORMULAS = {"scaling": (_chars, True, (1, 2, 3, 5, 6))}
