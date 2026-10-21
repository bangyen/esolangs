"""The miner's search kernel: scoring, proposals, annealing, admissibility.

Split from :mod:`superopt.mine` (the file-size cap): everything here
is a pure function of a candidate program and the audit's
:class:`superopt.audit.Runner` -- the chain driver, the spend ledger
and the command entry points stay in ``mine``.
"""

from __future__ import annotations

import importlib
import random
from dataclasses import dataclass

from esolangs.exceptions import ExecutionTimeoutError, InterpreterLimitError
from esolangs.runtime._evaluate import _iter_evaluate

from .audit import Runner, _OracleTimeoutError, discriminating_order, row_bits

#: Screen tier: per-row wall bound for the chain's inner loop, and
#: how far past it the alarm backstop sits (the audit's discipline
#: at a cheaper bound; certification keeps the audit's bounds).
SCREEN_ROW_TIMEOUT = 0.05
SCREEN_BACKSTOP = 0.5

#: Cost weights (plan section 3).
WRONG_ROW_WEIGHT = 64
TIMEOUT_ROW_WEIGHT = 4096

#: Metropolis temperature schedule, geometric across a restart.
TEMP_START = 6.0
TEMP_END = 0.15

#: Exceptions that mean "this row ran out of its bound", as opposed
#: to "this row answered wrong": the alarm backstop, the runtime's
#: own timeout, and the interpreter step/limit caps the screen tier
#: leans on.  Any other exception is a wrong row.
_TIMEOUT_EXCEPTIONS = (
    _OracleTimeoutError,
    ExecutionTimeoutError,
    InterpreterLimitError,
)


# --- Scoring: the all-rows variant of Runner.check ---------------------


@dataclass(frozen=True)
class Score:
    """One candidate's full-table score under the screen bounds."""

    wrong: int
    timeouts: int

    @property
    def correct(self) -> bool:
        """Whether every row answered, and answered right."""
        return self.wrong == 0 and self.timeouts == 0

    def cost(self, length: int) -> int:
        """The plan's cost: length plus per-row penalties."""
        return (
            length + WRONG_ROW_WEIGHT * self.wrong + TIMEOUT_ROW_WEIGHT * self.timeouts
        )


def score_program(
    runner: Runner,
    program: str,
    table: str,
    *,
    row_timeout: float = SCREEN_ROW_TIMEOUT,
) -> Score:
    """Score ``program`` on every row of ``table``; never early-exit.

    Printing languages run rows in the audit's discriminating order
    (order affects nothing but tie-breaking in the chain's view);
    termination languages stream ``_iter_evaluate`` in its counting
    order, exactly as ``Runner.check`` does, with rows the stream
    never reaches charged to the failure that ended it.
    """
    n = len(table).bit_length() - 1
    wrong = 0
    timeouts = 0
    if runner.terminating:
        seen = 0
        try:
            answers = _iter_evaluate(
                runner.name, program, inputs=n, timeout=row_timeout
            )
            for i, answer in enumerate(answers):
                seen += 1
                if answer != table[i]:
                    wrong += 1
        except _TIMEOUT_EXCEPTIONS:
            timeouts += len(table) - seen
        except Exception:
            wrong += len(table) - seen
        else:
            wrong += len(table) - seen
        return Score(wrong, timeouts)
    for i in discriminating_order(table):
        try:
            answer = runner.answer_row(
                program,
                row_bits(i, n),
                timeout=row_timeout,
                backstop=SCREEN_BACKSTOP,
            )
        except _TIMEOUT_EXCEPTIONS:
            timeouts += 1
        except Exception:
            wrong += 1
        else:
            if answer != table[i]:
                wrong += 1
    return Score(wrong, timeouts)


# --- Operators (plan section 3) ----------------------------------------


def _span(program: str, rng: random.Random, low: int, high: int) -> tuple[int, int]:
    """A random (start, length) span with length in [low, high]."""
    length = rng.randint(low, min(high, len(program)))
    start = rng.randrange(len(program) - length + 1)
    return start, length


