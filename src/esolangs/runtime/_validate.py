"""Shared validation keeps entry points from drifting."""

from __future__ import annotations

import re
from collections.abc import Callable
from inspect import Signature, signature
from reprlib import recursive_repr
from sys import getrecursionlimit
from typing import TYPE_CHECKING, TypeGuard

if TYPE_CHECKING:
    from collections.abc import Mapping

# Preserve quoted literals as a group when removing default repr addresses.
_REPR_ADDRESS = re.compile(
    r"""('(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*")| at 0x[0-9a-fA-F]+(?=>)"""
)

_INFINITE = (float("inf"), float("-inf"))

#: The longest wall-clock bound; a thread wait overflows past
#: ``threading.TIMEOUT_MAX``; see :func:`check_timeout`.
_TIMEOUT_CEILING = 2_592_000.0
_ISOLATED_TIMEOUT = 30.0


def _call_signature(callback: Callable[..., object]) -> Signature:
    """Inspect the invoked wrapper, with a fallback for opaque C decorators."""
    seen = {}
    while True:
        try:
            return signature(callback, follow_wrapped=False)
        except ValueError:
            seen[id(callback)] = callback
            wrapped = getattr(callback, "__wrapped__", None)
            if (
                not callable(wrapped)
                or id(wrapped) in seen
                or len(seen) >= getrecursionlimit()
            ):
                raise
            callback = wrapped


def _has_backing_type[T](value: object, kind: type[T]) -> TypeGuard[T]:
    """Use the real type when calling a built-in descriptor directly."""
    return issubclass(type(value), kind)


@recursive_repr(fillvalue="[...]")
def _argument_repr(value: object) -> str:
    """Describe rejected values even beyond CPython's decimal rendering cap."""
    try:
        shown = repr(value)
    except ValueError:
        if _has_backing_type(value, int):
            value = int.__int__(value)
            sign = "negative " if value < 0 else ""
            return f"<{sign}integer with {value.bit_length()} bits>"
        if _has_backing_type(value, list):
            try:
                items = map(_argument_repr, list.__iter__(value))
                return "[" + ", ".join(items) + "]"
            except RecursionError:
                pass
        return f"<{type(value).__name__}>"
    except Exception:  # A caller's ``__repr__`` that raises (RuntimeError).
        return f"<{type(value).__name__}>"
    if _has_backing_type(value, str) or " at 0x" not in shown:
        return shown
    # A default repr carries an address ("<object object at 0x10...>") that
    # differs per run; strip it, keeping the rest ("[<object object>]").
    return _REPR_ADDRESS.sub(r"\1", shown)


def require_text_source(
    source: object, options: Mapping[str, object], language: str
) -> str:
    """Validate the source and options for a whole-text machine."""
    if not isinstance(source, str):
        raise TypeError(f"{language} machines require text source")
    if options:
        raise TypeError(f"{language} machines accept no runtime options")
    return source


def require_split_source(
    source: object, options: Mapping[str, object], language: str
) -> list[str]:
    """Validate the source and options for a split-text machine."""
    if not isinstance(source, list):
        raise TypeError(f"{language} machines require split text source")
    if options:
        raise TypeError(f"{language} machines accept no runtime options")
    return source


def check_whole(value: object, name: str) -> int:
    """Return ``value`` as a non-negative index, or refuse it by name."""
    from esolangs.exceptions import ArgumentError
    from esolangs.runtime.source_hints import with_hint

    if type(value) is not bool and _has_backing_type(value, int):
        value = int.__int__(value)
        if value >= 0:
            return value
    raise with_hint(
        ArgumentError(
            f"{name} must be a non-negative integer, got {_argument_repr(value)}"
        ),
        f"use a non-negative integer, for example {name}=0; "
        "bools and floats are not counts",
    )


def check_memory_size(value: object) -> int:
    """Return the positive whole byte count shared by the limits and worker."""
    from esolangs.exceptions import ArgumentError

    if type(value) is not bool and _has_backing_type(value, int):
        value = int.__int__(value)
        if value > 0:
            return value
    raise ArgumentError(
        f"max_memory must be a positive integer, got {_argument_repr(value)}"
    )


def check_seed(seed: object) -> int | None:
    """Return the integer seed or ``None``.

    A float or a string otherwise reached ``random.Random``, which accepts
    both, so ``seed=1.5`` ran instead of failing like ``max_steps=1.5``.
    """
    from esolangs.exceptions import ArgumentError
    from esolangs.runtime.source_hints import with_hint

    if seed is None:
        return None
    if type(seed) is not bool and _has_backing_type(seed, int):
        return int.__int__(seed)
    raise with_hint(
        ArgumentError(f"seed must be an integer or None, got {_argument_repr(seed)}"),
        "use an integer seed, for example seed=0",
    )


def _timeout_noun(name: str) -> str:
    """Return how a hint names the timeout parameter."""
    return "a timeout" if name == "timeout" else name


