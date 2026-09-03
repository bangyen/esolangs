"""Check that every RISC-V backend is registered and uniformly callable.

Compilers used to be discovered by a hand-appended list of module-name
strings inside ``verify_riscv_unicorn.py``.  A backend nobody remembered to
add to that list was simply never verified, and nothing reported its
absence -- the same silent-exemption failure that a hard-coded category
tuple caused in ``check_docstrings.py``, where two whole categories went
unchecked and three real violations hid behind it.

So the check runs in the failing direction: it walks
``src/esolangs/compilers/`` and requires each module to appear in the
registry, rather than walking the registry and trusting it to be complete.
A new backend that nobody registers fails this check.

Each compiler must also expose ``comp`` callable with a single ``code``
argument, so a driver iterating them needs no per-language special case.
Exits nonzero on any violation, so the pre-push hook and CI catch it.
"""

import ast
import importlib
import inspect
import os
import sys

from esolangs.registry import COMPILERS

ROOT = os.path.join(os.path.dirname(__file__), os.pardir, "src", "esolangs")
COMPILER_DIR = os.path.join(ROOT, "compilers")


def _modules() -> list[str]:
    """Return every compiler module, excluding private helpers.

    A leading underscore marks shared plumbing rather than a language
    backend (``_riscv_common.py``), the same convention the docstring
    checker uses to skip ``_template.py``.
    """
    return sorted(
        entry[:-3]
        for entry in os.listdir(COMPILER_DIR)
        if entry.endswith(".py") and not entry.startswith(("_", "."))
    )


def _check(module: str, registered: set[str]) -> list[str]:
    """Return the ways ``module`` departs from the compiler conventions."""
    issues: list[str] = []
    if module not in registered:
        issues.append(
            "is not registered: give some Language a "
            f'compiler="{module}" so the drivers can find it'
        )

    imported = importlib.import_module(f"esolangs.compilers.{module}")
    comp = getattr(imported, "comp", None)
    if comp is None:
        return [*issues, "exposes no comp()"]

    # Callable with exactly one argument: any further parameter must carry a
    # default, or a driver has to special-case this language by name.
    params = list(inspect.signature(comp).parameters.values())
    if not params:
        issues.append("comp() takes no arguments; expected comp(code)")
    else:
        extra = [p.name for p in params[1:] if p.default is inspect.Parameter.empty]
        if extra:
            issues.append(
                f"comp() requires {', '.join(extra)} beyond code; "
                "give it a default so comp(code) works"
            )

    # A __main__ block must not write a fixed filename into the caller's
    # working directory; print to stdout so the output composes.
    path = os.path.join(COMPILER_DIR, f"{module}.py")
    with open(path, encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and node.value == "output.asm":
            issues.append("writes a fixed output.asm; print to stdout instead")
            break
    return issues


def main() -> int:
    """Check every compiler module; return a nonzero exit on violations."""
    registered = set(COMPILERS.values())
    modules = _modules()
    failures = 0
    for module in modules:
        issues = _check(module, registered)
        if issues:
            failures += 1
            print(f"{module}: " + "; ".join(issues))

    # The registry must not name a backend that no longer exists either.
    for stale in sorted(registered - set(modules)):
        failures += 1
        print(f"{stale}: registered as a compiler but no such module exists")

    if failures:
        print(f"\n{failures} compilers violate the conventions")
        return 1
    print(f"all {len(modules)} compilers follow the conventions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
