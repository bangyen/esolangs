"""Input containers normalized without imposing a language input unit."""

from __future__ import annotations

from typing import Protocol

from esolangs.exceptions import ArgumentError


class Reader(Protocol):
    """A text or binary stream consumed from its current position."""

    def read(self) -> str | bytes: ...


type InputSource = str | bytes | Reader


def check_input(source: InputSource) -> None:
    """Check the input container without consuming a stream."""
    if not isinstance(source, (str, bytes)) and not callable(
        getattr(source, "read", None)
    ):
        raise ArgumentError(
            "stdin must be a string, bytes, or a readable stream, got "
            f"{type(source).__name__}"
        )


def read_input(source: InputSource) -> str:
    """Snapshot remaining input; binary input is UTF-8 text."""
    check_input(source)
    try:
        value = source if isinstance(source, (str, bytes)) else source.read()
        if isinstance(value, bytes):
            return value.decode("utf-8")
        if isinstance(value, str):
            return value
    except (OSError, TypeError, ValueError) as exc:
        raise ArgumentError(f"cannot read stdin: {exc}") from exc
    raise ArgumentError("stdin stream must return a string or bytes")
