r"""Boolean-function generator for Packlang."""

from esolangs.tools.boolean.fargo import _anf_coefficients
from esolangs.tools.boolean.helpers import _ASCII_ZERO, _validate_truth_table

__all__ = ["packlang"]

_INDENT = "  "


def _term_inputs(mask: int, n: int) -> list[int]:
    r"""Return the inputs the term ``mask`` ANDs, most-significant-first."""
    return [i for i in range(n) if mask >> (n - 1 - i) & 1]


def _term(mask: int, n: int, depth: int) -> str:
    r"""Emit one ANF term as a nest of ``If``s ending in ``INCR acc``."""
    pad = _INDENT * depth
    inputs = _term_inputs(mask, n)
    lines = [
        f"{pad}{_INDENT * k}If x{i} ^ {_ASCII_ZERO} Then {{"
        for k, i in enumerate(inputs)
    ]
    inner = _INDENT * (depth + len(inputs))
    lines.append(f"{inner}INCR acc;")
    lines += [f"{pad}{_INDENT * k}}}" for k in reversed(range(len(inputs)))]
    return "\n".join(lines)


def packlang(truth_table: str) -> str:
    r"""Build a Packlang program computing the given truth table."""
    n = _validate_truth_table(truth_table)
    coefficients = _anf_coefficients(truth_table)

    declarations = "".join(f"  Char x{i};\n" for i in range(n))
    reads = "".join(f"{_INDENT * 2}charGet(x{i});\n" for i in range(n))
    terms = "\n".join(_term(mask, n, 2) for mask in range(1 << n) if coefficients[mask])
    body = f"{terms}\n" if terms else ""
    return (
        "Package : IO {\n"
        f"{declarations}"
        "  Integer(0, 1, 1, 0) acc;\n"
        "  Integer main {\n"
        f"{_INDENT * 2}INIT acc;\n"
        f"{reads}"
        f"{body}"
        f"{_INDENT * 2}charPut({_ASCII_ZERO} ^ acc);\n"
        f"{_INDENT * 2}0;\n"
        "  }\n"
        "} truthTable;\n"
    )
