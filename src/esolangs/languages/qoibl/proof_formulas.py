"""Straight-line commands and generated variable/cursor bit ceilings."""


def execution_terms(_: int, program: str) -> dict[str, int]:
    """Count assignments by their three markers."""
    # Width-1 01 executes 40 statements, up from 7 in the default layout.
    return {"W": program.count("w")}


def workspace_terms(n: int, program: str) -> dict[str, int]:
    """Extract the layout and assignment tally for the two cursor bounds."""
    markers = program.count("w")
    return {
        "C": int("".join(program.split()).startswith("weeweetwe")),
        "A": int(3 * n <= markers < 3 * (n + 1)),
        "F": int(markers >= 3 * (n + 6)),
        "W": markers,
    }
