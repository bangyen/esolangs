"""Check that the generators keep to their documented signature.

The boolean generators are already uniform -- of the names the package
exports, 67 take ``(truth_table)`` or are allowlisted below.  This check
exists to keep them that way, because a convention nothing enforces is not
a convention: this repo has been bitten before by a documented class that
turned out not to hold.

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
_ALLOWED = {
    # A byte-valued generalization: leaves print chr(value), not chr(48+bit),
    # so its table is a sequence of byte values rather than a bit string.
    "circlefuck_byte",
    # One construction multiplies any two decimal operands, so operand length
    # is a property of the input rather than of the function; there is no
    # truth table to take.
    "jaune_multiply",
}


def _public(module: object) -> list[tuple[str, Callable[..., Any]]]:
    """Return the generator functions a package re-exports."""
    return [
        (name, getattr(module, name))
        for name in getattr(module, "__all__", [])
        if not name.startswith("_")
        and callable(getattr(module, name, None))
        and name not in {"instantiate", "main"}
    ]


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
    """Check the generators; return a nonzero exit on violations."""
    from esolangs.tools import boolean as boolean_pkg

    failures = 0
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
