r"""Assert that no interpreter leaks a raw Python exception to its."""

import concurrent.futures as cf
import json
import os
import pathlib
import random
import subprocess
import sys
import time
import typing

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_HERE = pathlib.Path(__file__).resolve()
sys.path.insert(0, str(_ROOT / "src"))

from esolangs.exceptions import EsolangError
from esolangs.vm import make_vm, run_until_halt

# Exceptions an interpreter is.
# .
# ``RecursionError`` was here.
# ``exceptions.py`` or any doc.
# It let a *host* limit escape.
# that needed it have since.
# stack, and Forbin converts.
ALLOWED = (EsolangError, ValueError, EOFError, SystemExit)

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
    "\u0661",  # digits str.isdigit accepts.
    "9" * 40,
    "z" * 40,
    "\n".join(["1"] * 8),
]

# Programs are bounded by.
# programs for a grid or beam.
# 14 generic fragments do, for.
# spends its whole budget.
# a 2-second timeout is ten.
# reproducible -- it does not.
# it, so it cannot time out a.
_STEP_CAP = int(os.environ.get("LEAKSWEEP_STEP_CAP", 0)) or 20000

# : Caps the sweep walks,.
# :.
# : Halting is monotone in the.
# : finishes at 20000 and never.
# : exact rather than a.
# : expensive languages are.
# : run to the ceiling, and.
# : a sweep's cost.
# : unchanged; only the number.
_CAP_LADDER = (10, 100, 1000, _STEP_CAP)

# The cap is not what makes.
# help: the slow languages cost.
# (COD, Factor, Painfuck,.
# subprocess timeout is what.
# `make_vm` factorizes before a.
# SIGALRM cannot land on.
# few runs pay it.

# Four inputs, not a dozen: the.
# are no input at all, a blank.
# spellings of "a digit".
# and the sweep runs every.
STDINS = ["", "\n", "0\n1\n", "abc"]


def mutate(text: str, rng: random.Random, n: int = 12) -> list[str]:
    r"""Return small corruptions of a working program."""
    out: list[str] = []
    if not text:
        return out
    for _ in range(n):
        kind = rng.randrange(4)
        i = rng.randrange(len(text))
        if kind == 0:
            out.append(text[:i])  # truncate.
        elif kind == 1:
            out.append(text[:i] + text[i + 1 :])  # drop a char.
        elif kind == 2:
            out.append(text[:i] + text[i] * 2 + text[i + 1 :])  # double a char.
        else:
            out.append(text[:i] + rng.choice(",.[]{}()$0az") + text[i:])
    return out


# The scoping rule (which files.
# shared with.
sys.path.insert(0, str(_ROOT / "scripts"))
from _scope import SHARED_INTERPRETER as _SHARED
from _scope import changed_files as _changed_files


def _select(
    langs: list[str], runners: dict[str, tuple[str, bool]]
) -> tuple[list[str], str]:
    r"""Return the languages worth sweeping, and why that set was chosen."""
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


def _drive(lang: str, program: str, stdin: str, cap: int) -> bool:
    r"""Run one program, stepping it rather than running it to completion."""
    return run_until_halt(make_vm(lang, program, stdin), cap)


# : Wall-clock a language's.
# :.
# : Sized from measurement, not.
# : in 102.9s *combined*, and.
# : at 4.7s.
# : machine without letting a.
# : exceed it (COD, Factor,.
# : are unbounded work, and no.
_LANG_TIMEOUT = 30.0

# : How many language workers.
# : count: each worker is a.
# : this to the machine.
# : laptop beside everything.
# : slow language (Factor burns.
# : which is most of the win.
# : on a machine with cores to.
# : which is what to use when.
_JOBS = max(1, int(os.environ.get("LEAKSWEEP_JOBS", 0)) or 2)


def _corpus(lang: str, examples: dict[str, list[str]], rng: random.Random) -> list[str]:
    r"""Return the programs swept for ``lang``, advancing ``rng`` as it."""
    progs = list(GENERIC)
    for src in examples[lang]:
        progs.append(src)
        progs.extend(mutate(src, rng))
    return progs


def _sweep_one(lang: str, progs: list[str]) -> tuple[int, list[dict[str, str]]]:
    r"""Run every (program, stdin) for one language, collecting leaks."""
    found: list[dict[str, str]] = []
    pending = [(prog, stdin) for prog in progs for stdin in STDINS]
    n = len(pending)
    for cap in _CAP_LADDER:
        still: list[tuple[str, str]] = []
        for prog, stdin in pending:
            try:
                if not _drive(lang, prog, stdin, cap):
                    still.append((prog, stdin))
            except ALLOWED:
                pass
            except BaseException as e:
                if len(found) < 6:
                    found.append(
                        {
                            "exc": type(e).__name__,
                            "msg": str(e)[:120],
                            "program": prog[:120],
                            "stdin": stdin,
                        }
                    )
        # Only what is still running.
        # resolved too, and drops out.
        pending = still
        if not pending:
            break
    return n, found