def _op_substitute(program: str, alphabet: tuple[str, ...], rng: random.Random) -> str:
    if not program:
        return program
    at = rng.randrange(len(program))
    return program[:at] + rng.choice(alphabet) + program[at + 1 :]


def _op_delete_char(
    program: str, _alphabet: tuple[str, ...], rng: random.Random
) -> str:
    if not program:
        return program
    at = rng.randrange(len(program))
    return program[:at] + program[at + 1 :]


def _op_insert(program: str, alphabet: tuple[str, ...], rng: random.Random) -> str:
    at = rng.randrange(len(program) + 1)
    return program[:at] + rng.choice(alphabet) + program[at:]


def _op_delete_span(program: str, alphabet: tuple[str, ...], rng: random.Random) -> str:
    if len(program) < 2:
        return _op_delete_char(program, alphabet, rng)
    start, length = _span(program, rng, 2, 8)
    return program[:start] + program[start + length :]


def _op_move_span(program: str, _alphabet: tuple[str, ...], rng: random.Random) -> str:
    if len(program) < 2:
        return program
    start, length = _span(program, rng, 1, 8)
    piece = program[start : start + length]
    rest = program[:start] + program[start + length :]
    at = rng.randrange(len(rest) + 1)
    return rest[:at] + piece + rest[at:]


def _op_duplicate_span(
    program: str, _alphabet: tuple[str, ...], rng: random.Random
) -> str:
    if not program:
        return program
    start, length = _span(program, rng, 1, 8)
    piece = program[start : start + length]
    return program[:start] + piece + piece + program[start + length :]


def _op_replace_span(
    program: str, alphabet: tuple[str, ...], rng: random.Random
) -> str:
    if not program:
        return _op_insert(program, alphabet, rng)
    start, length = _span(program, rng, 1, 4)
    fresh = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 4)))
    return program[:start] + fresh + program[start + length :]


#: (name, weight, operator) in the plan's table order; weights sum to 1.
OPERATORS = (
    ("substitute", 0.30, _op_substitute),
    ("delete_char", 0.20, _op_delete_char),
    ("insert", 0.15, _op_insert),
    ("delete_span", 0.12, _op_delete_span),
    ("move_span", 0.10, _op_move_span),
    ("duplicate_span", 0.08, _op_duplicate_span),
    ("replace_span", 0.05, _op_replace_span),
)
_OPERATOR_FUNCS = tuple(op for _name, _weight, op in OPERATORS)
_OPERATOR_WEIGHTS = tuple(weight for _name, weight, _op in OPERATORS)


def propose(program: str, alphabet: tuple[str, ...], rng: random.Random) -> str:
    """One Metropolis proposal: a single weighted operator applied."""
    operator = rng.choices(_OPERATOR_FUNCS, weights=_OPERATOR_WEIGHTS, k=1)[0]
    return operator(program, alphabet, rng)


def temperature(step: int, steps: int) -> float:
    """Geometric anneal from TEMP_START to TEMP_END across a restart."""
    if steps <= 1:
        return TEMP_END
    fraction = step / (steps - 1)
    # mypy types float ** float as Any; the value is a positive real,
    # and the annotation states its runtime type.
    result: float = TEMP_START * (TEMP_END / TEMP_START) ** fraction
    return result


# --- Painfuck admissibility (plan section 3) ---------------------------


def painfuck_decoded(program: str) -> str:
    """Decode Painfuck text with the interpreter's own ``_translate``."""
    module = importlib.import_module("esolangs.languages.painfuck.interpreter")
    return str(module._translate(program))  # noqa: SLF001


def painfuck_admissible(program: str) -> bool:
    """Whether a Painfuck candidate may be recorded as a find.

    The decoded command ``y`` is random (skip the next command with
    probability 1/2), so a candidate using it can pass by luck; the
    search may pass through such candidates but never record one.
    Shipped programs at n=2..4 never decode to ``y`` (plan section 3),
    so the rule excludes no shipped behaviour.
    """
    return "y" not in painfuck_decoded(program)
