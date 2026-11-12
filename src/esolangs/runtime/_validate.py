"""Shared validation keeps entry points from drifting."""

from __future__ import annotations

import re

#: The address a default ``repr`` embeds, matched only where it closes the
#: repr's ``>``: quoted text ("['x at 0xdead']", b" at 0xab") is the caller's.
_ADDRESS = re.compile(r" at 0x[0-9a-fA-F]+(?=>)")

_INFINITE = (float("inf"), float("-inf"))

#: The longest wall-clock bound; a thread wait overflows past
#: ``threading.TIMEOUT_MAX``; see :func:`check_timeout`.
_TIMEOUT_CEILING = 2_592_000.0


def _argument_repr(value: object) -> str:
    """Describe rejected values even beyond CPython's decimal rendering cap."""
    try:
        shown = repr(value)
    except ValueError:
        if isinstance(value, int):
            sign = "negative " if value < 0 else ""
            return f"<{sign}integer with {value.bit_length()} bits>"
        if isinstance(value, list):
            return "[" + ", ".join(_argument_repr(item) for item in value) + "]"
        return f"<{type(value).__name__}>"
    except Exception:  # A caller's ``__repr__`` that raises (RuntimeError).
        return f"<{type(value).__name__}>"
    if isinstance(value, str):
        return shown  # The caller's own text, even one reading " at 0x".
    # A default repr carries an address ("<object object at 0x10...>") that
    # differs per run; strip it, keeping the rest ("[<object object>]").
    return _ADDRESS.sub("", shown)


def check_whole(value: object, name: str) -> int:
    """Return ``value`` as a non-negative index, or refuse it by name."""
    from esolangs.exceptions import ArgumentError
    from esolangs.runtime.source_hints import with_hint

    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise with_hint(
            ArgumentError(
                f"{name} must be a non-negative integer, got {_argument_repr(value)}"
            ),
            f"use a non-negative integer, for example {name}=0; "
            "bools and floats are not counts",
        )
    return value


def check_seed(seed: object) -> None:
    """Refuse a seed that is not an integer; ``None`` is allowed.

    A float or a string otherwise reached ``random.Random``, which accepts
    both, so ``seed=1.5`` ran instead of failing like ``max_steps=1.5``.
    """
    from esolangs.exceptions import ArgumentError
    from esolangs.runtime.source_hints import with_hint

    if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int)):
        raise with_hint(
            ArgumentError(
                f"seed must be an integer or None, got {_argument_repr(seed)}"
            ),
            "use an integer seed, for example seed=0",
        )


def check_timeout(timeout: object) -> None:
    """Refuse invalid timeouts; ``None`` is allowed."""
    from esolangs.exceptions import ArgumentError
    from esolangs.runtime.source_hints import with_hint

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
        # Thread waits take this bound: the CLI's source read joins with it
        # and a worker reads records with ``Queue.get``.  Both raised
        # ``OverflowError: timestamp out of range for C PyTime_t`` past
        # ``threading.TIMEOUT_MAX`` (about 9.2e9) -- ``join(1e10)`` and
        # ``get(timeout=1e300)``; a bound that long is not one anybody wants.
        raise with_hint(
            ArgumentError(
                f"timeout must be at most {_TIMEOUT_CEILING} seconds, got "
                f"{_argument_repr(timeout)}; a longer one does not fit "
                "a thread wait"
            ),
            ("set a timeout in seconds, for example timeout=5.0"),
        )


def check_width(width: object) -> None:
    """Refuse a width that is not a positive integer."""
    from esolangs.exceptions import ArgumentError
    from esolangs.runtime.source_hints import with_hint

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
    from esolangs.runtime.source_hints import with_hint

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

    A store to an address far past the limit came back as
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
    from esolangs.runtime.source_hints import with_hint

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


def check_flag(value: object, name: str) -> bool:
    """Return ``value`` if it is a bool; ``isolated="no"`` read as True."""
    from esolangs.exceptions import ArgumentError

    if not isinstance(value, bool):
        raise ArgumentError(
            f"{name} must be True or False, got {_argument_repr(value)}"
        )
    return value
