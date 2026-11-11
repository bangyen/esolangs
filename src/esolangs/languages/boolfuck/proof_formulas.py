"""Snapshot-bit bounds."""


def workspace_terms(n: int, program: str) -> dict[str, int]:
    """Distinguish the symmetric counter from the drain-only prefix."""
    source = "".join(program.split())
    symmetric = source.startswith("+>" * n + "<" * n + "[,,,,,,,,>]")
    return {
        "C": int(not symmetric and source.startswith("," * (8 * n))),
        "S": int(symmetric),
    }
