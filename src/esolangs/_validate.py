"""Shared validation keeps entry points from drifting."""

from __future__ import annotations

_INFINITE = (float("inf"), float("-inf"))

#: The shortest wall-clock bound the ``SIGALRM`` guard can service.  See
#: :func:`check_timeout` for the measurement behind the number.
_TIMEOUT_FLOOR = 0.001

#: The longest one it can take.  ``setitimer``'s interval is a C type and
#: a large enough float overflows it; see :func:`check_timeout`.
_TIMEOUT_CEILING = 2_592_000.0


def _argument_repr(value: object) -> str:
    """Describe rejected values even beyond CPython's decimal rendering cap."""
    try:
        return repr(value)
    except ValueError:
        if isinstance(value, int):
            sign = "negative " if value < 0 else ""
            return f"<{sign}integer with {value.bit_length()} bits>"
        if isinstance(value, list):
            return "[" + ", ".join(_argument_repr(item) for item in value) + "]"
        return f"<{type(value).__name__}>"


def check_whole(value: object, name: str) -> int:
    """Return ``value`` as a non-negative index, or refuse it by name."""
    from esolangs.exceptions import ArgumentError
    from esolangs.interpreters.source_hints import with_hint

    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise with_hint(
            ArgumentError(
                f"{name} must be a non-negative integer, got {_argument_repr(value)}"
            ),
            f"use a non-negative integer, for example {name}=0; "
            "bools and floats are not counts",
        )
    return value


def check_timeout(timeout: object) -> None:
    """Refuse invalid timeouts; ``None`` is allowed."""
    from esolangs.exceptions import ArgumentError
    from esolangs.interpreters.source_hints import with_hint

    if timeout is None:
        return
    if isinstance(timeout, bool) or not isinstance(timeout, int | float):
        raise with_hint(
            ArgumentError(
                f"timeout must be a number or None, got {_argument_repr(timeout)}"
            ),
            ("set a timeout in seconds, for example timeout=5.0"),
        )
    if timeout != timeout or timeout in _INFINITE:
        raise with_hint(
            ArgumentError(f"timeout must be finite, got {_argument_repr(timeout)}"),
            ("set a timeout in seconds, for example timeout=5.0"),
        )
    if timeout <= 0:
        raise with_hint(
            ArgumentError(f"timeout must be positive, got {_argument_repr(timeout)}"),
            ("set a timeout in seconds, for example timeout=5.0"),
        )
    if timeout > _TIMEOUT_CEILING:
        # ``setitimer`` takes a C interval, and a big enough float does not
        # fit one: 1e9 came back as ``ItimerError: [Errno 22] Invalid
        # argument`` and 1e10 as ``OverflowError: timestamp out of range``,
        # both as raw tracebacks.  Zero, negatives, ``inf`` and ``nan`` were
        # all refused cleanly; only the large finite case fell through, and
        # a bound that long is not one anybody wants anyway.
        raise with_hint(
            ArgumentError(
                f"timeout must be at most {_TIMEOUT_CEILING} seconds, got "
                f"{_argument_repr(timeout)}; a longer one does not fit "
                "the wall-clock timer"
            ),
            ("set a timeout in seconds, for example timeout=5.0"),
        )
    if timeout < _TIMEOUT_FLOOR:
        # Measured: below about a millisecond the alarm lands inside the
        # guard's own teardown -- 19 of 20 processes hammering a
        # 100-microsecond bound were killed outright, none at a millisecond
        # or above (4000 runs each).  The shortest bound this package uses
        # is five seconds.
        raise with_hint(
            ArgumentError(
                f"timeout must be at least {_TIMEOUT_FLOOR} seconds, got "
                f"{_argument_repr(timeout)}; the wall-clock guard is a signal "
                "and cannot be "
                f"taken down reliably faster than that"
            ),
            ("set a timeout in seconds, for example timeout=5.0"),
        )


def check_width(width: object) -> None:
    """Refuse a width that is not a positive integer."""
    from esolangs.exceptions import ArgumentError
    from esolangs.interpreters.source_hints import with_hint

    if width is None:
        return
    if isinstance(width, bool) or not isinstance(width, int):
        raise with_hint(
            ArgumentError(
                f"width must be an integer or None, got {_argument_repr(width)}"
            ),
            ("use a positive integer column width, for example width=80"),
        )
    if width <= 0:
        raise with_hint(
            ArgumentError(f"width must be positive, got {_argument_repr(width)}"),
            ("use a positive integer column width, for example width=80"),
        )


def check_bits(bits: object, what: str = "bits") -> list[int]:
    """Return a nonempty list or tuple of integer bits, or refuse it."""
    from esolangs.exceptions import ArgumentError
    from esolangs.interpreters.source_hints import with_hint

    if isinstance(bits, str) or not isinstance(bits, list | tuple):
        raise with_hint(
            ArgumentError(
                f"{what} must be a list or tuple of 0s and 1s, "
                f"got {type(bits).__name__}"
            ),
            ("pass integer bits as a list or tuple, for example [0, 1]"),
        )
    if not bits:
        raise with_hint(
            ArgumentError(f"{what} must not be empty; a program reads at least one"),
            ("pass integer bits as a list or tuple, for example [0, 1]"),
        )
    if any(
        isinstance(bit, bool) or not isinstance(bit, int) or bit not in (0, 1)
        for bit in bits
    ):
        if any(isinstance(bit, bool) for bit in bits):
            # Said separately because "must be 0 or 1" reads as wrong when
            # you passed True.  Before this check `[True, False]` and
            # `[1.0, 0.0]` were accepted and selected a different row.
            raise with_hint(
                ArgumentError(
                    f"{what} must be the integers 0 and 1; bools are refused on "
                    f"purpose, because True == 1 and a list of them used to be "
                    f"accepted as a different row, got {_argument_repr(list(bits))}"
                ),
                ("pass integer bits as a list or tuple, for example [0, 1]"),
            )
        raise with_hint(
            ArgumentError(
                f"{what} must each be 0 or 1, got {_argument_repr(list(bits))}"
            ),
            ("pass integer bits as a list or tuple, for example [0, 1]"),
        )
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

    if addr >= _MAX_CELLS:
        raise InterpreterLimitError(
            f"{language} would have to grow its store to "
            f"{_argument_repr(addr + 1)} cells, "
            f"past the {_MAX_CELLS}-cell limit this interpreter allocates",
            hint="use smaller memory addresses to fit the interpreter allocation limit",
        )
    return addr


def check_scale(scale: object) -> int:
    """Return a positive integer pixel replication factor."""
    from esolangs.exceptions import ArgumentError
    from esolangs.interpreters.source_hints import with_hint

    if isinstance(scale, bool) or not isinstance(scale, int) or scale < 1:
        raise with_hint(
            ArgumentError(
                f"scale must be a positive integer, got {_argument_repr(scale)}"
            ),
            (
                "use scale=1 for the original raster size or "
                "an integer replication factor"
            ),
        )
    return scale
