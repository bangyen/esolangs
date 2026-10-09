"""Languages chosen by what they are, so a shared test names none."""

from typing import Any

import esolangs


def languages(**facts: Any) -> list[str]:
    """Every language whose ``describe()`` has these facts, in list order."""
    return [
        name
        for name in esolangs.list_languages()
        if all(esolangs.describe(name)[key] == value for key, value in facts.items())
    ]


def first(**facts: Any) -> str:
    """The first language with these facts."""
    return languages(**facts)[0]
