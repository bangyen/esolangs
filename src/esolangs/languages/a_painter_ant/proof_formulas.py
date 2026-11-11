"""Executed command bounds."""


def source_terms(_: int, program: str) -> dict[str, int]:
    """Count significant source characters."""
    return {"S": len("".join(program.split()))}
