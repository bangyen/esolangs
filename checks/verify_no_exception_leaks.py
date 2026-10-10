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
one inserted).  A language's ``fuzz_max_digits`` shortens its numbers before
mutation where operand size changes cost, not interpreter paths.  Truncation finds the
interesting cases -- a half-written program reaches states no hand-written
test thinks to build.

By default only the languages this branch actually touched are swept,
which makes it cheap enough to run habitually: a change to one
interpreter is checked in seconds, and a change to shared machinery
(``io.py``, ``vm.py``, ``exceptions.py``) still sweeps everything, since
that is exactly where a one-line bug reaches every language at once --
as the ``input_char`` bug this script was written to catch did.

Run::

    python scripts/verify_no_exception_leaks.py            # touched languages
    python scripts/verify_no_exception_leaks.py --all      # every language
    python scripts/verify_no_exception_leaks.py --all out.json

A clean sweep is remembered in ``.leaksweep-cache.json`` under a hash of
the interpreter, the shared machinery, the language's examples and this
script, and skipped while that hash stands; a leak is never remembered.
``LEAKSWEEP_CACHE=0`` sweeps regardless.
"""

import ast
import concurrent.futures as cf
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import pathlib
import random
import re
import subprocess
import sys
import time
import typing

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_HERE = pathlib.Path(__file__).resolve()
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT / "scripts"))

from _verify_process import write_text

from esolangs._program import Program
from esolangs.exceptions import EsolangError
from esolangs.raster import Raster
from esolangs.registry import INTERPRETERS, LANGUAGES, example_stems
from esolangs.vm import make_vm, run_until_halt

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

# Lowering the final cap would miss late exceptions.  The optimizations below
# instead bound Factor's pre-step arithmetic and make Befunge's pushes O(1),
# leaving all 20,000 steps intact.  Measurements are in the verification history.

# Four inputs, not a dozen: the distinctions that actually change a read
# are no input at all, a blank line, a digit, and a non-digit.  Extra
# spellings of "a digit" multiply the sweep without reaching new code --
# and the sweep runs every program against every one of these.
STDINS = ["", "\n", "0\n1\n", "abc"]


def _cap_numeric_runs(program: str, digits: int) -> str:
    """Keep only the first ``digits`` digits of a program's numbers."""
    left = digits

    def shorten(match: re.Match[str]) -> str:
        nonlocal left
        kept = match.group()[:left]
        left -= len(kept)
        return kept

    return re.sub(r"\d+", shorten, program)


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
    langs: list[str],
    runners: dict[str, tuple[str, bool]],
    imports: dict[pathlib.Path, set[str]] | None = None,
) -> tuple[list[str], str]:
    """Return the languages worth sweeping, and why that set was chosen."""
    changed = _changed_files()
    if not changed:
        return langs, "no diff available, sweeping everything"
    if any(f.endswith(_SHARED) for f in changed):
        return langs, "shared interpreter machinery changed"
    if any(
        name.startswith("src/esolangs/")
        and not name.startswith("src/esolangs/examples/")
        and not (_ROOT / name).is_file()
        for name in changed
    ):
        return langs, "source removed; dependency resolution is incomplete"
    changed_examples = {
        pathlib.Path(name).stem
        for name in changed
        if pathlib.Path(name).parent == pathlib.Path("src/esolangs/examples")
        and pathlib.Path(name).suffix in {".txt", ".png"}
    }
    stems = example_stems()
    changed_paths = {(_ROOT / name).resolve() for name in changed}
    picked = [
        name
        for name in langs
        if (changed_examples and stems.get(LANGUAGES[name].id) in changed_examples)
        or changed_paths.intersection(_sources(runners[name][0], imports))
    ]
    if not picked:
        return [], "no interpreter changed"
    return picked, f"{len(picked)} interpreter(s) changed"


def _drive(lang: str, program: Program, stdin: str, cap: int) -> bool:
    """Run one program, stepping it rather than running it to completion.

    Every registry language is step-capable (``esolangs.vm._VM_ADAPTERS``
    covers all of them), so the sweep steps the machine and stops at ``cap``
    instead of waiting out a clock.  A program still going at the cap is not
    a finding -- looping forever is legal for most of these languages.

    Returns whether it halted, which is what lets :func:`_sweep_one`
    escalate: halting is monotone in the cap, so a program that finishes
    here finishes at every larger one and never needs rerunning.  That is
    :func:`~esolangs.vm.run_until_halt`'s verdict exactly, so the drive is
    its call and the overrun policy -- a cap is not a finding -- is the
    ``False`` this hands straight back.
    """
    return run_until_halt(make_vm(lang, program, stdin=stdin), cap)


#: Wall-clock a language's worker gets before the parent kills it.
#:
#: The slowest workers (123, Befunge, Circlefuck) take 8-10s locally and
#: passed 30s on one release runner but not the next.  Ninety seconds leaves
#: room for a slower machine while bounding a regression in VM construction,
#: where the step cap cannot act.
_LANG_TIMEOUT = 90.0

