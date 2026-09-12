r"""Check that the generators keep to their documented signature."""

import inspect
import sys
from collections.abc import Callable
from typing import Any

# Boolean generators that.
# truth-table string, with the.
_ALLOWED = {
    # A byte-valued generalization:.
    # so its table is a sequence of.
    "circlefuck_byte",
    # One construction multiplies.
    # is a property of the input.
    # truth table to take.
    "jaune_multiply",
}


def _public(module: object) -> list[tuple[str, Callable[..., Any]]]:
    r"""Return the generator functions a package re-exports."""
    return [
        (name, getattr(module, name))
        for name in getattr(module, "__all__", [])
        if not name.startswith("_")
        and callable(getattr(module, name, None))
        and name not in {"instantiate", "main"}
    ]


def _check_boolean(name: str, fn: Callable[..., Any]) -> list[str]:
    r"""Return the ways a boolean generator departs from ``(truth_table)``."""
    if name in _ALLOWED:
        return []
    params = list(inspect.signature(fn).parameters.values())
    if not params:
        return ["takes no arguments; expected (truth_table)"]
    issues: list[str] = []
    if params[0].name != "truth_table":
        issues.append(f"first parameter is {params[0].name!r}, expected 'truth_table'")
    for extra in params[1:]:
        if extra.default is inspect.Parameter.empty:
            issues.append(
                f"requires {extra.name!r} beyond truth_table; give it a default"
            )
    return issues


def main() -> int:
    r"""Check the generators; return a nonzero exit on violations."""
    from esolangs.tools import boolean as boolean_pkg

    failures = 0
    for name, fn in _public(boolean_pkg):
        issues = _check_boolean(name, fn)
        if issues:
            failures += 1
            print(f"boolean.{name}: " + "; ".join(issues))

    # An allowlist entry for a.
    # would silently keep exempting.
    exported = {name for name, _ in _public(boolean_pkg)}
    for stale in sorted(_ALLOWED - exported):
        failures += 1
        print(f"boolean.{stale}: allowlisted but not exported any more")

    if failures:
        print(f"\n{failures} generators violate the conventions")
        return 1
    print("all generators follow the conventions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
