r"""Boolean-function generator for Fargo."""

from esolangs.tools.boolean.helpers import _validate_truth_table

__all__ = ["fargo"]


def _anf_coefficients(truth_table: str) -> list[int]:
    r"""Return the table's algebraic normal form coefficients."""
    n = _validate_truth_table(truth_table)
    coeffs = [int(bit) for bit in truth_table]
    step = 1
    for _ in range(n):
        for start in range(0, 1 << n, step * 2):
            for offset in range(start, start + step):
                coeffs[offset + step] ^= coeffs[offset]
        step *= 2
    return coeffs


def _term(mask: int, n: int) -> str:
    r"""Return the AND-product of the inputs ``mask`` selects."""
    reads = [f"@ {(n - 1 - i):b}" for i in range(n) if mask >> (n - 1 - i) & 1]
    return "& " * (len(reads) - 1) + " ".join(reads)


def fargo(truth_table: str) -> str:
    r"""Build a Fargo program computing the given truth table."""
    n = _validate_truth_table(truth_table)
    coeffs = _anf_coefficients(truth_table)
    terms = [_term(mask, n) for mask in range(1 << n) if coeffs[mask] and mask]
    constant = coeffs[0]
    if not terms:
        return f"% 0 {constant}\n$\n"
    # ``^`` is binary and prefix,.
    # up front; a nonzero constant.
    if constant:
        terms.insert(0, "1")
    expression = "^ " * (len(terms) - 1) + " ".join(terms)
    return f"% 0 {expression}\n$\n"
