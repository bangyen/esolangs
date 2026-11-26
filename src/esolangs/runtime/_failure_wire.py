"""Encode and restore isolated worker failure records."""

from typing import Any

from esolangs import exceptions
from esolangs.runtime._error_causes import decode_cause, encode_cause
from esolangs.runtime._json import worker_dumps
from esolangs.runtime._result_wire import _counter, decode_result, encode_result

#: The worker's output-cap message, which also tells the parent the cap hit.
_OUTPUT_LIMIT = "isolated output limit exceeded"


def _restore_error_notes(error: exceptions.EsolangError, notes: object) -> None:
    """Keep absent and explicitly empty notes distinct."""
    if notes is None:
        error.__dict__.pop("__notes__", None)
    elif isinstance(notes, list) and all(isinstance(note, str) for note in notes):
        error.__notes__ = list(notes)
    else:
        raise ValueError("invalid isolated error notes")


def _error_from_wire(result: dict[str, Any], partial: str) -> exceptions.EsolangError:
    """Restore only the canonical error envelope and its explicit observation."""
    kind = result["error"]
    cls = getattr(exceptions, kind, None) if isinstance(kind, str) else None
    if not isinstance(cls, type) or not issubclass(cls, exceptions.EsolangError):
        raise ValueError("unknown isolated error kind")
    fields = {
        "error",
        "args",
        "notes",
        "execution",
        "output_limit",
        "cause",
        "suppress_context",
    }
    if issubclass(cls, exceptions.ExecutionBudgetError):
        fields.add("bound")
    if set(result) != fields or not isinstance(result["args"], list):
        raise ValueError("invalid isolated error fields")
    if (
        type(result["output_limit"]) is not bool
        or type(result["suppress_context"]) is not bool
    ):
        raise ValueError("invalid isolated error options")
    args = result["args"]
    # The wire keeps every argument positional; these options are keyword-only.
    options: dict[str, Any] = {}
    if kind == "UnknownLanguageError":
        if (
            len(args) != 2
            or not isinstance(args[0], str)
            or not isinstance(args[1], list)
            or any(not isinstance(name, str) for name in args[1])
        ):
            raise ValueError("invalid unknown-language error arguments")
        args, options = args[:1], {"suggestions": tuple(args[1])}
    elif kind == "InputExhaustedError":
        if len(args) != 3 or not isinstance(args[2], str):
            raise ValueError("invalid input-exhaustion error arguments")
        args, options = [_counter(args[0]), _counter(args[1])], {"unit": args[2]}
    error: exceptions.EsolangError = cls(*args, **options)
    if result["output_limit"] != (
        isinstance(error, exceptions.ExecutionCapError) and str(error) == _OUTPUT_LIMIT
    ):
        raise ValueError("inconsistent isolated output-limit marker")
    error.partial_output = partial
    _restore_error_notes(error, result["notes"])
    error.__cause__ = decode_cause(result["cause"])
    error.__suppress_context__ = result["suppress_context"]
    if isinstance(error, exceptions.ExecutionTimeoutError):
        if result["bound"] not in (
            "execution_timeout",
            "preparation_timeout",
            "total_timeout",
        ):
            raise ValueError("invalid timeout bound")
        error.bound = result["bound"]
    elif isinstance(error, exceptions.ExecutionCapError):
        # The marker and the bound are two spellings of one fact.
        if result["bound"] not in (
            ("max_output",) if result["output_limit"] else ("max_memory", "max_steps")
        ):
            raise ValueError("invalid cap bound")
        error.bound = result["bound"]
    elif isinstance(error, exceptions.ExecutionBudgetError):
        bound = result["bound"]
        if bound not in (
            None,
            "max_steps",
            "max_output",
            "max_memory",
            "execution_timeout",
            "preparation_timeout",
            "total_timeout",
        ):
            raise ValueError("invalid budget bound")
        if bound is not None:
            error.bound = bound
    if result["execution"] is not None:
        error.observation = decode_result(partial, result["execution"])
        if error.observation.completion is not None:
            raise ValueError("failed execution cannot declare completion")
    return error


def _failure_wire(
    error: BaseException, *, include_cause: bool = True
) -> dict[str, Any]:
    """Encode one retained failure for the worker's validated wire protocol."""
    args: tuple[object, ...] = error.args
    if isinstance(error, exceptions.UnknownLanguageError):
        args = (error.language, error.suggestions)
    elif isinstance(error, exceptions.InputExhaustedError):
        args = (error.reads, error.supplied, error.unit)
    observation = getattr(error, "observation", None)
    return {
        "error": type(error).__name__,
        "args": args,
        "notes": getattr(error, "__notes__", None),
        "cause": encode_cause(error.__cause__) if include_cause else None,
        "suppress_context": error.__suppress_context__,
        "execution": encode_result(observation) if observation is not None else None,
        **(
            {"bound": getattr(error, "bound", None)}
            if isinstance(error, exceptions.ExecutionBudgetError)
            else {}
        ),
        "output_limit": isinstance(error, exceptions.ExecutionCapError)
        and str(error) == _OUTPUT_LIMIT,
    }


def _failure_text(error: BaseException) -> str:
    try:
        return worker_dumps(_failure_wire(error))
    except MemoryError:
        return worker_dumps(_failure_wire(error, include_cause=False))
