"""Direct constants and the unchanged decision-diagram envelopes."""


def source_terms(_: int, program: str) -> dict[str, int]:
    """Mark the straight-line constant with fifty bytes of written storage."""
    return {"C": int(program.startswith(","))}
