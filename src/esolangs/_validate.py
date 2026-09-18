"""Shared validation keeps entry points from drifting."""

from __future__ import annotations

_INFINITE = (float("inf"), float("-inf"))

#: The shortest wall-clock bound the ``SIGALRM`` guard can service.  See
#: :func:`check_timeout` for the measurement behind the number.
_TIMEOUT_FLOOR = 0.001

#: The longest one it can take.  ``setitimer``'s interval is a C type and
#: a large enough float overflows it; see :func:`check_timeout`.
_TIMEOUT_CEILING = 2_592_000.0


def check_whole(value: object, name: str) -> int:
    """Return ``value`` as a non-negative index, or refuse it by name."""
    from esolangs.exceptions import ArgumentError

    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ArgumentError(f"{name} must be a non-negative integer, got {value!r}")
    return value


def check_timeout(timeout: object) -> None:
    """Refuse invalid timeouts; ``None`` is allowed."""
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
        # ``setitimer`` takes a C interval, and a big enough float does not
        # fit one: 1e9 came back as ``ItimerError: [Errno 22] Invalid
        # argument`` and 1e10 as ``OverflowError: timestamp out of range``,
        # both as raw tracebacks.  Zero, negatives, ``inf`` and ``nan`` were
        # all refused cleanly; only the large finite case fell through, and
        # a bound that long is not one anybody wants anyway.
        raise ArgumentError(
            f"timeout must be at most {_TIMEOUT_CEILING} seconds, got "
            f"{timeout}; a longer one does not fit the wall-clock timer"
        )
    if timeout < _TIMEOUT_FLOOR:
        # Measured: below about a millisecond the alarm lands inside the
        # guard's own teardown -- 19 of 20 processes hammering a
        # 100-microsecond bound were killed outright, none at a millisecond
        # or above (4000 runs each).  The shortest bound this package uses
        # is five seconds.
        raise ArgumentError(
            f"timeout must be at least {_TIMEOUT_FLOOR} seconds, got "
            f"{timeout}; the wall-clock guard is a signal and cannot be "
            f"taken down reliably faster than that"
        )


def check_width(width: object) -> None:
    """Refuse a width that is not a positive integer."""
    from esolangs.exceptions import ArgumentError

    if width is None:
        return
    if isinstance(width, bool) or not isinstance(width, int):
        raise ArgumentError(f"width must be an integer or None, got {width!r}")
    if width <= 0:
        raise ArgumentError(f"width must be positive, got {width}")


def check_bits(bits: object, what: str = "bits") -> list[int]:
    """Return a nonempty list or tuple of integer bits, or refuse it."""
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
            # Said separately because "must be 0 or 1" reads as wrong when
            # you passed True.  Before this check `[True, False]` and
            # `[1.0, 0.0]` were accepted and selected a different row.
            raise ArgumentError(
                f"{what} must be the integers 0 and 1; bools are refused on "
                f"purpose, because True == 1 and a list of them used to be "
                f"accepted as a different row, got {list(bits)!r}"
            )
        raise ArgumentError(f"{what} must each be 0 or 1, got {list(bits)!r}")
    return list(bits)


#: The most cells an interpreter will grow its store to.
#:
#: Sixteen million is far past anything a generated program addresses and
#: far short of what hurts: the store is a tuple of Python ints, so this
#: is already hundreds of megabytes.
_MAX_CELLS = 1 << 24


def check_address(addr: int, language: str) -> int:
    """Return ``addr``, refusing one no store should be grown to.

    ``run("S*bleq", "100000000000000000000 0 0")`` came back as
    ``OverflowError`` (and ``MemoryError`` one magnitude down), escaping
    the ``EsolangError`` promise and unstoppable by ``timeout``.  Refused
    before allocating, since a roomier machine thrashes instead.
    """
    from esolangs.exceptions import InterpreterLimitError

    if addr > _MAX_CELLS:
        raise InterpreterLimitError(
            f"{language} would have to grow its store to {addr + 1} cells, "
            f"past the {_MAX_CELLS}-cell limit this interpreter allocates"
        )
    return addr
