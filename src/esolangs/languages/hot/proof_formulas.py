"""Constant paths and Church-pair envelopes, also bounding majority identities."""


def execution_terms(_: int, program: str) -> dict[str, int]:
    """Mark the constant spine; the majority replacement stays below the tree bound."""
    return {"C": int(program.startswith("A0"))}
