"""Pure-core mutation, repeatability and effect boundaries for every interpreter."""

import builtins
import dataclasses
import inspect
import sys
from collections import deque
from collections.abc import Mapping
from pathlib import Path
from types import FrameType
from typing import Any

import pytest

import esolangs
from esolangs.registry import LANGUAGES
from esolangs.runtime._answers import encode_inputs
from esolangs.runtime.io import IO, ScriptedIO
from esolangs.vm import make_vm
from tests.support.samples import SAMPLES

pytestmark = pytest.mark.medium
_CORE_NAMES = frozenset(
    {"_advance", "_iterate", "_generation", "_at_eof", "_tick", "_rewrite"}
)
_MEMOS = frozenset({"_digest", "_sorted", "__dict__", "__weakref__"})


def _value(value: Any, ancestors: frozenset[int] = frozenset()) -> Any:
    """Capture semantic fields, including mutable containers under frozen records."""
    if isinstance(value, (str, bytes, int, float, bool, type(None))):
        return value
    if id(value) in ancestors:
        return ("cycle", type(value).__qualname__)
    ancestors = ancestors | {id(value)}
    if isinstance(value, Mapping):
        return (
            "mapping",
            frozenset(
                (_value(k, ancestors), _value(v, ancestors)) for k, v in value.items()
            ),
        )
    if isinstance(value, (tuple, list, deque)):
        return tuple(_value(v, ancestors) for v in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_value(v, ancestors) for v in value)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return (
            type(value).__qualname__,
            tuple(
                (f.name, _value(getattr(value, f.name), ancestors))
                for f in dataclasses.fields(value)
            ),
        )
    if callable(value):
        return ("callable", id(value))
    fields = dict(vars(value)) if hasattr(value, "__dict__") else {}
    for cls in type(value).__mro__:
        slots = cls.__dict__.get("__slots__", ())
        if isinstance(slots, str):
            slots = (slots,)
        for slot in slots:
            if hasattr(value, slot):
                fields[slot] = getattr(value, slot)
    if fields:
        # Memoized hashes/sorted views do not change the represented state.
        return (
            type(value).__qualname__,
            tuple(
                sorted(
                    (k, _value(v, ancestors))
                    for k, v in fields.items()
                    if k not in _MEMOS and "cache" not in k
                )
            ),
        )
    return (type(value).__qualname__, repr(value))


def _immutable(value: Any, ancestors: frozenset[int] = frozenset()) -> bool:
    """Reject mutable collections and records in the changing state graph."""
    if id(value) in ancestors:
        return True
    ancestors = ancestors | {id(value)}
    if isinstance(value, (list, dict, set, bytearray, deque)):
        return False
    if isinstance(value, Mapping):
        return all(
            _immutable(k, ancestors) and _immutable(v, ancestors)
            for k, v in value.items()
        )
    if isinstance(value, (tuple, frozenset)):
        return all(_immutable(v, ancestors) for v in value)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        if not value.__dataclass_params__.frozen:
            return False
        # Parsed functions are fixed program data, rather than changing state.
        return all(
            _immutable(getattr(value, f.name), ancestors)
            for f in dataclasses.fields(value)
            if f.name not in {"func", "fn"}
        )
    return True


def _core(frame: FrameType) -> bool:
    name = frame.f_code.co_name
    return (
        (name in _CORE_NAMES or name.startswith("_advance_"))
        and "." not in frame.f_code.co_qualname
        and "/languages/" in frame.f_code.co_filename
    )


def _inside_core(frame: FrameType | None) -> bool:
    while frame is not None:
        if _core(frame):
            return True
        frame = frame.f_back
    return False


