"""Assert that no interpreter leaks a raw Python exception to its caller.

``esolangs/exceptions.py`` states the contract: an interpreter halts with
:class:`HaltError` "instead of leaking an incidental Python error", and a
structurally malformed program is rejected with :class:`ValueError`.
Exhausted input raises :class:`EOFError` (the repo-wide convention), and
Container halts by exiting, so :class:`SystemExit` is its documented end.
Anything else reaching the caller -- IndexError, TypeError, OverflowError,
KeyError -- is a bug in the interpreter, not in the program it was given.

The corpus is deliberately hostile but *derived from real programs*: the
generic fragments below, plus every shipped example for the language, plus
mutations of those examples (truncated, a character dropped, one doubled,
one inserted).  Truncation is what finds the interesting cases -- a
half-written program reaches states no hand-written test thinks to build.

By default only the languages this branch actually touched are swept,
which is what makes it cheap enough to run habitually: a change to one
interpreter is checked in seconds, and a change to shared machinery
(``io.py``, ``vm.py``, ``exceptions.py``) still sweeps everything, since
that is exactly where a one-line bug reaches all 59 languages at once --
as the ``input_char`` bug this script was written to catch did.

Run::

    python scripts/verify_no_exception_leaks.py            # touched languages
    python scripts/verify_no_exception_leaks.py --all      # every language
    python scripts/verify_no_exception_leaks.py --all out.json
"""

import json
import pathlib
import random
import sys
import time

_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from esolangs.exceptions import EsolangError
from esolangs.vm import make_vm

# Exceptions an interpreter is allowed to raise at the API boundary.
ALLOWED = (EsolangError, ValueError, EOFError, RecursionError, SystemExit)

GENERIC = [
    "",
    " ",
    "\n",
    "\n\n",
    "\t",
    "\x00",
    "0",
    "1",
    "-1",
    "999999",
    "a",
    "z",
    "A",
    "!",
    "?",
    "#",
    ",",
    ".",
    ":",
    ";",
    "$",
    "%",
    "&",
    "[",
    "]",
    "()",
    "{}",
    "<>",
    "[]",
    "[[[",
    "]]]",
    "((",
    "))",
    "+-*/",
    "><",
    '"',
    "''",
    '"unterminated',
    "\\",
    "//",
    "**",
    ",,,,",
    "::::",
    "$$$$",
    "a,b,c",
    "1,2,3",
    "x=",
    "=x",
    "..",
    "0..",
    "..0",
    "1..0",
    "f",
    "f()",
    "main{}",
    "print",
    "make",
    "if",
    "loop",
    "for",
    "return",
    "out",
    "in",
    "\u00b2",
    "\u0661",  # digits str.isdigit accepts but int() will not
    "9" * 40,
    "z" * 40,
    "\n".join(["1"] * 8),
]

# Programs are bounded by *steps*, not by a wall clock.  Most malformed
# programs for a grid or beam language loop forever by construction (11 of
# 14 generic fragments do, for Back and Circlefuck), so a wall-clock bound
# spends its whole budget waiting for those: at 300 hanging programs, even
# a 2-second timeout is ten minutes.  A step cap ends them at once, and is
# reproducible -- it does not shift with the speed of the machine running
# it, so it cannot time out a slow-but-valid program and call it a leak.
_STEP_CAP = 20000

# Four inputs, not a dozen: the distinctions that actually change a read
# are no input at all, a blank line, a digit, and a non-digit.  Extra
# spellings of "a digit" multiply the sweep without reaching new code --
# and the sweep runs every program against every one of these.
STDINS = ["", "\n", "0\n1\n", "abc"]


def mutate(text: str, rng: random.Random, n: int = 12) -> list[str]:
    """Return small corruptions of a working program."""
    out: list[str] = []
    if not text:
        return out
    for _ in range(n):
        kind = rng.randrange(4)
        i = rng.randrange(len(text))
        if kind == 0:
            out.append(text[:i])  # truncate
        elif kind == 1:
            out.append(text[:i] + text[i + 1 :])  # drop a char
        elif kind == 2:
            out.append(text[:i] + text[i] * 2 + text[i + 1 :])  # double a char
        else:
            out.append(text[:i] + rng.choice(",.[]{}()$0az") + text[i:])
    return out


