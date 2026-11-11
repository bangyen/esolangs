"""Direct constants and single-accumulator resource envelopes.

A selector's shifted copy is h bits shorter; its peak is at most
2U+h+4m+16 queue bits, versus 3(U+m)+6 during extraction (U=2**m).
The command cap covers prefix O(n**3), Horner O(U), and summed smears O(U).
"""


def _constant(n: int, program: str) -> bool:
    return program in ("V" * (n - 1) + "AAVVV", "V" * (n - 1) + "AAVVAVLAVV")


def execution_terms(n: int, program: str) -> dict[str, int]:
    """Identify the direct constant program."""
    return {"C": int(_constant(n, program))}
