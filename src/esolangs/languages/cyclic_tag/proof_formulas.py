"""Queue-walk resource maxima, including named minority markers."""


def execution(n: int, _: str) -> int:
    """AND's extra continuation wins from three inputs."""
    return (1 << n) + n + 2 + (n >= 3)


def workspace(n: int, _: str) -> int:
    """The queue peaks at T+1 bits; a marker10 adds one from two inputs."""
    return (8 << n) + 9 + 8 * (n >= 2) + ((1 << n) + n).bit_length()
