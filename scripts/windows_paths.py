"""Windows filename rules for source paths."""

_DEVICE_NAMES = frozenset(
    {
        "AUX",
        "CON",
        "CONIN$",
        "CONOUT$",
        "NUL",
        "PRN",
        *(f"{port}{digit}" for port in ("COM", "LPT") for digit in "123456789¹²³"),
    }
)


def windows_reserved_name(name: str) -> bool:
    """Return whether Windows reserves this path component."""
    stem = name.partition(".")[0].rstrip(" ").upper()
    return (
        stem in _DEVICE_NAMES
        or name.endswith((" ", "."))
        or any(char in '<>:"/\\|?*' or ord(char) < 32 for char in name)
    )
