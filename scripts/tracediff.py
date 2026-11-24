"""Diff an interpreter's step-by-step behaviour against another revision.

The refactor check AGENTS.md asks for: run the old and new declared factories side
by side and compare, at every step, each public property, the snapshot and
the output, and on an error its type, message, notes and the state left
behind.  The corpus is the suite sample, wiki examples, every table through
n=3 on every input row (and wrapped at width 8 below n=3), and seeded random
programs.  Machines that draw get the same seeded source in both copies.
``--mutant`` is the positive control: a deliberately broken copy
that must differ somewhere, or the corpus never reached the change.
Baselines and mutants must expose the declared preparation hook.
``--speed`` also times both over the longest-running programs: a teaching
rewrite once cost Deadfish a third of its step rate, unmeasured.

Exits 1 on a difference, when no matching run halts cleanly or witnesses a
declared nonterminating contract, on a mutant that went unseen, or with
``--speed`` on a new copy more than 10% slower (CONTRIBUTING.md's bar).
"""

from __future__ import annotations

import argparse
import gzip
import importlib
import importlib.util
import itertools
import marshal
import math
import os
import random
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import tomllib
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import asdict
from pathlib import Path
from types import ModuleType
from typing import Any, NamedTuple, cast

ROOT = Path(__file__).resolve().parent.parent
# tests/ holds the suite samples; run as a script, only scripts/ is on the path.
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from gendiff import _checkout  # noqa: E402

import esolangs  # noqa: E402
from esolangs.exceptions import GeneratorCapError  # noqa: E402
from esolangs.registry import INTERPRETERS, LANGUAGES, resolve  # noqa: E402
from esolangs.registry._certification import load as load_certification  # noqa: E402
from esolangs.runtime._definition import RuntimeSpec  # noqa: E402
from esolangs.runtime._lifecycle import Completion  # noqa: E402
from esolangs.runtime._machine import MachinePreparation  # noqa: E402
from esolangs.runtime._program import RunnerProgram  # noqa: E402
from esolangs.runtime.io import ScriptedIO  # noqa: E402
from esolangs.runtime.randomness import Seeded  # noqa: E402

#: Steps traced per program; past it a run counts as non-halting.
LIMIT = 400
_WORKER_TIMEOUT = 120
_RECORD_SIZE = struct.Struct(">Q")
RANDOM_PROGRAMS = 3000
#: The slowdown a refactor may cost before ``--speed`` fails it.
SLOWDOWN = 0.10
_ADDRESS = re.compile(r"<[\w.]+\.(\w+) object at 0x[0-9a-f]+>| at 0x[0-9a-f]+")

#: ``(source or runnable artifact, stdin)``; native fixtures stay raw.
type Program = tuple[Any, str]
type Event = tuple[object, ...]


def _preparation(module: ModuleType, runtime: RuntimeSpec) -> MachinePreparation:
    """Require the declared hook, including in old revisions and mutants."""
    prepare = getattr(module, runtime.machine_preparation, None)
    if not callable(prepare):
        raise TypeError(
            f"{getattr(module, '__name__', 'module')} needs declared preparation "
            f"{runtime.machine_preparation}; "
            "choose a revision or mutant with the declared factory"
        )
    return cast(MachinePreparation, prepare)


def _machine(
    module: ModuleType, source: object, io: ScriptedIO, *, runtime: RuntimeSpec
) -> Any:
    """Bind declared source/options and construct with a fresh seeded random source."""
    prepare = _preparation(module, runtime)
    options: dict[str, object] = {}
    if isinstance(source, esolangs.ProgramArtifact):
        if source.settings is not None:
            options.update(source.settings.options())
        if source.scale is not None:
            options["scale"] = source.scale
        source = source.source
    if runtime.split and isinstance(source, str):
        source = source.splitlines()
    if runtime.random:
        options["rng"] = Seeded(0)
    return prepare(cast(RunnerProgram, source), options)(io)


