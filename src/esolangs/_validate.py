"""Argument checks shared by every entry point that takes them.

These live in a leaf module rather than beside their callers because that
is the only arrangement that keeps them honest.  Twice now the same check
has been written on one side of a pair and not the other:
:meth:`esolangs.debugger.Debugger.run` validated its ``timeout`` while
:func:`esolangs.run` did not, and the commit that fixed *that* added a
shared checker to the package root -- which the debugger could not import
without a cycle, so it kept its own copy and the copies diverged again.
The second divergence was worse than the first: ``timeout=inf`` and
``timeout=nan`` both passed the debugger's ``timeout <= 0`` test, and a
deadline of ``monotonic() + inf`` is one no run ever reaches, so bounding a
runaway with either hung the process outright.

So: one definition, imported by both, depending on nothing but the
exceptions.
"""

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
    """Refuse a timeout that is not a positive, finite number.

    ``inf`` and ``nan`` are refused explicitly.  Neither is caught by a
    ``<= 0`` test -- ``nan`` compares false against everything -- and both
    produce a deadline that never arrives, which turns the bound meant to
    stop a runaway into the thing that lets it run forever.
    """
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
        # a year-long bound is not one anybody wants anyway.
        raise ArgumentError(
            f"timeout must be at most {_TIMEOUT_CEILING} seconds (about a "
            f"month), got {timeout}; a longer one does not fit the "
            f"wall-clock timer"
        )
    if timeout < _TIMEOUT_FLOOR:
        # Measured, not chosen.  The guard arms a ``SIGALRM`` and takes it
        # down again, and below about a millisecond the alarm starts landing
        # inside that teardown: with the caller's own disposition restored
        # -- which it must be, or a later alarm of theirs is swallowed --
        # 19 of 20 processes hammering a 100-microsecond bound were killed
        # outright, and none at all at a millisecond or above (4000 runs
        # each).
        #
        # So the bound this cannot service is refused rather than offered
        # and quietly turned into a death.  Nothing realistic asks for one:
        # the shortest bound anything in this package uses is five seconds.
        raise ArgumentError(
            f"timeout must be at least {_TIMEOUT_FLOOR} seconds, got "
            f"{timeout}; the wall-clock guard is a signal and cannot be "
            f"taken down reliably faster than that"
        )


def check_width(width: object) -> None:
    """Refuse a width that is not a positive integer.

    Shared by :func:`esolangs.generate` and :func:`esolangs.instantiate`:
    they are the same option on the same program, and only one of them used
    to check it.
    """
    from esolangs.exceptions import ArgumentError

    if width is None:
        return
    if isinstance(width, bool) or not isinstance(width, int):
        raise ArgumentError(f"width must be an integer or None, got {width!r}")
    if width <= 0:
        raise ArgumentError(f"width must be positive, got {width}")


def check_bits(bits: object, what: str = "bits") -> list[int]:
    """Return ``bits`` as a list of 0s and 1s, or refuse it.

    The container as well as the elements.  ``None`` leaked ``'NoneType'
    object is not iterable``, and a ``dict`` was accepted and iterated as
    its *keys* -- ``{0: 1, 1: 0}`` produced the program for ``[0, 1]``,
    which is a different row of the table.  ``bit not in (0, 1)`` alone
    also lets ``1.0`` and ``True`` through, since both equal 1.
    """
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
            # you passed True, which *is* 1.  The exclusion is deliberate:
            # `bool` is an `int` subclass, so before this check a
            # `[True, False]` -- or a `[1.0, 0.0]` -- was accepted and
            # selected a different row of the table.
            raise ArgumentError(
                f"{what} must be the integers 0 and 1; bools are refused on "
                f"purpose, because True == 1 and a list of them used to be "
                f"accepted as a different row, got {list(bits)!r}"
            )
        raise ArgumentError(f"{what} must each be 0 or 1, got {list(bits)!r}")
    return list(bits)
