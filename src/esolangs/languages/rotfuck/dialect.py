"""ROTfuck rotation choices, independent of execution."""

#: The rotation cycle per direction, each read as "turns into the next":
#: backward is the prose's ``+-><,.[]`` reversed.
ROTFUCK_CYCLES = {"backward": "+][.,<>-", "forward": "+-><,.[]"}
ROTATIONS = tuple(ROTFUCK_CYCLES)


def validate_rotation(value: str) -> str:
    """Validate which way the command cycle turns."""
    if value not in ROTATIONS:
        raise ValueError("rotation must be backward or forward")
    return value
