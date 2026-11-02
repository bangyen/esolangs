"""Source ceiling for input buffering and shared residual cases."""

from esolangs.languages.switchcase.proof_formulas import diagram_cap


def _chars(n: int, _: str) -> int:
    """Input names and bounded-address residuals; O(T) characters in all."""
    nodes = diagram_cap(n)
    name = len(f"x{n - 1}")
    digits = len(str(n + nodes + 4))
    return 34 + n * (2 * name + 10) + nodes * (name + 10 + 2 * digits) + digits


FORMULAS = {"scaling": (_chars, False, (1, 2, 3, 4, 5, 6, 8, 9, 10, 12))}
