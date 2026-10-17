"""Diff an interpreter's step-by-step behaviour against another revision.

The refactor check AGENTS.md asks for: run the old and new ``_Machine`` side
by side and compare, at every step, each public property, the snapshot and
the output, and on an error its type, message, notes and the state left
behind.  The corpus is the suite sample, wiki examples, every table through
n=3 on every input row (and wrapped at width 8 below n=3), and seeded random
programs.  Machines that draw get the same seeded source in both copies.
``--mutant`` is the positive control: a deliberately broken copy
that must differ somewhere, or the corpus never reached the change.
``--speed`` also times both over the longest-running programs: a teaching
rewrite once cost Deadfish a third of its step rate, unmeasured.

Exits 1 on any difference, on a mutant that went unseen, or with ``--speed``
on a new copy more than 10% slower (CONTRIBUTING.md's bar).
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import inspect
import itertools
import math
import random
import re
import subprocess
import sys
import tempfile
import time
import tomllib
from contextlib import suppress
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
# tests/ holds the suite samples; run as a script, only scripts/ is on the path.
sys.path.insert(0, str(ROOT))

import esolangs  # noqa: E402
from esolangs.exceptions import GeneratorCapError  # noqa: E402
from esolangs.registry import INTERPRETERS, LANGUAGES, resolve  # noqa: E402
from esolangs.runtime.io import ScriptedIO  # noqa: E402
from esolangs.runtime.randomness import Seeded  # noqa: E402

# Imported by name so mypy, which checks scripts/ but not tests/, stops here.
SAMPLES = importlib.import_module("tests.support.samples").SAMPLES

#: Steps traced per program; past it a run counts as non-halting.
LIMIT = 400
RANDOM_PROGRAMS = 3000
#: The slowdown a refactor may cost before ``--speed`` fails it.
SLOWDOWN = 0.10
_ADDRESS = re.compile(r"<[\w.]+\.(\w+) object at 0x[0-9a-f]+>| at 0x[0-9a-f]+")

#: ``(source, stdin)``; a generated source may be a raster or compressed.
type Program = tuple[Any, str]
type Event = tuple[object, ...]


def _machine(module: ModuleType, source: object, io: ScriptedIO) -> Any:
    """Build ``module``'s machine; one that draws gets a fresh seeded source.

    Unseeded, a draw comes from ``secrets``: tracing one INTERCAL ``%50``
    program 20 times gave 20 different traces.
    """
    machine = module._Machine  # noqa: SLF001
    if "rng" in inspect.signature(machine).parameters:
        return machine(source, io, rng=Seeded(0))
    return machine(source, io)


def _load(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    # Dataclasses look their module up while it is still executing.
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _source_path(module: str, ref: str) -> tuple[Path, str]:
    """Return the interpreter's file and the name to load other copies under.

    A package's old ``__init__`` is loaded inside the package, so its relative
    imports reach the current submodules: sound only when it alone changed.
    """
    path = Path(importlib.import_module(module).__file__ or "")
    if path.name != "__init__.py":
        return path, "tracediff"
    changed = subprocess.run(
        ["git", "diff", "--name-only", ref, "--", path.parent.relative_to(ROOT)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split()
    others = [name for name in changed if not name.endswith("/__init__.py")]
    if others:
        raise SystemExit(f"{module} changed beyond __init__.py: {others}")
    return path, f"{module}.tracediff"


def _revision(path: Path, ref: str, scratch: Path) -> Path:
    """Write ``path`` as it is at git ``ref`` into ``scratch``."""
    relative = path.relative_to(ROOT).as_posix()
    text = subprocess.run(
        ["git", "show", f"{ref}:{relative}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    copy = scratch / f"old_{path.name}"
    copy.write_text(text, encoding="utf-8")
    return copy


def _error(error: BaseException) -> Event:
    return (type(error).__name__, str(error), tuple(getattr(error, "__notes__", ())))


def _views(machine: object, ignored: frozenset[str]) -> Event:
    names = sorted(
        name
        for name, attribute in vars(type(machine)).items()
        if isinstance(attribute, property)
        and not name.startswith("_")
        and name not in ignored
    )
    seen: list[tuple[str, object]] = []
    for name in names:
        try:
            value = getattr(machine, name)
        except Exception as error:
            seen.append((name, _error(error)))
            continue
        if isinstance(value, list):
            # A grown store makes repr dominate the run; a hash compares in C.
            value = (len(value), hash(tuple(map(_repr, value))))
        seen.append((name, _repr(value)))
    return tuple(seen)


def _repr(value: object) -> str:
    """``repr`` without memory addresses or module paths, which differ by copy."""
    return _ADDRESS.sub(lambda m: f"<{m[1]} object>" if m[1] else "", repr(value))


_SLOTS: dict[type, tuple[str, ...]] = {}


def _slots(cls: type) -> tuple[str, ...]:
    """Every ``__slots__`` name along ``cls``'s MRO."""
    if cls not in _SLOTS:
        _SLOTS[cls] = tuple(
            name for base in cls.__mro__ for name in getattr(base, "__slots__", ())
        )
    return _SLOTS[cls]