def _load(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    # Dataclasses look their module up while it is still executing.
    sys.modules[name] = module
    # Same-size edits within one timestamp tick can reuse stale .pyc mutations.
    exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
    return module


def _error(error: BaseException) -> Event:
    return (type(error).__name__, str(error), tuple(getattr(error, "__notes__", ())))


def _views(machine: object, ignored: frozenset[str]) -> Event:
    names = sorted(
        name
        for name in dir(type(machine))
        if isinstance(getattr(type(machine), name), property)
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
# _plain converts every ordinary set to a tuple.
_NAN_TAG: frozenset[object] = frozenset()


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
    if isinstance(value, float) and math.isnan(value):
        return (_NAN_TAG, struct.pack("!d", value))
    if value is None or type(value) in (bool, int, float, str, bytes):
        return value
    if isinstance(value, int):
        return int.__int__(value)
    if isinstance(value, float):
        return float.__float__(value)
    if isinstance(value, str):
        return str.__str__(value)
    if isinstance(value, bytes):
        return bytes.__bytes__(value)
    key = id(value)
    if key in memo:
        return memo[key]
    result: object
    if isinstance(value, tuple | list):
        result = tuple(_plain(item, memo) for item in value)
    elif isinstance(value, Mapping):
        # Forþ's persistent scope table is a Mapping whose undo links depend
        # on read order; compare it by content.
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


def _capture_trace(
    module: ModuleType,
    program: Program,
    ignored: frozenset[str],
    *,
    runtime: RuntimeSpec,
) -> tuple[list[Event], int]:
    """Record views, snapshot and output at entry and after each command.

    Completion comes from the runtime declaration, never a machine-class flag.
    The runtime declares source splitting, random draws and the preparation hook:
    a string passed to a split grid built one column and every program failed alike.
    """
    policy = runtime.capabilities.completion
    if not isinstance(policy, Completion):
        raise TypeError("policy must be a Completion policy")
    _preparation(module, runtime)
    code, stdin = program
    io = ScriptedIO(stdin)
    try:
        machine = _machine(module, code, io, runtime=runtime)
    except Exception as error:
        return [("error", *_error(error))], 0
    events: list[Event] = []
    commands = 0
    try:
        for step in range(LIMIT + 1):
            events.append((_views(machine, ignored), machine.snapshot(), io.getvalue()))
            if machine.halted:
                if policy is Completion.POST_HALT:
                    machine.step()
                    machine.step()  # idempotent by the VM contract
                    events.append(
                        (
                            "dumped",
                            _views(machine, ignored),
                            machine.snapshot(),
                            io.getvalue(),
                        )
                    )
                elif step == LIMIT:
                    # The full-length trace can end with or without a halt.
                    events[-1] = ("halted", *events[-1])
                break
            if step == LIMIT:
                break
            machine.step()
            commands += 1
    except Exception as error:
        events.append(("error", *_error(error), machine.snapshot()))
    return events, commands


def trace(
    module: ModuleType,
    program: Program,
    ignored: frozenset[str],
    *,
    runtime: RuntimeSpec,
) -> list[Event]:
    """Return the trace events without timing metadata."""
    return _capture_trace(module, program, ignored, runtime=runtime)[0]


def _halts(events: list[Event]) -> bool:
    """Whether a trace ended by halting: no error, and inside the step limit."""
    outcome = events[-1][0]
    return outcome in ("dumped", "halted") or (
        outcome != "error" and len(events) <= LIMIT
    )


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
    sources = (
        code.source if isinstance(code, esolangs.ProgramArtifact) else code
        for code, _ in corpus
    )
    texts = [code for code in sources if isinstance(code, str) and code.strip()]
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
    sample = importlib.import_module("tests.support.samples").SAMPLES.get(name)
    if sample is not None and isinstance(sample[0], str):
        programs.append((sample[0], sample[1]))
    tests = ROOT / "src/esolangs/languages" / language.id / "tests"
    path = tests / "cases.toml"
    if path.is_file():
        programs.extend(
            (
                _example_text(path, example, "source"),
                _example_text(path, example, "stdin"),
            )
            for example in tomllib.loads(path.read_text()).get("examples", [])
        )
    if language.backend is not None:
        parameterized = esolangs.describe(name).parameterized
        for n in range(1, max_n + 1):
            for table in map("".join, itertools.product("01", repeat=1 << n)):
                for width in (None, 8) if n < 3 else (None,):
                    try:
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
    return programs + _random_programs(
        programs, count, load_certification(language).fuzz_max_digits
    )


type Difference = tuple[Program, int, Event | None, Event | None]


class _Comparison(NamedTuple):
    differences: list[Difference]
    halting: int
    witnessed: bool


def _first_difference(
    before: list[Event], after: list[Event], *, projected: bool = False
) -> tuple[int, Event | None, Event | None] | None:
    if before == after:
        return None
    # Snapshots can contain instances of different copies of the same class.
    # Compare by fields, keeping both traces alive so the memo's ids stay unique.
    memo: dict[int, object] = {}
    for step, (first, second) in enumerate(itertools.zip_longest(before, after)):
        if first != second and (
            projected
            or first is None
            or second is None
            or _plain(first, memo) != _plain(second, memo)
        ):
            return step, first, second
    return None


def _repeated_snapshot(events: list[Event]) -> bool:
    """Find an exact-state repeat on a fault-free bounded trace."""
    if events[-1][0] == "error":
        return False
    seen: set[object] = set()
    try:
        for _, state, _ in events:
            if state in seen:
                return True
            seen.add(state)
    except TypeError:
        return False  # An unhashable snapshot cannot supply a cycle witness.
    return False


type Observation = tuple[list[Event], bool, int]


def _observe(
    module: ModuleType,
    program: Program,
    ignored: frozenset[str],
    *,
    runtime: RuntimeSpec,
    allow_cycles: bool,
) -> Observation:
    events, commands = _capture_trace(module, program, ignored, runtime=runtime)
    cycle = allow_cycles and not _halts(events) and _repeated_snapshot(events)
    return events, cycle, commands


def _summarize(
    programs: Iterable[Program],
    pairs: Iterable[tuple[Observation, Observation]],
    *,
    projected: bool = False,
) -> _Comparison:
    found = []
    halting = 0
    witnessed = False
    for program, ((before, old_cycle, _), (after, new_cycle, _)) in zip(
        programs, pairs, strict=True
    ):
        halted = _halts(after)
        halting += halted
        difference = _first_difference(before, after, projected=projected)
        if difference is not None:
            found.append((program, *difference))
        elif not witnessed:
            witnessed = halted or (old_cycle and new_cycle)
    return _Comparison(found, halting, witnessed)


def _compare(
    old: ModuleType,
    new: ModuleType,
    programs: list[Program],
    ignored: frozenset[str],
    *,
    runtime: RuntimeSpec,
    allow_cycles: bool = False,
) -> _Comparison:
    """Collect differences and successful witnesses from the same traces."""
    pairs = (
        (
            _observe(old, program, ignored, runtime=runtime, allow_cycles=allow_cycles),
            _observe(new, program, ignored, runtime=runtime, allow_cycles=allow_cycles),
        )
        for program in programs
    )
    return _summarize(programs, pairs)


def differences(
    old: ModuleType,
    new: ModuleType,
    programs: list[Program],
    ignored: frozenset[str] = frozenset(),
    *,
    runtime: RuntimeSpec,
) -> list[Difference]:
    """Return each differing program with its first differing step."""
    return _compare(old, new, programs, ignored, runtime=runtime).differences


def _lap(
    module: ModuleType, work: list[tuple[Program, int]], *, runtime: RuntimeSpec
) -> float:
    """Seconds to build each machine and run it its step count."""
    _preparation(module, runtime)
    start = time.perf_counter()
    for (code, stdin), steps in work:
        machine = _machine(module, code, ScriptedIO(stdin), runtime=runtime)
        for _ in range(steps):
            if machine.halted:
                raise ValueError("timing workload halted before its traced commands")
            machine.step()
    return time.perf_counter() - start


def _timing_work[T](work: Iterable[tuple[T, int]]) -> list[tuple[T, int]]:
    """Select the longest successful command prefixes."""
    selected = sorted(
        (case for case in work if case[1]), key=lambda case: case[1], reverse=True
    )[:40]
    if not selected:
        raise ValueError("no completed commands to time")
    return selected


def speeds(
    old: ModuleType,
    new: ModuleType,
    programs: list[Program],
    *,
    runtime: RuntimeSpec,
    rounds: int = 5,
) -> tuple[float, float]:
    """Return each copy's steps per second over the longest-running programs.

    Both run the same completed commands, repeated until a lap takes
    0.2 s. Both copies warm the sized workload before timed laps; laps
    alternate and the fastest of ``rounds`` counts.
    """
    _preparation(old, runtime)
    _preparation(new, runtime)
    work = _timing_work(
        (program, _capture_trace(new, program, frozenset(), runtime=runtime)[1])
        for program in programs
    )
    work *= max(1, math.ceil(0.2 / max(_lap(new, work, runtime=runtime), 1e-6)))
    # Line's inherited warm prefix gave the baseline 15 misses versus 20.
    _lap(old, work, runtime=runtime)
    _lap(new, work, runtime=runtime)
    old_best = new_best = math.inf
    for _ in range(rounds):
        old_best = min(old_best, _lap(old, work, runtime=runtime))
        new_best = min(new_best, _lap(new, work, runtime=runtime))
    steps = sum(count for _, count in work)
    return steps / old_best, steps / new_best


def _pack_program(program: Program, artifacts: dict[int, object]) -> tuple[object, str]:
    """Keep exact source and explicit runtime options across the worker boundary."""
    code, stdin = program
    if not isinstance(code, esolangs.ProgramArtifact):
        return code, stdin
    key = id(code)
    if key in artifacts:
        return artifacts[key], stdin
    source = code.source
    payload: object
    if isinstance(source, esolangs.Raster):
        kind, payload = "raster", source.rows
    elif isinstance(source, esolangs.CompressedText):
        kind = "gzip"
        payload = (
            source.data,
            None if source.limits is None else asdict(source.limits),
        )
    else:
        kind, payload = "text", source
    settings = None if code.settings is None else code.settings.options()
    artifacts[key] = (kind, payload, settings, code.scale)
    return artifacts[key], stdin


def _unpack_program(
    api: esolangs.Language, record: tuple[Any, str], artifacts: dict[int, Any]
) -> Program:
    code, stdin = record
    if isinstance(code, str):
        return code, stdin
    key = id(code)
    if key in artifacts:
        return artifacts[key], stdin
    kind, source, choices, scale = code
    if kind == "raster":
        source = esolangs.Raster(source)
    if kind == "gzip":
        data, limits = source
        source = esolangs.CompressedText(
            data, limits=None if limits is None else esolangs.TextLimits(**limits)
        )
    settings = None if choices is None else api.settings(**choices)
    return esolangs.ProgramArtifact(
        source, api.name, settings=settings, scale=scale
    ), stdin


def _worker(
    language: str, source: Path, request: Path, output: Path, *, timing: bool
) -> None:
    """Trace one revision using its own interpreter and dependencies."""
    assert esolangs.__file__ is not None
    if not Path(esolangs.__file__).resolve().is_relative_to(source.resolve()):
        raise SystemExit("trace worker imported esolangs from the wrong source tree")
    with request.open("rb") as stream:
        packed, extra = marshal.load(stream)
    api = esolangs.Language(language)
    name = api.name
    module = importlib.import_module(INTERPRETERS[name])
    runtime = LANGUAGES[name].runtime
    _preparation(module, runtime)
    artifacts: dict[int, Any] = {}
    if timing:
        selected, repeats = extra
        work = [
            (_unpack_program(api, packed[index], artifacts), steps)
            for index, steps in selected
        ]
        if repeats is None:
            repeats = max(
                1, math.ceil(0.2 / max(_lap(module, work, runtime=runtime), 1e-6))
            )
        work *= repeats
        _lap(module, work, runtime=runtime)
        seconds = min(_lap(module, work, runtime=runtime) for _ in range(5))
        with output.open("wb") as stream:
            marshal.dump((sum(steps for _, steps in work) / seconds, repeats), stream)
        return
    ignored = frozenset(extra)
    allow_cycles = not runtime.random and (
        runtime.capabilities.completion is Completion.PERIODIC
        or LANGUAGES[name].contract.answer_mode == "termination"
    )
    with gzip.open(output, "wb", compresslevel=1) as stream:
        for record in packed:
            events, cycle, commands = _observe(
                module,
                _unpack_program(api, record, artifacts),
                ignored,
                runtime=runtime,
                allow_cycles=allow_cycles,
            )
            # Project private classes before crossing revisions and preserve wide ints.
            memo: dict[int, object] = {}
            record_bytes = marshal.dumps(
                ([_plain(event, memo) for event in events], cycle, commands)
            )
            stream.write(_RECORD_SIZE.pack(len(record_bytes)))
            stream.write(record_bytes)


def _run_worker(
    source: Path, name: str, request: Path, output: Path, *, timing: bool = False
) -> None:
    command = [
        sys.executable,
        __file__,
        name,
        "--worker",
        str(source),
        str(request),
        str(output),
    ]
    if timing:
        command.append("--speed")
    try:
        subprocess.run(
            command,
            cwd=ROOT,
            check=True,
            timeout=_WORKER_TIMEOUT,
            env=dict(os.environ, PYTHONPATH=str(source), PYTHONHASHSEED="0"),
        )
    except subprocess.TimeoutExpired:
        raise SystemExit(
            f"trace worker for {name} exceeded {_WORKER_TIMEOUT}s"
        ) from None
    except subprocess.CalledProcessError as error:
        raise SystemExit(f"trace worker for {name} exited {error.returncode}") from None


def _observations(path: Path) -> Iterator[Observation]:
    with gzip.open(path, "rb") as stream:
        while length := stream.read(_RECORD_SIZE.size):
            (size,) = _RECORD_SIZE.unpack(length)
            # Read a whole record before decoding to avoid per-field gzip reads.
            payload = stream.read(size)
            if len(payload) != size:
                raise ValueError("incomplete trace observation")
            yield marshal.loads(payload)


def _worker_speeds(
    old: Path, new: Path, name: str, packed: list[tuple[object, str]], scratch: Path
) -> tuple[float, float]:
    selected = _timing_work(
        (index, commands)
        for index, (_, _, commands) in enumerate(_observations(scratch / "new.gz"))
    )
    request, output = scratch / "speed.in", scratch / "speed.out"
    repeats: int | None = None
    rates = []
    for source in (new, old):
        with request.open("wb") as stream:
            marshal.dump((packed, (selected, repeats)), stream)
        _run_worker(source, name, request, output, timing=True)
        with output.open("rb") as stream:
            rate, repeats = marshal.load(stream)
        rates.append(rate)
    now, was = rates
    return was, now


def _mutant_source(name: str, mutant: Path, target: Path | None, scratch: Path) -> Path:
    entry = Path(importlib.import_module(INTERPRETERS[name]).__file__ or "")
    path = entry if target is None else (ROOT / target).resolve()
    if path != entry and (
        entry.name != "__init__.py" or not path.is_relative_to(entry.parent)
    ):
        raise SystemExit(
            "mutant target must be the interpreter or one of its package files"
        )
    if not path.is_file() or path.suffix != ".py":
        raise SystemExit("mutant target must be an existing Python source file")
    source = scratch / "mutant"
    shutil.copytree(ROOT / "src", source, ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copyfile(mutant, source / path.relative_to(ROOT / "src"))
    return source


def main(argv: list[str] | None = None) -> int:
    """Print the first differences and the counts; return the exit status."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("language")
    parser.add_argument(
        "--old", default="main", help="revision with declared factory (default main)"
    )
    parser.add_argument("--mutant", type=Path, help="broken copy that must differ")
    parser.add_argument(
        "--mutant-target", type=Path, help="repo-relative interpreter file to replace"
    )
    parser.add_argument("--worker", nargs=3, type=Path, help=argparse.SUPPRESS)
    parser.add_argument(
        "--ignore-views", default="", help="comma-separated renamed views"
    )
    parser.add_argument("--random", type=int, default=RANDOM_PROGRAMS)
    parser.add_argument("--speed", action="store_true", help="also compare steps/s")
    args = parser.parse_args(argv)
    if args.worker:
        _worker(args.language, *args.worker, timing=args.speed)
        return 0
    if args.mutant_target is not None and args.mutant is None:
        parser.error("--mutant-target requires --mutant")
    if args.random < 0:
        parser.error("--random must be nonnegative")
    try:
        name = resolve(args.language)
    except ValueError as exc:
        parser.error(str(exc))
    ignored = frozenset(filter(None, args.ignore_views.split(",")))
    with tempfile.TemporaryDirectory() as directory:
        scratch = Path(directory)
        try:
            old = _checkout(args.old, scratch / "old")
        except ValueError as error:
            parser.error(str(error))
        programs = corpus(name, args.random)
        return _compare_revisions(name, programs, ignored, args, old, scratch)


def _compare_revisions(
    name: str,
    programs: list[Program],
    ignored: frozenset[str],
    args: argparse.Namespace,
    old: Path,
    scratch: Path,
) -> int:
    new = ROOT / "src"
    request = scratch / "corpus"
    before_path, after_path = scratch / "old.gz", scratch / "new.gz"
    artifacts: dict[int, object] = {}
    packed = [_pack_program(program, artifacts) for program in programs]
    with request.open("wb") as stream:
        marshal.dump((packed, sorted(ignored)), stream)
    _run_worker(old, name, request, before_path)
    _run_worker(new, name, request, after_path)
    pairs = zip(_observations(before_path), _observations(after_path), strict=True)
    found, halting, witnessed = _summarize(programs, pairs, projected=True)
    for (code, stdin), step, before, after in found[:3]:
        print(f"DIFF {code!r:.60} stdin={stdin[:20]!r} at step {step}")
        print(f"  {args.old}: {before!r:.300}")
        print(f"  new: {after!r:.300}")
    print(
        f"{name}: {len(programs)} programs ({halting} halt cleanly), "
        f"{len(found)} differ from {args.old}"
    )
    if not witnessed:
        print(f"{name}: no matching clean halt or declared cycle", file=sys.stderr)
        return 1
    failed = bool(found)
    if args.speed and not failed:
        try:
            was, now = _worker_speeds(old, new, name, packed, scratch)
        except ValueError as error:
            print(f"{name}: {error}", file=sys.stderr)
            return 1
        change = now / was - 1
        print(f"speed: {was:,.0f} -> {now:,.0f} steps/s ({change:+.0%})")
        failed |= change < -SLOWDOWN
    if args.mutant is not None:
        mutant = _mutant_source(name, args.mutant, args.mutant_target, scratch)
        mutant_path = scratch / "mutant.gz"
        _run_worker(mutant, name, request, mutant_path)
        pairs = zip(_observations(before_path), _observations(mutant_path), strict=True)
        caught = len(_summarize(programs, pairs, projected=True).differences)
        print(f"control: mutant differs on {caught}")
        failed |= not caught
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
