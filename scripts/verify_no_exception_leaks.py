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
from esolangs.vm import make_vm

# Exceptions an interpreter is allowed to raise at the API boundary.
#
# ``RecursionError`` was here from this script's first commit, undefended by
# ``exceptions.py`` or any doc -- the one entry with no documented backing.
# It let a *host* limit escape as an interpreter's answer.  Both languages
# that needed it have since been fixed: Eval runs nested programs on a frame
# stack, and Forbin converts the one natively-recursive path it has left.
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
_STEP_CAP = int(os.environ.get("LEAKSWEEP_STEP_CAP", 0)) or 20000

#: Caps the sweep walks, cheapest first, retrying only what is still running.
#:
#: Halting is monotone in the cap, so a program that finishes at 10 steps
#: finishes at 20000 and never needs rerunning -- which is what makes this
#: exact rather than a heuristic.  Almost everything halts immediately: the
#: expensive languages are expensive because a handful of *their* mutants
#: run to the ceiling, and paying that ceiling for all 336 runs was most of
#: a sweep's cost.  The last rung is ``_STEP_CAP``, so the depth reached is
#: unchanged; only the number of runs that pay for it is.
_CAP_LADDER = (10, 100, 1000, _STEP_CAP)

# The cap is not what makes `--all` expensive.  **Factor is**, and no value
# of the cap helps: its programs are integers whose *factorization* is the
# program, so `make_vm` calls `sympy.factorint` before a single step runs.
# A mutation that alters a digit can turn a factorable number into a ~120
# digit one that is infeasible, and that work is uninterruptible C -- a
# SIGALRM cannot land on it, since the timer needs a bytecode boundary.
# `Factor prog[69]` (of the seeded corpus) is the specific run; it wedges a
# sweep before COD is ever reached.  Bounding it needs a subprocess with a
# hard kill, or a digit-length guard on Factor's mutants.
#
# What the cap costs, measured on COD, the most expensive language to *run*.
# Five mutants of its example (a dropped or inserted character in the `~`
# border) shift the entrance corridor to the tree, so the cod never reaches
# open water and loops forever -- crossing `+` increments as it goes.  Its
# value therefore grows without bound, no state ever repeats, and the cycle
# detector cannot decide it: this is the unbounded-growth class, and the
# programs are genuinely non-terminating rather than slow.
#
# Those 5 programs x 4 stdins are 20 runs that always reach the cap, and
# the growing integer makes each step dearer than the last.
#
# The cap stays 20000, but the ladder below means few runs pay it.  What is
# *not* true -- measured, after assuming otherwise -- is that a smaller cap
# would fix the slow languages.  Their cost is per-step, not step count:
# 87 of Painfuck's 376 runs survive cap 10, and cost ~7ms a step after it,
# so halving the ceiling only halves the bill.  Four languages (COD, Factor,
# Painfuck, Suptiftam) exceed any cap worth setting, and the subprocess
# timeout is what actually bounds them.

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
    langs: list[str], runners: dict[str, tuple[str, bool]]
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


def _drive(lang: str, program: str, stdin: str, cap: int) -> bool:
    """Run one program, stepping it rather than running it to completion.

    Every registry language is step-capable (``esolangs.vm._VM_ADAPTERS``
    covers all of them), so the sweep steps the machine and stops at ``cap``
    instead of waiting out a clock.  A program still going at the cap is not
    a finding -- looping forever is legal for most of these languages.

    Returns whether it halted, which is what lets :func:`_sweep_one`
    escalate: halting is monotone in the cap, so a program that finishes
    here finishes at every larger one and never needs rerunning.
    """
    vm = make_vm(lang, program, stdin)
    for _ in range(cap):
        if vm.halted:
            return True
        vm.step()
    return False


#: Wall-clock a language's worker gets before the parent kills it.
#:
#: Sized from measurement, not from caution: 60 of the 64 languages finish
#: in 102.9s *combined*, and the slowest that finishes at all is AddSubJump
#: at 4.7s.  30s is therefore ~6x the real maximum -- room for a slower
#: machine without letting a wedged language cost minutes.  The four that
#: exceed it (COD, Factor, Painfuck, Suptiftam) are not slow-but-valid: they
#: are unbounded work, and no larger number collects them.
_LANG_TIMEOUT = 30.0

#: How many language workers run at once.  Deliberately **2**, not the core
#: count: each worker is a separate process doing pure CPU work, so scaling
#: this to the machine saturates it -- and this script runs on a developer's
#: laptop beside everything else they are doing.  Two is enough to stop one
#: slow language (Factor burns its whole timeout) from stalling the queue,
#: which is most of the win.  Raise it deliberately with ``LEAKSWEEP_JOBS``
#: on a machine with cores to spare; ``LEAKSWEEP_JOBS=1`` is sequential,
#: which is what to use when reading a live transcript.
_JOBS = max(1, int(os.environ.get("LEAKSWEEP_JOBS", 0)) or 2)