class _Audit:
    def __init__(self) -> None:
        self.pending: dict[int, tuple[Any, Any, str]] = {}
        self.mutations: list[str] = []
        self.mutable_states: list[str] = []
        self.effects: list[str] = []
        self.differences: list[str] = []
        self.replayed = 0
        self.observed = False

    def profile(self, frame: FrameType, event: str, arg: Any) -> None:
        code = frame.f_code
        if event == "call" and _core(frame):
            names = code.co_varnames[: code.co_argcount + code.co_kwonlyargcount]
            args = {
                name: frame.f_locals[name] for name in names if name in frame.f_locals
            }
            for name in ("state", "core", "run", "frames"):
                if name in args and not _immutable(args[name]):
                    self.mutable_states.append(f"{code.co_name}: {name}")
            self.pending[id(frame)] = (args, _value(args), code.co_name)
            self.observed = True
        elif event == "return" and id(frame) in self.pending:
            args, before, name = self.pending.pop(id(frame))
            if arg is not None and not _immutable(arg):
                self.mutable_states.append(f"{name}: result")
            if _value(args) != before:
                self.mutations.append(name)
            fn = frame.f_globals.get(name)
            if arg is not None and inspect.isfunction(fn) and fn.__code__ is code:
                try:
                    again = fn(**args)
                except Exception as exc:  # a successful call must succeed again
                    self.differences.append(f"{name}: {type(exc).__name__}")
                else:
                    self.replayed += 1
                    if _value(again) != _value(arg):
                        self.differences.append(name)
        if event == "call":
            receiver = frame.f_locals.get("self")
            effect = isinstance(receiver, IO) and code.co_name not in {
                "position",
                "progress",
            }
            effect |= (
                code.co_name == "draw" and "/runtime/randomness.py" in code.co_filename
            )
        elif event == "c_call":
            effect = arg in (builtins.print, builtins.input, builtins.open)
            effect |= getattr(arg, "__module__", None) == "time"
            owner = getattr(arg, "__self__", None)
            effect |= getattr(owner, "__module__", None) == "datetime" and getattr(
                arg, "__name__", ""
            ) in {"now", "utcnow", "today"}
        else:
            return
        if effect and _inside_core(frame):
            self.effects.append(code.co_name)

    def __enter__(self) -> "_Audit":
        self.previous = sys.getprofile()
        sys.setprofile(self.profile)
        return self

    def __exit__(self, *args: object) -> None:
        sys.setprofile(self.previous)


def test_purity_audit_detects_mutation_and_effects(tmp_path: Path) -> None:
    namespace: dict[str, Any] = {}
    # A real path outside coverage's `source` (src/esolangs) that still looks
    # like a language interpreter: `_core` keys on "/languages/".  A fake name
    # under src/esolangs leaves a record coverage cannot read, and `coverage
    # report` then exits nonzero on "No source for code".
    filename = tmp_path / "languages" / "_positive_control" / "interpreter.py"
    source = (
        "def _advance(state, io):\n"
        " state.append(1)\n"
        ' io.print_char("x")\n'
        " return tuple(state)\n"
    )
    exec(compile(source, str(filename), "exec"), namespace)
    with _Audit() as audit:
        namespace["_advance"]([], ScriptedIO(""))
    assert audit.mutations
    assert audit.mutable_states
    assert audit.effects
    assert audit.differences


@pytest.mark.parametrize("language", sorted(LANGUAGES))
def test_interpreter_core_is_pure_for_its_sample(language: str) -> None:
    program, stdin = SAMPLES[language]
    if program == "" and LANGUAGES[language].boolean is not None:
        program = esolangs.generate(language, "01")
        stdin = encode_inputs(language, (0,), truth_table="01")
    vm = make_vm(language, program, stdin=stdin)
    with _Audit() as audit:
        for _ in range(100):
            if vm.halted:
                break
            vm.step()
    assert audit.observed, "sample must actually reach its pure core"
    assert not audit.mutations, audit.mutations
    assert not audit.mutable_states, audit.mutable_states
    assert not audit.effects, audit.effects
    assert not audit.differences, audit.differences
    assert audit.replayed, (
        "sample must supply a successful transition as a positive control"
    )