def _plain(value: object, memo: dict[int, object]) -> object:
    """``value`` as builtins: an instance becomes its class name and fields.

    A default ``repr`` names the module copy and hides the fields, so two
    copies' equal continuations differed and unequal ones would not.  ``memo``
    maps ``id`` to result: Unlambda's terms and continuations are shared from
    step to step, and without it the walk ran its tracediff 6x slower.
    """
    if value is None or isinstance(value, int | float | str | bytes):
        return value
    key = id(value)
    if key in memo:
        return memo[key]
    result: object
    if isinstance(value, tuple | list):
        result = tuple(_plain(item, memo) for item in value)
    elif isinstance(value, dict):
        result = tuple(sorted((_repr(k), _plain(v, memo)) for k, v in value.items()))
    elif isinstance(value, set | frozenset):
        result = tuple(sorted(map(_repr, value)))
    else:
        fields = {
            name: getattr(value, name)
            for name in _slots(type(value))
            if hasattr(value, name)
        }
        fields.update(getattr(value, "__dict__", {}))
        result = (
            (
                type(value).__name__,
                tuple((k, _plain(v, memo)) for k, v in sorted(fields.items())),
            )
            if fields
            else _repr(value)
        )
    memo[key] = result
    return result


def trace(
    module: ModuleType,
    program: Program,
    ignored: frozenset[str],
    *,
    split: bool = False,
) -> list[Event]:
    """Return one event per step: views, snapshot and output so far.

    ``split`` passes the source as lines, as the registry does for grids:
    a string there built a one-column grid and every program failed alike.
    """
    code, stdin = program
    io = ScriptedIO(stdin)
    try:
        source = code.splitlines() if split and isinstance(code, str) else code
        machine = _machine(module, source, io)
    except Exception as error:
        return [("error", *_error(error))]
    events: list[Event] = []
    try:
        for _ in range(LIMIT):
            events.append((_views(machine, ignored), machine.snapshot(), io.getvalue()))
            if machine.halted:
                if getattr(machine, "dumps_on_the_post_halt_step", False):
                    machine.step()
                    machine.step()  # idempotent by the VM contract
                    events.append(("dumped", io.getvalue()))
                break
            machine.step()
    except Exception as error:
        events.append(("error", *_error(error), machine.snapshot()))
    return events


def _halts(events: list[Event]) -> bool:
    """Whether a trace ended by halting: no error, and inside the step limit."""
    return events[-1][0] != "error" and len(events) < LIMIT


def _cap_digits(code: str, limit: int | None) -> str:
    """Drop every digit past the first ``limit``; ``None`` keeps them all."""
    if limit is None:
        return code
    seen = itertools.accumulate(char.isdigit() for char in code)
    pairs = zip(code, seen, strict=True)
    return "".join(c for c, at in pairs if not (c.isdigit() and at > limit))


