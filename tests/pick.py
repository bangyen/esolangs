"""Languages chosen by what they are, so a shared test names none."""

from collections.abc import Callable
from typing import Any

import pytest

import esolangs


def languages(**facts: Any) -> list[str]:
    """Every language whose ``describe()`` has these facts, in list order."""
    return [
        name
        for name in esolangs.list_languages()
        if all(esolangs.describe(name)[key] == value for key, value in facts.items())
    ]


def first(**facts: Any) -> str:
    """The first language with these facts; inside a test, a skip if none.

    At import time an empty pick is an error, so a module-level pick of a
    fact only one language has goes through :func:`one` instead.
    """
    found = languages(**facts)
    if not found:
        pytest.skip(f"no registered language has {facts}")
    return found[0]


def one(**facts: Any) -> list[str]:
    """:func:`first` as a list, empty when no language has the facts.

    For ``parametrize``: an empty list skips the test instead of failing
    collection, so removing the only language with a fact skips its tests.
    """
    return languages(**facts)[:1]


def one_where(test: Callable[[dict[str, Any]], bool], **facts: Any) -> list[str]:
    """:func:`one`, narrowed further by ``test`` on the ``describe()`` dict."""
    return [n for n in languages(**facts) if test(esolangs.describe(n))][:1]


def spread(*keys: str, **facts: Any) -> list[str]:
    """The first language for each distinct combination of ``keys``' values.

    One per way of doing something -- each input shape, each answer mode --
    so a test covers every mechanism the registry has, and a mechanism that
    leaves with its last language simply drops out.
    """
    seen: dict[tuple[object, ...], str] = {}
    for name in languages(**facts):
        described = esolangs.describe(name)
        seen.setdefault(tuple(described[key] for key in keys), name)
    return list(seen.values())
