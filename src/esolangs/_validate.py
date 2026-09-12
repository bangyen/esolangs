r"""Argument checks shared by every entry point that takes them."""

from __future__ import annotations

_INFINITE = (float("inf"), float("-inf"))

# : The shortest wall-clock.
# : :func:`check_timeout` for.
_TIMEOUT_FLOOR = 0.001

# : The longest one it can take.
# : a large enough float.
_TIMEOUT_CEILING = 2_592_000.0


def check_whole(value: object, name: str) -> int:
    r"""Return ``value`` as a non-negative index, or refuse it by name."""
    from esolangs.exceptions import ArgumentError

    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ArgumentError(f"{name} must be a non-negative integer, got {value!r}")
    return value


def check_timeout(timeout: object) -> None:
    r"""Refuse a timeout that is not a positive, finite number."""
    from esolangs.exceptions import ArgumentError

    if timeout is None:
        return
    if isinstance(timeout, bool) or not isinstance(timeout, int | float):
        raise ArgumentError(f"timeout must be a number or None, got {timeout!r}")
    if timeout != timeout or timeout in _INFINITE:
        raise ArgumentError(f"timeout must be finite, got {timeout!r}")
    if timeout <= 0:
        raise ArgumentError(f"timeout must be positive, got {timeout}")
    if timeout > _TIMEOUT_CEILING:
        # ``setitimer`` takes a C.
        # fit one: 1e9 came back as.
        # argument`` and 1e10 as.
        # both as raw tracebacks.
        # all refused cleanly; only the.
        # a year-long bound is not one.
        raise ArgumentError(
            f"timeout must be at most {_TIMEOUT_CEILING} seconds (about a "
            f"month), got {timeout}; a longer one does not fit the "
            f"wall-clock timer"
        )
    if timeout < _TIMEOUT_FLOOR:
        # Measured, not chosen.
        # down again, and below about a.
        # inside that teardown: with.
        # -- which it must be, or a.
        # 19 of 20 processes hammering.
        # outright, and none at all at.
        # each).
        # .
        # So the bound this cannot.
        # and quietly turned into a.
        # the shortest bound anything.
        raise ArgumentError(
            f"timeout must be at least {_TIMEOUT_FLOOR} seconds, got "
            f"{timeout}; the wall-clock guard is a signal and cannot be "
            f"taken down reliably faster than that"
        )


def check_width(width: object) -> None:
    r"""Refuse a width that is not a positive integer."""
    from esolangs.exceptions import ArgumentError

    if width is None:
        return
    if isinstance(width, bool) or not isinstance(width, int):
        raise ArgumentError(f"width must be an integer or None, got {width!r}")
    if width <= 0:
        raise ArgumentError(f"width must be positive, got {width}")


def check_bits(bits: object, what: str = "bits") -> list[int]:
    r"""Return ``bits`` as a list of 0s and 1s, or refuse it."""
    from esolangs.exceptions import ArgumentError

    if isinstance(bits, str) or not isinstance(bits, list | tuple):
        raise ArgumentError(
            f"{what} must be a list or tuple of 0s and 1s, got {type(bits).__name__}"
        )
    if not bits:
        raise ArgumentError(f"{what} must not be empty; a program reads at least one")
    if any(
        isinstance(bit, bool) or not isinstance(bit, int) or bit not in (0, 1)
        for bit in bits
    ):
        if any(isinstance(bit, bool) for bit in bits):
            # Said separately because "must.
            # you passed True, which *is* 1.
            # `bool` is an `int` subclass,.
            # `[True, False]` -- or a.
            # selected a different row of.
            raise ArgumentError(
                f"{what} must be the integers 0 and 1; bools are refused on "
                f"purpose, because True == 1 and a list of them used to be "
                f"accepted as a different row, got {list(bits)!r}"
            )
        raise ArgumentError(f"{what} must each be 0 or 1, got {list(bits)!r}")
    return list(bits)


# : The most cells an.
# :.
# : Sixteen million is far past.
# : far short of what hurts:.
# : is already hundreds of.
_MAX_CELLS = 1 << 24


def check_address(addr: int, language: str) -> int:
    r"""Return ``addr``, refusing one no store should be grown to."""
    from esolangs.exceptions import InterpreterLimitError

    if addr > _MAX_CELLS:
        raise InterpreterLimitError(
            f"{language} would have to grow its store to {addr + 1} cells, "
            f"past the {_MAX_CELLS}-cell limit this interpreter allocates"
        )
    return addr