def _random_programs(
    corpus: list[Program], count: int, max_digits: int | None = None
) -> list[Program]:
    """Seeded programs over the corpus alphabet, and small integer tokens.

    Integer tokens appear when some corpus program is integers alone; a
    language that also takes assembly gets both kinds, half each.  A
    language's ``fuzz_max_digits`` caps the digits each one holds.
    """
    rng = random.Random(0)
    texts = [code for code, _ in corpus if isinstance(code, str) and code.strip()]
    inputs = sorted({stdin for _, stdin in corpus}) or [""]
    numbers = [
        [int(token) for token in code.split()]
        for code in texts
        if all(token.lstrip("-").isdigit() for token in code.split())
    ]
    mixed = len(numbers) < len(texts)
    alphabet = sorted(set("".join(texts)) | {" "})
    # Negative values the corpus uses are special addresses (AddSubJump's
    # flags sit at -2..-9); without them a flag mutant went unseen.
    low = min([-1, *(value for row in numbers for value in row)])
    programs = []
    for _ in range(count):
        if numbers and not (mixed and rng.random() < 0.5):
            # Random digit strings address millions of cells; small ones
            # reach jumps, I/O and in-range writes instead.
            size = rng.randint(1, 15)
            words = (str(rng.randint(max(low, -16), 40)) for _ in range(size))
            code = " ".join(words)
        else:
            code = "".join(rng.choice(alphabet) for _ in range(rng.randint(1, 14)))
        programs.append((_cap_digits(code, max_digits), rng.choice(inputs)))
    return programs


def _example_text(page: Path, example: dict[str, str], key: str) -> str:
    """Return a wiki example's ``key``, inline or from its ``<key>_file``."""
    if f"{key}_file" in example:
        return (page.parent / example[f"{key}_file"]).read_text(encoding="utf-8")
    return example.get(key, "")


def corpus(name: str, count: int = RANDOM_PROGRAMS, max_n: int = 3) -> list[Program]:
    """Return the sample, wiki examples, generated rows and random programs."""
    language = LANGUAGES[name]
    programs: list[Program] = []
    sample = SAMPLES.get(name)
    if sample is not None and isinstance(sample[0], str):
        programs.append((sample[0], sample[1]))
    tests = ROOT / "src/esolangs/languages" / language.id / "tests"
    path = tests / "cases.toml"
    if path.is_file():
        for example in tomllib.loads(path.read_text()).get("examples", []):
            programs.append(
                (
                    _example_text(path, example, "source"),
                    _example_text(path, example, "input"),
                )
            )
    if language.boolean is not None:
        parameterized = esolangs.describe(name)["parameterized"]
        for n in range(1, max_n + 1):
            for table in map("".join, itertools.product("01", repeat=1 << n)):
                widths = (None, 8) if n < 3 else (None,)
                for width in widths:
                    try:
                        if width is None:
                            program = esolangs.generate(name, table)
                        else:
                            program = esolangs.generate(name, table, width=width)
                    except GeneratorCapError:
                        continue  # Unary's n=3 programs are too long to build
                    for row in range(1 << n):
                        bits = [int(c) for c in f"{row:0{n}b}"]
                        # Kept as generated: a raster or compressed program
                        # stringified is no longer that program.
                        if parameterized:
                            code = esolangs.instantiate(name, program, bits)
                            programs.append((code, ""))
                        else:
                            stdin = esolangs.encode_inputs(
                                name, bits, truth_table=table
                            )
                            programs.append((program, str(stdin)))
    return programs + _random_programs(programs, count, language.fuzz_max_digits)


def differences(
    old: ModuleType,
    new: ModuleType,
    programs: list[Program],
    ignored: frozenset[str] = frozenset(),
    *,
    split: bool = False,
) -> list[tuple[Program, int, Event | None, Event | None]]:
    """Return each differing program with its first differing step."""
    found = []
    for program in programs:
        before = trace(old, program, ignored, split=split)
        after = trace(new, program, ignored, split=split)
        if before == after:
            continue
        # A snapshot holding instances (Unlambda's terms and continuations,
        # FALSE's frames) never equals its twin from the other module copy:
        # __eq__ wants the same class object.  Such traces compare by fields.
        # Event by event, so a real difference stops at its first step.
        memo: dict[int, object] = {}  # both traces stay alive, so ids stay unique
        for step in range(max(len(before), len(after))):
            first = before[step] if step < len(before) else None
            second = after[step] if step < len(after) else None
            if first != second and (
                first is None
                or second is None
                or _plain(first, memo) != _plain(second, memo)
            ):
                found.append((program, step, first, second))
                break
    return found