class _Report(typing.NamedTuple):
    r"""What one language's worker reported back."""

    runs: int
    findings: list[dict[str, str]]


def _run_worker(lang: str) -> tuple[float, str, _Report | None]:
    r"""Sweep one language in a child process, killing it if it wedges."""
    t0 = time.time()
    try:
        proc = subprocess.run(
            [sys.executable, str(_HERE), "--worker", lang],
            capture_output=True,
            text=True,
            timeout=None if _LANG_TIMEOUT <= 0 else _LANG_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired:
        # SIGKILL lands without needing.
        # whole reason this runs out of.
        return time.time() - t0, "TIMEOUT", None
    elapsed = time.time() - t0
    if proc.returncode != 0 or not proc.stdout.strip():
        return elapsed, "DIED", None
    got = json.loads(proc.stdout.strip().splitlines()[-1])
    return elapsed, "ok", _Report(got["runs"], got["findings"])


def _worker(target: str) -> None:
    r"""Sweep one language and print its result as JSON on stdout."""
    from esolangs.registry import RUNNERS, canonical_id

    langs = sorted(RUNNERS)
    slug_of = {name: canonical_id(name) for name in langs}
    by_slug: dict[str, list[str]] = {}
    for d in ("boolean",):
        for p in (_ROOT / "examples" / d).glob("*.txt"):
            by_slug.setdefault(p.stem, []).append(p.read_text())
    examples = {name: by_slug.get(slug, []) for name, slug in slug_of.items()}

    rng = random.Random(1234)
    progs: list[str] = []
    for lang in langs:  # replay in order so the corpus.
        got = _corpus(lang, examples, rng)
        if lang == target:
            progs = got
            break

    n, found = _sweep_one(target, progs)
    print(json.dumps({"runs": n, "findings": found}), flush=True)


def main() -> None:
    r"""Sweep every registered language and report any that leaks."""
    from esolangs.registry import RUNNERS, canonical_id

    if "--worker" in sys.argv[1:]:
        _worker(sys.argv[sys.argv.index("--worker") + 1])
        return

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

    # RUNNERS is keyed by display.
    slug_of = {name: canonical_id(name) for name in langs}
    by_slug: dict[str, list[str]] = {}
    for d in ("boolean",):
        for p in (_ROOT / "examples" / d).glob("*.txt"):
            by_slug.setdefault(p.stem, []).append(p.read_text())
    examples = {name: by_slug.get(slug, []) for name, slug in slug_of.items()}
    missing = [n for n, v in examples.items() if not v]
    print(f"languages without example programs: {len(missing)}", flush=True)

    findings: dict[str, list[dict[str, str]]] = {}
    counts: dict[str, int] = {}

    # Drawn here, in order, purely.
    # worker's own replay: one.
    # so the corpus is only.
    # Doing it before the pool.
    # mutable state.
    rng = random.Random(1234)
    for lang in langs:
        _corpus(lang, examples, rng)

    timeouts: list[str] = []
    # Workers are independent.
    # threads only because each.
    # keeps a language that burns.
    with cf.ThreadPoolExecutor(max_workers=_JOBS) as pool:
        futures = {pool.submit(_run_worker, lang): lang for lang in langs}
        done = {}
        for fut in cf.as_completed(futures):
            lang = futures[fut]
            done[lang] = fut.result()
            # Progress as it lands.
            # this is so a long sweep shows.
            # language that is still out.
            done_msg = f"  .. {lang} ({len(done)}/{len(langs)})"
            print(done_msg, file=sys.stderr, flush=True)
    # Reported in registry order.
    # of the sweep produce the same.
    for lang in langs:
        elapsed, status, result = done[lang]
        if result is None:
            timeouts.append(lang)
            print(f"{lang:26} {'':6}      {elapsed:6.1f}s  {status}", flush=True)
            continue
        n = result.runs
        for hit in result.findings:
            findings.setdefault(lang, []).append(hit)
            key = f"{lang}:{hit['exc']}"
            counts[key] = counts.get(key, 0) + 1
        hits = findings.get(lang)
        status = f"LEAK {len(hits)}" if hits else "ok"
        print(f"{lang:26} {n:6} runs {elapsed:6.1f}s  {status}", flush=True)

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
