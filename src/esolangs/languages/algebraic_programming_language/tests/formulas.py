"""Bounds for inline expressions and shared, ordered expression frames."""

from esolangs.languages.algebraic_programming_language.generator import (
    _NOT_TIGHT,
    _reads,
)


def execution_terms(n: int, program: str) -> dict[str, int]:
    """Classify constant reads and count the initialized definitions."""
    prefix = _reads(n, "&")
    constant = program in (prefix, prefix + "|1")
    return {
        "C": int(constant),
        "J": int(program.endswith("|1")),
        "K": program.count("=") - program.startswith(_NOT_TIGHT),
    }


def workspace_terms(_: int, program: str) -> dict[str, int]:
    """Identify expressions without initialized shared definitions."""
    return {"C": int(program.count("=") == program.startswith(_NOT_TIGHT))}
