"""Check that every transpiler is registered and uniformly callable.

A transpiler is a *relation* between two languages, so it is keyed by a
``(source, target)`` pair in a single ``TRANSPILERS`` table rather than by
module.  There is no directory to walk, and the failure it must catch is an
unregistered *pair*: one naming a language the registry does not have.

That is a real silent exemption.  ``esolangs.transpile`` looks both names up
in ``LANGUAGES`` to reach the interpreters, so a pair whose name is misspelled
-- or that outlives a language rename -- is unreachable through the public
API while still sitting in the table looking supported.  Nothing reported it
before this check.

So the check runs in the failing direction on the names: every endpoint of
every registered pair must resolve in ``LANGUAGES``, and the source and
target must differ.  Each transpiler must also be callable as ``fn(program)``
and be exported, so a driver iterating the table needs no special case.

Exits nonzero on any violation, so the pre-push hook and CI catch it.
"""

import inspect
import sys

import esolangs.transpilers as transpilers
from esolangs.registry import LANGUAGES
from esolangs.transpilers import TRANSPILERS


def _check(pair: tuple[str, str], fn: object) -> list[str]:
    """Return the ways the ``pair`` entry departs from the conventions."""
    issues: list[str] = []
    source, target = pair

    # Both endpoints must name a real language: esolangs.transpile resolves
    # them through LANGUAGES, so an unknown name is unreachable in practice.
    for role, name in (("source", source), ("target", target)):
        if name not in LANGUAGES:
            issues.append(
                f"names {role} {name!r}, which is not a registered language; "
                "use the name its Language entry carries"
            )
    if source == target:
        issues.append(f"maps {source!r} to itself")

    if not callable(fn):
        return [*issues, "is not callable"]

    # Callable with exactly one argument: any further parameter must carry a
    # default.
    params = list(inspect.signature(fn).parameters.values())
    if not params:
        issues.append("takes no arguments; expected fn(program)")
    else:
        extra = [p.name for p in params[1:] if p.default is inspect.Parameter.empty]
        if extra:
            issues.append(
                f"requires {', '.join(extra)} beyond program; "
                "give it a default so fn(program) works"
            )

    # Exported, so the table and the module's public surface cannot drift.
    exported = getattr(fn, "__name__", None)
    if exported is not None and exported not in transpilers.__all__:
        issues.append(f"{exported} is missing from __all__")
    return issues


def main() -> int:
    """Check every registered transpiler; return nonzero on violations."""
    failures = 0
    for pair, fn in sorted(TRANSPILERS.items()):
        issues = _check(pair, fn)
        if issues:
            failures += 1
            print(f"{pair[0]} -> {pair[1]}: " + "; ".join(issues))

    # __all__ must not promise a transpiler the table no longer carries.
    registered = {getattr(fn, "__name__", "") for fn in TRANSPILERS.values()}
    for stale in sorted(set(transpilers.__all__) - registered - {"TRANSPILERS"}):
        failures += 1
        print(f"{stale}: exported but not in TRANSPILERS")

    if failures:
        print(f"\n{failures} transpilers violate the conventions")
        return 1
    print(f"all {len(TRANSPILERS)} transpilers follow the conventions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
