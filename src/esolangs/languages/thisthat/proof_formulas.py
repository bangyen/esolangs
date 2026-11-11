"""Uncontracted command bounds."""


def execution_terms(n: int, program: str) -> dict[str, int]:
    """Mark the constant glyph layout."""
    constant = (
        "◧" not in program
        and program.count("□") + program.count("■") == 1
        and program.count("◇") == n + 1
    )
    return {"C": int(constant)}
