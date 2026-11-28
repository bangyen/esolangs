"""Direct constants and the single-accumulator command envelope."""


def _constant(n: int, program: str) -> bool:
    return program in ("V" * (n - 1) + "AAVVV", "V" * (n - 1) + "AAVVAVLAVV")


def execution_terms(n: int, program: str) -> dict[str, int]:
    """Identify the direct constant program."""
    return {"C": int(_constant(n, program))}