#: How many language workers run at once.  Deliberately **2**, not the core
#: count: each worker is a separate process doing pure CPU work, so scaling
#: this to the machine saturates it -- and this script runs on a developer's
#: laptop beside everything else they are doing.  Two keeps a slow language
#: from stalling the queue without occupying the whole machine.  Raise it
#: deliberately with ``LEAKSWEEP_JOBS``
#: on a machine with cores to spare; ``LEAKSWEEP_JOBS=1`` is sequential,
#: which is what to use when reading a live transcript.
_JOBS = max(1, int(os.environ.get("LEAKSWEEP_JOBS", 0)) or 2)


def _corpus(lang: str, examples: dict[str, list[Program]]) -> list[Program]:
    """Return a reproducible corpus independent of other languages' examples."""
    rng = random.Random(f"1234:{lang}")
    seed = examples[lang][0] if examples[lang] else None
    progs: list[Program]
    if isinstance(seed, Raster):
        progs = [seed]
        for _ in range(4):
            rows = [list(row) for row in seed.rows]
            y, x = rng.randrange(len(rows)), rng.randrange(len(rows[0]))
            rows[y][x] = (0, 0, 0) if rows[y][x] != (0, 0, 0) else (255, 255, 255)
            progs.append(Raster(tuple(tuple(row) for row in rows)))
        progs.extend(
            Raster(((pixel,),)) for pixel in ((0, 0, 0), (255, 255, 255), (17, 83, 149))
        )
        return progs
    progs = list(GENERIC)
    for src in examples[lang]:
        assert isinstance(src, str)
        if digits := LANGUAGES[lang].fuzz_max_digits:
            src = _cap_numeric_runs(src, digits)
        progs.append(src)
        progs.extend(mutate(src, rng))
    return progs


def _sweep_one(lang: str, progs: list[Program]) -> tuple[int, list[dict[str, str]]]:
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
        still: list[tuple[Program, str]] = []
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
                            "program": str(prog)[:120],
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


#: Where clean results live.  Gitignored; CI restores it across runs so
#: ``--all`` pays only for what changed since the last green sweep.
_CACHE = _ROOT / ".leaksweep-cache.json"
_USE_CACHE = os.environ.get("LEAKSWEEP_CACHE", "1") != "0"


def _examples_by_slug() -> dict[str, list[Program]]:
    """Return the shipped example programs keyed by canonical language ID.

    The filenames are dash-separated display names (``a-painter-ant``) and
    every lookup here is the underscored slug (``a_painter_ant``), so the
    two are bridged by ``example_stems()`` rather than by the stem alone.
    Keying on the stem silently gave sixteen of the sixty-two languages no
    example to sweep -- the exact failure that helper's docstring warns
    about -- and a language with no example is swept on generic fragments
    alone, without the mutations of a real program that find the
    interesting cases.
    """
    by_slug: dict[str, list[Program]] = {}
    directory = _ROOT / "src" / "esolangs" / "examples"
    for slug, stem in example_stems().items():
        path = directory / f"{stem}.txt"
        if path.exists():
            by_slug.setdefault(slug, []).append(path.read_text())
        image = directory / f"{stem}.png"
        if image.exists():
            from esolangs.raster.scale import normalize

            decoded = Raster.from_png(image.read_bytes())
            by_slug.setdefault(slug, []).append(Raster(normalize(decoded.rows)))
    return by_slug


def _module_path(module: str) -> pathlib.Path | None:
    """Resolve a local import without importing its code."""
    if not module.startswith("esolangs."):
        return None
    path = _ROOT / "src" / module.replace(".", "/")
    if path.with_suffix(".py").is_file():
        return path.with_suffix(".py")
    init = path / "__init__.py"
    return init if init.is_file() else None


def _imports(path: pathlib.Path) -> set[str]:
    """Return absolute local import names, including package submodules."""
    parts = path.relative_to(_ROOT / "src").with_suffix("").parts
    package = ".".join(parts[:-1])
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level:
                module = importlib.util.resolve_name("." * node.level + module, package)
            found.add(module)
            found.update(
                name
                for alias in node.names
                if _module_path(name := f"{module}.{alias.name}") is not None
            )
    return found


