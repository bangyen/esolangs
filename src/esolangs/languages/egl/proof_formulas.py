"""Dimensions and wrap markers for the painted grid."""


def workspace_terms(n: int, program: str) -> dict[str, int]:
    """Extract the explicit dimensions and body length for the large grid."""
    if n <= 3:
        return {"G": 0, "W": 0, "H": 0, "B": 0}
    dimensions, body = program.split(":", 1)
    w, h = map(int, dimensions.split(","))
    return {"G": 1, "W": w, "H": h, "B": len(body)}


def execution_terms(_: int, program: str) -> dict[str, int]:
    """Detect wrapping, whose no-ops require a wider ceiling."""
    return {"R": int("\n" in program)}