# The scoping rule (which files changed, and what forces a full sweep) is
# shared with scripts/verify.py, so both agree on when a narrowed run is safe.
sys.path.insert(0, str(_ROOT / "scripts"))
from _scope import SHARED_INTERPRETER as _SHARED
from _scope import changed_files as _changed_files


def _select(
    langs: list[str], runners: dict[str, tuple[str, bool, dict[str, int]]]
) -> tuple[list[str], str]:
    """Return the languages worth sweeping, and why that set was chosen."""
    changed = _changed_files()
    if not changed:
        return langs, "no diff available, sweeping everything"
    if any(f.endswith(_SHARED) for f in changed):
        return langs, "shared interpreter machinery changed"
    picked = [
        n for n in langs if any(runners[n][0].replace(".", "/") in f for f in changed)
    ]
    if not picked:
        return [], "no interpreter changed"
    return picked, f"{len(picked)} interpreter(s) changed"


def _drive(lang: str, program: str, stdin: str) -> None:
    """Run one program, stepping it rather than running it to completion.

    Every registry language is step-capable (``esolangs.vm._VM_ADAPTERS``
    covers all of them), so the sweep steps the machine and stops at
    ``_STEP_CAP`` instead of waiting out a clock.  A program that is still
    going at the cap is not a finding -- looping forever is legal for most
    of these languages -- so it simply returns.
    """
    vm = make_vm(lang, program, stdin)
    for _ in range(_STEP_CAP):
        if vm.halted:
            return
        vm.step()


def main() -> None:
    """Sweep every registered language and report any that leaks."""
    from esolangs.registry import RUNNERS, canonical_id

    args = [a for a in sys.argv[1:] if a != "--all"]
    langs = sorted(RUNNERS)
    if "--all" in sys.argv[1:]:
        why = "--all"
    else:
        langs, why = _select(langs, RUNNERS)
    print(f"sweeping {len(langs)} language(s): {why}", flush=True)
    if not langs:
        print("nothing to check (pass --all to sweep the whole registry)")
        return

    # RUNNERS is keyed by display name; the example files by canonical id.
    slug_of = {name: canonical_id(name) for name in langs}
    by_slug: dict[str, list[str]] = {}
    for d in ("hello-world", "boolean"):
        for p in (_ROOT / "examples" / d).glob("*.txt"):
            by_slug.setdefault(p.stem, []).append(p.read_text())
    examples = {name: by_slug.get(slug, []) for name, slug in slug_of.items()}
    missing = [n for n, v in examples.items() if not v]
    print(f"languages without example programs: {len(missing)}", flush=True)

    findings: dict[str, list[dict[str, str]]] = {}
    counts: dict[str, int] = {}
    rng = random.Random(1234)

    for lang in langs:
        progs = list(GENERIC)
        for src in examples[lang]:
            progs.append(src)
            progs.extend(mutate(src, rng))
        n = 0
        t0 = time.time()
        for prog in progs:
            for stdin in STDINS:
                n += 1
                try:
                    _drive(lang, prog, stdin)
                except ALLOWED:
                    pass
                except BaseException as e:
                    key = type(e).__name__
                    findings.setdefault(lang, [])
                    if len(findings[lang]) < 6:
                        findings[lang].append(
                            {
                                "exc": key,
                                "msg": str(e)[:120],
                                "program": prog[:120],
                                "stdin": stdin,
                            }
                        )
                    counts[f"{lang}:{key}"] = counts.get(f"{lang}:{key}", 0) + 1
        hits = findings.get(lang)
        status = f"LEAK {len(hits)}" if hits else "ok"
        print(f"{lang:26} {n:6} runs {time.time() - t0:6.1f}s  {status}", flush=True)

    if args:
        with open(args[0], "w") as fh:
            json.dump(
                {"findings": findings, "counts": counts}, fh, indent=1, sort_keys=True
            )
    print(f"\nlanguages with leaks: {len(findings)} / {len(langs)}")
    if findings:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