def _lap(module: ModuleType, work: list[tuple[Program, int]], *, split: bool) -> float:
    """Seconds to build each machine and run it its step count."""
    start = time.perf_counter()
    for (code, stdin), steps in work:
        source = code.splitlines() if split and isinstance(code, str) else code
        with suppress(Exception):  # an error ends the run, as it did when traced
            machine = _machine(module, source, ScriptedIO(stdin))
            for _ in range(steps):
                machine.step()
    return time.perf_counter() - start


def speeds(
    old: ModuleType,
    new: ModuleType,
    programs: list[Program],
    *,
    split: bool = False,
    rounds: int = 5,
) -> tuple[float, float]:
    """Return each copy's steps per second over the longest-running programs.

    Both run the same steps, the trace's length, repeated until a lap takes
    0.2 s; laps alternate and the fastest of ``rounds`` counts.
    """
    lengths = [(len(trace(new, p, frozenset(), split=split)), p) for p in programs]
    lengths.sort(key=lambda pair: pair[0], reverse=True)
    work = [(program, steps) for steps, program in lengths[:40]]
    work *= max(1, math.ceil(0.2 / max(_lap(new, work, split=split), 1e-6)))
    old_best = new_best = math.inf
    for _ in range(rounds):
        old_best = min(old_best, _lap(old, work, split=split))
        new_best = min(new_best, _lap(new, work, split=split))
    steps = sum(count for _, count in work)
    return steps / old_best, steps / new_best


def main(argv: list[str] | None = None) -> int:
    """Print the first differences and the counts; return the exit status."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("language")
    parser.add_argument("--old", default="main", help="git revision (default main)")
    parser.add_argument("--mutant", type=Path, help="broken copy that must differ")
    parser.add_argument(
        "--ignore-views", default="", help="comma-separated renamed views"
    )
    parser.add_argument("--random", type=int, default=RANDOM_PROGRAMS)
    parser.add_argument("--speed", action="store_true", help="also compare steps/s")
    args = parser.parse_args(argv)
    name = resolve(args.language)
    ignored = frozenset(filter(None, args.ignore_views.split(",")))
    split = LANGUAGES[name].split
    new = importlib.import_module(INTERPRETERS[name])
    programs = corpus(name, args.random)
    path, prefix = _source_path(INTERPRETERS[name], args.old)
    with tempfile.TemporaryDirectory() as scratch:
        old = _load(_revision(path, args.old, Path(scratch)), f"{prefix}_old")
    found = differences(old, new, programs, ignored, split=split)
    for (code, stdin), step, before, after in found[:3]:
        print(f"DIFF {code!r:.60} stdin={stdin[:20]!r} at step {step}")
        print(f"  {args.old}: {before!r:.300}")
        print(f"  new: {after!r:.300}")
    # A diff over programs that all fail at once proves nothing: say so.
    halting = sum(_halts(trace(new, p, ignored, split=split)) for p in programs)
    print(
        f"{name}: {len(programs)} programs ({halting} halt cleanly), "
        f"{len(found)} differ from {args.old}"
    )
    failed = bool(found)
    if args.speed:
        was, now = speeds(old, new, programs, split=split)
        change = now / was - 1
        print(f"speed: {was:,.0f} -> {now:,.0f} steps/s ({change:+.0%})")
        failed |= change < -SLOWDOWN
    if args.mutant is not None:
        mutant = _load(args.mutant, f"{prefix}_mutant")
        caught = len(differences(old, mutant, programs, ignored, split=split))
        print(f"control: mutant differs on {caught}")
        failed |= not caught
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
