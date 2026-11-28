"""Source terms for the Flipscript workspace formula."""


def workspace_terms(_n: int, program: str) -> dict[str, int]:
    """Count the emitted lines before the terminal cursor."""
    return {"R": len(program.splitlines())}