def _sources(
    module: str, imports: dict[pathlib.Path, set[str]] | None = None
) -> list[pathlib.Path]:
    """Return interpreter sources, imported helpers and shared cache inputs."""
    pkg = _ROOT / "src" / "esolangs"
    if imports is None:
        imports = {}
    if not module.startswith("esolangs."):
        module = "esolangs." + (
            module if module.startswith("interpreters.") else "interpreters." + module
        )
    entry = _module_path(module)
    if entry is None:
        raise FileNotFoundError(f"interpreter source not found: {module}")
    shared = {pkg / name for name in _SHARED}
    pending = (
        list(entry.parent.rglob("*.py")) if entry.name == "__init__.py" else [entry]
    )
    pending.extend(shared)
    sources: set[pathlib.Path] = set()
    while pending:
        path = pending.pop()
        if path in sources:
            continue
        sources.add(path)
        for parent in path.parents:
            init = parent / "__init__.py"
            if parent == pkg:
                if init.is_file():
                    sources.add(init)
                break
            if init.is_file() and init not in sources:
                pending.append(init)
        # Shared inputs already invalidate every language; expanding registry
        # imports here would also pull in every unrelated generator.
        if (path in shared and path.is_relative_to(pkg / "registry")) or path == (
            pkg / "tools" / "__init__.py"
        ):
            continue
        if path not in imports:
            imports[path] = _imports(path)
        for name in imports[path]:
            dependency = _module_path(name)
            if dependency is None:
                if name.startswith("esolangs."):
                    raise FileNotFoundError(f"imported source not found: {name}")
            elif dependency not in sources:
                pending.append(dependency)
    return sorted({_HERE, _ROOT / "scripts" / "_scope.py", *sources, *shared})


def _runtime_identity() -> bytes:
    """Identify Python and the installed dependency versions used by workers."""
    inventory = sorted(
        (distribution.metadata["Name"], distribution.version)
        for distribution in importlib.metadata.distributions()
    )
    return json.dumps([sys.version, sys.implementation.cache_tag, inventory]).encode()


def _fingerprint(
    module: str,
    examples: list[Program],
    imports: dict[pathlib.Path, set[str]] | None = None,
    runtime: bytes | None = None,
) -> str:
    """Hash everything a sweep of ``module`` reads; a change to any part re-sweeps."""
    h = hashlib.sha256(_runtime_identity() if runtime is None else runtime)
    for path in _sources(module, imports):
        h.update(path.read_bytes())
        h.update(b"\0")
    for text in examples:
        h.update(text.to_png() if isinstance(text, Raster) else text.encode())
        h.update(b"\0")
    h.update(f"{_STEP_CAP}:{_LANG_TIMEOUT}".encode())
    return h.hexdigest()


def _load_cache() -> dict[str, str]:
    """Return the remembered clean fingerprints, empty if absent or unreadable."""
    if not _USE_CACHE or not _CACHE.exists():
        return {}
    try:
        got = json.loads(_CACHE.read_text())
    except (OSError, ValueError):
        return {}
    return got if isinstance(got, dict) else {}


def _save_cache(cache: dict[str, str]) -> None:
    """Write the clean fingerprints back, atomically."""
    if not _USE_CACHE:
        return
    write_text(_CACHE, json.dumps(cache, indent=1, sort_keys=True) + "\n")


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
    langs = sorted(INTERPRETERS)
    slug_of = {name: LANGUAGES[name].id for name in langs}
    by_slug = _examples_by_slug()
    examples = {name: by_slug.get(slug, []) for name, slug in slug_of.items()}

    progs = _corpus(target, examples)

    n, found = _sweep_one(target, progs)
    print(json.dumps({"runs": n, "findings": found}), flush=True)


def main() -> None:
    """Sweep every registered language and report any that leaks."""
    if "--worker" in sys.argv[1:]:
        _worker(sys.argv[sys.argv.index("--worker") + 1])
        return

    args = [a for a in sys.argv[1:] if a != "--all"]
    langs = sorted(INTERPRETERS)
    imports: dict[pathlib.Path, set[str]] = {}
    if "--all" in sys.argv[1:]:
        why = "--all"
    else:
        langs, why = _select(
            langs,
            {
                name: (module.removeprefix("esolangs."), False)
                for name, module in INTERPRETERS.items()
            },
            imports,
        )
    print(f"sweeping {len(langs)} language(s): {why}", flush=True)
    if not langs:
        print("nothing to check (pass --all to sweep the whole registry)")
        return

    # RUNNERS is keyed by display name; the example files by canonical id.
    slug_of = {name: LANGUAGES[name].id for name in langs}
    by_slug = _examples_by_slug()
    examples = {name: by_slug.get(slug, []) for name, slug in slug_of.items()}
    missing = [n for n, v in examples.items() if not v]
    print(f"languages without example programs: {len(missing)}", flush=True)

    cache = _load_cache()
    runtime = _runtime_identity()
    keys = {
        n: _fingerprint(INTERPRETERS[n], examples[n], imports, runtime) for n in langs
    }
    cached = [n for n in langs if cache.get(n) == keys[n]]
    if cached:
        print(f"unchanged since last clean sweep: {len(cached)}", flush=True)
    langs = [n for n in langs if n not in cached]

    findings: dict[str, list[dict[str, str]]] = {}
    counts: dict[str, int] = {}

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
        if not hits:
            cache[lang] = keys[lang]
    _save_cache(cache)

    if args:
        with open(args[0], "w") as fh:
            json.dump(
                {"findings": findings, "counts": counts}, fh, indent=1, sort_keys=True
            )
    print(f"\nlanguages with leaks: {len(findings)} / {len(langs) + len(cached)}")
    if timeouts:
        print(f"languages that timed out: {', '.join(timeouts)}")
    if findings or timeouts:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
