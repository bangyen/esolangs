"""Transitive package visibility for Packlang calls."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.interpreters.other.packlang import _Function, _Program


def _visible(func: _Function, caller: str, program: _Program) -> bool:
    """Whether ``caller``'s package may call ``func``.

    A package reaches its own functions and those of the packages it
    depends on.  The wiki says dependencies may themselves have
    dependencies, so the relation is followed transitively rather than one
    level deep.
    """
    if func.package == caller:
        return True
    seen: set[str] = set()
    frontier = [caller]
    while frontier:
        package = frontier.pop()
        if package in seen:
            continue
        seen.add(package)
        if package == func.package:
            return True
        frontier.extend(program.dependencies.get(package, frozenset()))
    return func.package in seen
