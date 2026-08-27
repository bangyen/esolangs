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

Run: ``python scripts/verify_no_exception_leaks.py [out.json]``
"""


import itertools
import json
import time
import os
import pathlib
import random
import sys

_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

import esolangs
from esolangs.exceptions import EsolangError

# Exceptions an interpreter is allowed to raise at the API boundary.
ALLOWED = (EsolangError, ValueError, EOFError, RecursionError, SystemExit)

GENERIC = [
    "", " ", "\n", "\n\n", "\t", "\x00", "0", "1", "-1", "999999",
    "a", "z", "A", "!", "?", "#", ",", ".", ":", ";", "$", "%", "&",
    "[", "]", "()", "{}", "<>", "[]", "[[[", "]]]", "((", "))",
    "+-*/", "><", '"', "''", '"unterminated', "\\", "//", "**",
    ",,,,", "::::", "$$$$", "a,b,c", "1,2,3", "x=", "=x", "..",
    "0..", "..0", "1..0", "f", "f()", "main{}", "print", "make",
    "if", "loop", "for", "return", "out", "in", "²", "١",
    "9" * 40, "z" * 40, "\n".join(["1"] * 8),
]

STDINS = ["", "0", "1", "01", "abc", "0\n1\n", "\n", "5", "255", "1\n" * 8]


def mutate(text: str, rng: random.Random, n: int = 24) -> list[str]:
    """Return small corruptions of a working program."""
    out = []
    if not text:
        return out
    for _ in range(n):
        kind = rng.randrange(4)
        i = rng.randrange(len(text))
        if kind == 0:
            out.append(text[:i])                      # truncate
        elif kind == 1:
            out.append(text[:i] + text[i + 1:])       # drop a char
        elif kind == 2:
            out.append(text[:i] + text[i] * 2 + text[i + 1:])  # double a char
        else:
            out.append(text[:i] + rng.choice(",.[]{}()$0az") + text[i:])
    return out


def main() -> None:
    from esolangs.registry import canonical_id

    langs = sorted(esolangs.RUNNERS)
    # RUNNERS is keyed by display name; the example files by canonical id.
    slug_of = {name: canonical_id(name) for name in langs}
    by_slug: dict[str, list[str]] = {}
    for d in ("hello-world", "boolean"):
        for p in (_ROOT / "examples" / d).glob("*.txt"):
            by_slug.setdefault(p.stem, []).append(p.read_text())
    examples = {name: by_slug.get(slug, []) for name, slug in slug_of.items()}
    missing = [n for n, v in examples.items() if not v]
    print(f"languages without example programs: {len(missing)}", flush=True)

    findings: dict[str, list] = {}
    counts: dict[str, int] = {}
    rng = random.Random(1234)

    for lang in langs:
        progs = list(GENERIC)
        for src in examples[lang]:
            progs.append(src)
            progs.extend(mutate(src, rng))
        n = 0
        t0 = time.time()
        for prog, stdin in itertools.product(progs, STDINS):
            n += 1
            try:
                esolangs.run(lang, prog, stdin, timeout=0.25)
            except ALLOWED:
                pass
            except BaseException as e:  # noqa: BLE001
                key = type(e).__name__
                findings.setdefault(lang, [])
                if len(findings[lang]) < 6:
                    findings[lang].append(
                        {"exc": key, "msg": str(e)[:120],
                         "program": prog[:120], "stdin": stdin}
                    )
                counts[f"{lang}:{key}"] = counts.get(f"{lang}:{key}", 0) + 1
        print(f"{lang:26} {n:6} runs {time.time() - t0:6.1f}s  "
              f"{'LEAK ' + str(len(findings.get(lang, []))) if lang in findings else 'ok'}",
              flush=True)

    if len(sys.argv) > 1:
        json.dump({"findings": findings, "counts": counts},
                  open(sys.argv[1], "w"), indent=1, sort_keys=True)
    print(f"\nlanguages with leaks: {len(findings)} / {len(langs)}")
    if findings:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
