"""Snapshot-bit bounds."""


def workspace_terms(_: int, program: str) -> dict[str, int]:
    """Identify the constant route without a decision frame."""
    return {"C": int(program.replace("\n", "").startswith(("x->s[]=0;", "x->s[]=1;")))}
