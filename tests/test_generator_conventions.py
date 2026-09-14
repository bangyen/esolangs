"""Public boolean generators keep their uniform callable shape."""

import inspect
from collections.abc import Callable
from typing import Any

import esolangs.tools as boolean

_ALLOWED = {"circlefuck_byte", "jaune_multiply"}


def _public(module: object) -> list[tuple[str, Callable[..., Any]]]:
    """Return the public generator callables a package exports."""
    return [
        (name, getattr(module, name))
        for name in module.__all__
        if not name.startswith("_")
        and callable(getattr(module, name, None))
        and name not in {"instantiate", "main"}
    ]


def test_boolean_generators_take_a_truth_table() -> None:
    """Each non-exempt generator takes ``truth_table`` and no required extra."""
    failures = {}
    exported = dict(_public(boolean))
    for name, fn in exported.items():
        if name in _ALLOWED:
            continue
        params = list(inspect.signature(fn).parameters.values())
        issues = []
        if not params:
            issues.append("takes no arguments")
        elif params[0].name != "truth_table":
            issues.append(f"first parameter is {params[0].name!r}")
        issues.extend(
            f"requires {param.name!r} beyond truth_table"
            for param in params[1:]
            if param.default is inspect.Parameter.empty
        )
        if issues:
            failures[name] = issues
    assert not failures
    assert exported.keys() >= _ALLOWED
