"""Diff an interpreter's step-by-step behaviour against another revision.

The refactor check AGENTS.md asks for: run the old and new ``_Machine`` side
by side and compare, at every step, each public property, the snapshot and
the output, and on an error its type, message, notes and the state left
behind.  The corpus is the suite sample, wiki examples, every table through
n=3 on every input row (and wrapped at width 8 below n=3), and seeded random
programs.  ``--mutant`` is the positive control: a deliberately broken copy
that must differ somewhere, or the corpus never reached the change.

Exits 1 on any difference, or on a mutant that went unseen.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import itertools
import random
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parent.parent
# tests/ holds the suite samples; run as a script, only scripts/ is on the path.
sys.path.insert(0, str(ROOT))

import esolangs  # noqa: E402
from esolangs.registry import INTERPRETERS, LANGUAGES, resolve  # noqa: E402
from esolangs.runtime.io import ScriptedIO  # noqa: E402

# Imported by name so mypy, which checks scripts/ but not tests/, stops here.
SAMPLES = importlib.import_module("tests.support.samples").SAMPLES

#: Steps traced per program; past it a run counts as non-halting.
LIMIT = 400
RANDOM_PROGRAMS = 3000

type Program = tuple[str, str]
type Event = tuple[object, ...]


def _load(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _source_path(module: str) -> Path:
    path = Path(importlib.import_module(module).__file__ or "")
    if path.name == "__init__.py":
        # Relative imports inside the package would resolve to the new copy.
        raise SystemExit(f"{module} is a package; only single-file interpreters")
    return path


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
        except Exception as error:  # noqa: BLE001 - a raising view is behaviour too
            seen.append((name, _error(error)))
            continue
        if isinstance(value, list):
            # A grown store makes repr dominate the run; a hash compares in C.
            value = (len(value), hash(tuple(map(repr, value))))
        seen.append((name, repr(value)))
    return tuple(seen)


def trace(module: ModuleType, program: Program, ignored: frozenset[str]) -> list[Event]:
    """Return one event per step: views, snapshot and output so far."""
    code, stdin = program
    io = ScriptedIO(stdin)
    try:
        machine = module._Machine(code, io)  # noqa: SLF001
    except Exception as error:  # noqa: BLE001
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
    except Exception as error:  # noqa: BLE001
        events.append(("error", *_error(error), machine.snapshot()))
    return events


def _random_programs(corpus: list[Program], count: int) -> list[Program]:
    """Seeded programs over the corpus alphabet, or small integer tokens."""
    rng = random.Random(0)
    texts = [code for code, _ in corpus if code.strip()]
    inputs = sorted({stdin for _, stdin in corpus}) or [""]
    numeric = bool(texts) and all(
        token.lstrip("-").isdigit() for code in texts for token in code.split()
    )
    alphabet = sorted(set("".join(texts)) | {" "})
    programs = []
    for _ in range(count):
        if numeric:
            # Random digit strings address millions of cells; small ones
            # reach jumps, I/O and in-range writes instead.
            words = (str(rng.randint(-1, 40)) for _ in range(rng.randint(1, 15)))
            code = " ".join(words)
        else:
            code = "".join(rng.choice(alphabet) for _ in range(rng.randint(1, 14)))
        programs.append((code, rng.choice(inputs)))
    return programs


def corpus(name: str, count: int = RANDOM_PROGRAMS, max_n: int = 3) -> list[Program]:
    """Return the sample, wiki examples, generated rows and random programs."""
    language = LANGUAGES[name]
    programs: list[Program] = []
    sample = SAMPLES.get(name)
    if sample is not None and isinstance(sample[0], str):
        programs.append((sample[0], sample[1]))
    tests = ROOT / "src/esolangs/languages" / language.id / "tests"
    for path in sorted(tests.glob("*.toml")):
        for example in tomllib.loads(path.read_text()).get("examples", []):
            programs.append((example["source"], example.get("input", "")))
    if language.boolean is not None:
        parameterized = esolangs.describe(name)["parameterized"]
        for n in range(1, max_n + 1):
            for table in map("".join, itertools.product("01", repeat=1 << n)):
                widths = (None, 8) if n < 3 else (None,)
                for width in widths:
                    if width is None:
                        program = esolangs.generate(name, table)
                    else:
                        program = esolangs.generate(name, table, width=width)
                    for row in range(1 << n):
                        bits = [int(c) for c in f"{row:0{n}b}"]
                        if parameterized:
                            code = esolangs.instantiate(name, program, bits)
                            programs.append((str(code), ""))
                        else:
                            stdin = esolangs.encode_inputs(name, bits, truth_table=table)
                            programs.append((str(program), str(stdin)))
    return programs + _random_programs(programs, count)


def differences(
    old: ModuleType,
    new: ModuleType,
    programs: list[Program],
    ignored: frozenset[str] = frozenset(),
) -> list[tuple[Program, int, Event | None, Event | None]]:
    """Return each differing program with its first differing step."""
    found = []
    for program in programs:
        before, after = trace(old, program, ignored), trace(new, program, ignored)
        if before != after:
            padded = zip([*before, None], [*after, None], strict=False)
            step = next(i for i, (a, b) in enumerate(padded) if a != b)
            first = before[step] if step < len(before) else None
            second = after[step] if step < len(after) else None
            found.append((program, step, first, second))
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("language")
    parser.add_argument("--old", default="main", help="git revision (default main)")
    parser.add_argument("--mutant", type=Path, help="broken copy that must differ")
    parser.add_argument(
        "--ignore-views", default="", help="comma-separated renamed views"
    )
    parser.add_argument("--random", type=int, default=RANDOM_PROGRAMS)
    args = parser.parse_args(argv)
    name = resolve(args.language)
    ignored = frozenset(filter(None, args.ignore_views.split(",")))
    new = importlib.import_module(INTERPRETERS[name])
    programs = corpus(name, args.random)
    with tempfile.TemporaryDirectory() as scratch:
        old_path = _revision(_source_path(INTERPRETERS[name]), args.old, Path(scratch))
        old = _load(old_path, "tracediff_old")
    found = differences(old, new, programs, ignored)
    for (code, stdin), step, before, after in found[:3]:
        print(f"DIFF {code[:60]!r} stdin={stdin[:20]!r} at step {step}")
        print(f"  {args.old}: {before!r:.300}")
        print(f"  new: {after!r:.300}")
    print(f"{name}: {len(programs)} programs, {len(found)} differ from {args.old}")
    if args.mutant is None:
        return int(bool(found))
    mutant = _load(args.mutant, "tracediff_mutant")
    caught = len(differences(old, mutant, programs, ignored))
    print(f"control: mutant differs on {caught}")
    return int(bool(found) or not caught)


if __name__ == "__main__":
    raise SystemExit(main())