def check_timeout(
    timeout: object, name: str = "timeout", *, ceiling: float = _TIMEOUT_CEILING
) -> float | None:
    """Return a validated timeout using the underlying numeric value."""
    from esolangs.exceptions import ArgumentError
    from esolangs.runtime.source_hints import with_hint

    if timeout is None:
        return None
    if type(timeout) is not bool and _has_backing_type(timeout, int):
        timeout = int.__int__(timeout)
    elif _has_backing_type(timeout, float):
        timeout = float.__float__(timeout)
    else:
        raise with_hint(
            ArgumentError(
                f"{name} must be a number or None, got {_argument_repr(timeout)}"
            ),
            (f"set {_timeout_noun(name)} in seconds, for example {name}=5.0"),
        )
    if timeout != timeout or timeout in _INFINITE:
        raise with_hint(
            ArgumentError(f"{name} must be finite, got {_argument_repr(timeout)}"),
            (f"set {_timeout_noun(name)} in seconds, for example {name}=5.0"),
        )
    if timeout <= 0:
        raise with_hint(
            ArgumentError(f"{name} must be positive, got {_argument_repr(timeout)}"),
            (f"set {_timeout_noun(name)} in seconds, for example {name}=5.0"),
        )
    if timeout > ceiling:
        # Thread waits take this bound: the CLI's source read joins with it
        # and a worker reads records with ``Queue.get``.  Both raised
        # ``OverflowError: timestamp out of range for C PyTime_t`` past
        # ``threading.TIMEOUT_MAX`` (about 9.2e9) -- ``join(1e10)`` and
        # ``get(timeout=1e300)``; a bound that long is not one anybody wants.
        raise with_hint(
            ArgumentError(
                f"{name} must be at most {ceiling} seconds, got "
                f"{_argument_repr(timeout)}; a longer one does not fit "
                "a thread wait"
            ),
            (f"set {_timeout_noun(name)} in seconds, for example {name}=5.0"),
        )
    return timeout


def check_width(width: object) -> int | None:
    """Return a positive integer width or the default layout request."""
    from esolangs.exceptions import ArgumentError
    from esolangs.runtime.source_hints import with_hint

    if width is None:
        return None
    if type(width) is bool or not _has_backing_type(width, int):
        raise with_hint(
            ArgumentError(
                f"width must be an integer or None, got {_argument_repr(width)}"
            ),
            ("use a positive integer column width, for example width=80"),
        )
    width = int.__int__(width)
    if width <= 0:
        raise with_hint(
            ArgumentError(f"width must be positive, got {_argument_repr(width)}"),
            ("use a positive integer column width, for example width=80"),
        )
    return width


def check_bit_count(bits: list[int], inputs: int, subject: str) -> None:
    """Refuse a bit list whose length is not ``subject``'s input count."""
    from esolangs.exceptions import ArgumentError

    if len(bits) != inputs:
        given = f"{len(bits)} bit{' was' if len(bits) == 1 else 's were'} given"
        raise ArgumentError(
            f"this {subject} has {_argument_repr(inputs)} "
            f"input{'' if inputs == 1 else 's'}, but {given}"
        )


def check_bits(
    bits: object, what: str = "bits", *, allow_empty: bool = False
) -> list[int]:
    """Validate and freeze integer bits, optionally accepting a zero-input row."""
    from esolangs.exceptions import ArgumentError
    from esolangs.runtime.source_hints import with_hint

    if _has_backing_type(bits, list):
        entries = list.__iter__(bits)
    elif _has_backing_type(bits, tuple):
        entries = tuple.__iter__(bits)
    else:
        raise with_hint(
            ArgumentError(
                f"{what} must be a list or tuple of 0s and 1s, "
                f"got {type(bits).__name__}"
            ),
            ("pass integer bits as a list or tuple, for example [0, 1]"),
        )
    values = [
        int.__int__(bit)
        if type(bit) is not int
        and type(bit) is not bool
        and _has_backing_type(bit, int)
        else bit
        for bit in entries
    ]
    if not values and not allow_empty:
        raise with_hint(
            ArgumentError(f"{what} must not be empty; a program reads at least one"),
            ("pass integer bits as a list or tuple, for example [0, 1]"),
        )
    if any(type(bit) is not int or bit not in (0, 1) for bit in values):
        if any(type(bit) is bool for bit in values):
            # Said separately because "must be 0 or 1" reads as wrong when
            # you passed True.  Before this check `[True, False]` and
            # `[1.0, 0.0]` were accepted and selected a different row.
            raise with_hint(
                ArgumentError(
                    f"{what} must be the integers 0 and 1; bools are refused on "
                    f"purpose, because True == 1 and a list of them used to be "
                    f"accepted as a different row, got {_argument_repr(values)}"
                ),
                ("pass integer bits as a list or tuple, for example [0, 1]"),
            )
        raise with_hint(
            ArgumentError(f"{what} must each be 0 or 1, got {_argument_repr(values)}"),
            ("pass integer bits as a list or tuple, for example [0, 1]"),
        )
    return values


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


def check_input_arity(arity: object) -> int:
    """Normalize a positive integer supplied through a typed API."""
    from esolangs.exceptions import ArgumentError

    if type(arity) is not bool and _has_backing_type(arity, int):
        value = int.__int__(arity)
        if value > 0:
            return value
    raise ArgumentError("input_arity must be a positive integer")


def check_scale(scale: object) -> int:
    """Return a positive integer pixel replication factor."""
    from esolangs.exceptions import ArgumentError
    from esolangs.runtime.source_hints import with_hint

    value = (
        int.__int__(scale)
        if type(scale) is not bool and _has_backing_type(scale, int)
        else 0
    )
    if value < 1:
        raise with_hint(
            ArgumentError(
                f"scale must be a positive integer, got {_argument_repr(scale)}"
            ),
            (
                "use scale=1 for the original raster size or "
                "an integer replication factor"
            ),
        )
    return value


def check_flag(value: object, name: str) -> bool:
    """Return ``value`` if it is a bool; ``isolated="no"`` read as True."""
    from esolangs.exceptions import ArgumentError

    if type(value) is not bool:
        raise ArgumentError(
            f"{name} must be True or False, got {_argument_repr(value)}"
        )
    return value
