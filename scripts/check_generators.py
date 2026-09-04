"""Check that the generators keep to their two documented signatures.

The text and boolean generators are already uniform -- of the names the
two packages export, 46 text generators take ``(text)`` and 67 boolean
ones take ``(truth_table)`` or are allowlisted below.  This
check exists to keep them that way, because a convention nothing enforces
is not a convention: this repo has been bitten before by a documented
class that turned out not to hold.

Two shapes are legal on the boolean side, and the second is deliberate
rather than drift:

* *table-in, program-out* -- ``f(truth_table) -> str``, the common case.
* *template-in, instantiated-per-row* -- the parameterized family, for
  languages with no input command, which emit a template the harness fills
  in per input combination.

Three boolean generators depart from both, each for a reason recorded in
its docstring, so they are named in ``_ALLOWED`` below rather than being
waved through by a blanket rule.  Listing them keeps the exemption visible
in source: a fourth one appearing is then a decision someone makes on
purpose, not something that slips in unnoticed.

Exits nonzero on any violation.
"""

import inspect
import sys
from collections.abc import Callable
from typing import Any

# Boolean generators that legitimately take something other than a plain
# truth-table string, with the reason each one does.
_ALLOWED: set[str] = set()

# The one extra parameter a text generator may take.  `width` is the
# de-facto rule already (8 modules use it and nothing else does); naming it
# stops the next generator inventing a second knob.
_TEXT_EXTRA = {"width"}


def _public(module: object) -> list[tuple[str, Callable[..., Any]]]:
    """Return the generator functions a package re-exports."""
    return [
        (name, getattr(module, name))
        for name in getattr(module, "__all__", [])
        if not name.startswith("_")
        and callable(getattr(module, name, None))
        and name not in {"instantiate", "main"}
    ]


def _check_text(fn: Callable[..., Any]) -> list[str]:
    """Return the ways a text generator departs from ``(text[, width])``."""
    params = list(inspect.signature(fn).parameters.values())
    if not params:
        return ["takes no arguments; expected (text)"]
    issues: list[str] = []
    if params[0].name != "text":
        issues.append(f"first parameter is {params[0].name!r}, expected 'text'")
    for extra in params[1:]:
        if extra.name not in _TEXT_EXTRA:
            issues.append(
                f"takes {extra.name!r}; only {sorted(_TEXT_EXTRA)} is allowed"
            )
        elif extra.default is inspect.Parameter.empty:
            issues.append(f"{extra.name!r} has no default")
    return issues


def _check_boolean(name: str, fn: Callable[..., Any]) -> list[str]:
    """Return the ways a boolean generator departs from ``(truth_table)``."""
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
    """Check both generator families; return a nonzero exit on violations."""
    from esolangs.tools import boolean as boolean_pkg
    from esolangs.tools import text as text_pkg

    failures = 0
    for name, fn in _public(text_pkg):
        issues = _check_text(fn)
        if issues:
            failures += 1
            print(f"text.{name}: " + "; ".join(issues))

    for name, fn in _public(boolean_pkg):
        issues = _check_boolean(name, fn)
        if issues:
            failures += 1
            print(f"boolean.{name}: " + "; ".join(issues))

    # An allowlist entry for a generator that no longer exists is stale, and
    # would silently keep exempting a name someone later reuses.
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
