"""Executed command bounds."""


def workspace_terms(_: int, program: str) -> dict[str, int]:
    """Mark the false literal: its 11-bit snapshot retains the 18-bit ceiling."""
    return {"D": int(program == "$")}
