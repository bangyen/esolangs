"""Packlang store lookup and checked scalar/expression values."""

from esolangs.exceptions import HaltError
from esolangs.interpreters.source_hints import keyword_hint

type _Expr = tuple[object, ...]
type _Store = tuple[tuple[str, object], ...]


def _get(store: _Store, name: str) -> object:
    for slot, value in store:
        if slot == name:
            return value
    raise HaltError(
        f"undefined variable {name!r}",
        hint=keyword_hint(
            name,
            (slot for slot, _ in store),
            "declare the variable before reading it; check its spelling",
        ),
    )


def _set(store: _Store, name: str, value: object) -> _Store:
    return tuple((slot, value if slot == name else old) for slot, old in store)


def _truth(value: int) -> bool:
    return value != 0


def _node(value: object) -> _Expr:
    """Narrow heterogeneous parser slots; a wrong shape is an internal tree error."""
    if not isinstance(value, tuple):
        raise HaltError(f"malformed expression node {value!r}")
    return value


def _int(value: object) -> int:
    """Narrow a literal or a stored scalar to an ``int``."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise HaltError(
            f"expected a number, got {value!r}",
            hint="use a numeric value in this expression",
        )
    return value