def _corpus(lang: str, examples: dict[str, list[str]], rng: random.Random) -> list[str]:
    """Return the programs swept for ``lang``, advancing ``rng`` as it goes.

    One generator feeds every language in order, so the parent and a worker
    only agree on a corpus if both consume it in the same sequence -- which
    is why a worker replays the languages before its own rather than seeding
    afresh.
    """
    progs = list(GENERIC)
    for src in examples[lang]:
        progs.append(src)
        progs.extend(mutate(src, rng))
    return progs


def _sweep_one(lang: str, progs: list[str]) -> tuple[int, list[dict[str, str]]]:
    """Run every (program, stdin) for one language, collecting leaks.

    Escalating, because halting is monotone in the cap: run everything at a
    tiny cap first, and only the programs still going are retried at the
    next.  Almost every program halts in a handful of steps, so the full
    ``_STEP_CAP`` is paid by the few that need it rather than by all 336.

    The leaks found are the same either way -- an exception raised at step 7
    is raised at step 7 whatever the cap -- so this is purely a saving.
    """
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
        # Only what is still running escalates; a raised exception is
        # resolved too, and drops out with the ones that halted.
        pending = still
        if not pending:
            break
    return n, found


class _Report(typing.NamedTuple):
    """What one language's worker reported back."""

    runs: int
    findings: list[dict[str, str]]


def _run_worker(lang: str) -> tuple[float, str, _Report | None]:
    """Sweep one language in a child process, killing it if it wedges.

    Returns ``(elapsed, status, result)``; ``result`` is ``None`` when the
    child never reported, which is a failed sweep for that language rather
    than a clean one -- see the callers' ``timeouts`` list.
    """
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
        # SIGKILL lands without needing a bytecode boundary, which is the
        # whole reason this runs out of process.
        return time.time() - t0, "TIMEOUT", None
    elapsed = time.time() - t0
    if proc.returncode != 0 or not proc.stdout.strip():
        return elapsed, "DIED", None
    got = json.loads(proc.stdout.strip().splitlines()[-1])
    return elapsed, "ok", _Report(got["runs"], got["findings"])


def _worker(target: str) -> None:
    """Sweep one language and print its result as JSON on stdout.

    Runs in a child process so the parent can kill it: an interpreter can
    spend unbounded time inside a single uninterruptible C call (Factor
    factors its program with sympy before a step runs), which no step cap
    or in-process alarm can bound.
    """
    from esolangs.registry import RUNNERS, canonical_id

    langs = sorted(RUNNERS)
    slug_of = {name: canonical_id(name) for name in langs}
    by_slug: dict[str, list[str]] = {}
    for d in ("hello-world", "boolean"):
        for p in (_ROOT / "examples" / d).glob("*.txt"):
            by_slug.setdefault(p.stem, []).append(p.read_text())
    examples = {name: by_slug.get(slug, []) for name, slug in slug_of.items()}

    rng = random.Random(1234)
    progs: list[str] = []
    for lang in langs:  # replay in order so the corpus matches the parent's
        got = _corpus(lang, examples, rng)
        if lang == target:
            progs = got
            break

    n, found = _sweep_one(target, progs)
    print(json.dumps({"runs": n, "findings": found}), flush=True)


def main() -> None:
    """Sweep every registered language and report any that leaks."""
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

    # Drawn here, in order, purely to keep this generator in step with each
    # worker's own replay: one generator feeds every language in sequence,
    # so the corpus is only reproducible if the draws happen in that order.
    # Doing it before the pool keeps the parallel section free of shared
    # mutable state.
    rng = random.Random(1234)
    for lang in langs:
        _corpus(lang, examples, rng)

    timeouts: list[str] = []
    # Workers are independent processes, so they overlap freely; the pool is
    # threads only because each task does nothing but wait on one.  This also
    # keeps a language that burns its whole timeout from delaying the rest.
    with cf.ThreadPoolExecutor(max_workers=_JOBS) as pool:
        futures = {pool.submit(_run_worker, lang): lang for lang in langs}
        done = {}
        for fut in cf.as_completed(futures):
            lang = futures[fut]
            done[lang] = fut.result()
            # Progress as it lands.  The ordered report below is the record;
            # this is so a long sweep shows it is alive, and names the
            # language that is still out when it is not.
            done_msg = f"  .. {lang} ({len(done)}/{len(langs)})"
            print(done_msg, file=sys.stderr, flush=True)
    # Reported in registry order rather than completion order, so two runs
    # of the sweep produce the same transcript.
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
