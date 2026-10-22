"""Stochastic mining: a STOKE-style sampler over shipped programs.

The v2 audit enumerates; this module samples.  For one language and
one truth table, a Metropolis chain over strings of the generator's
corpus alphabet looks for a program *shorter than the shipped one*
that computes the table.  A find is a hypothesis, not a result: it
must still pass the repo's generator bar (ablation pricing at bar
arities) before anything ships, and a no-find at a stated budget is
a bounded null, never a minimality claim.

Semantics are the audit's, unchanged.  Rows are answered through
:class:`superopt.audit.Runner`; the inner loop scores with a thin
all-rows variant of ``Runner.check`` (partial credit instead of
early exit, a 50 ms screen bound instead of the audit's 5 s), and
nothing is recorded until it passes the audit's certification tier:
``Runner.certify`` over the full table at the audit's bounds, plus
``Runner.reads`` matching the shipped program's per-row read counts
where the scripted-IO oracle exists.  The screen can lose a find
(a slow-but-valid program); it can never manufacture one.

Cost (plan section 3): ``len + 64 * wrong_rows + 4096 *
timeout_rows``, counted over *every* row -- finite tables make
exactness cheap, so unlike STOKE there is no test-case compromise.
Acceptance is Metropolis with the temperature annealed
geometrically from 6.0 to 0.15 across each restart: the known
FALSE gaps are reorderings reached through equal- or worse-scoring
intermediates, which a hill-climb cannot cross.

Spend is accounted in CPU seconds in a JSON ledger on disk; the
pilot's hard caps live here as constants (20 CPU-hours total,
2 CPU-hours for the control phase) and are enforced before every
search, across runs.
"""

from __future__ import annotations

import importlib
import json
import math
import random
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import esolangs

from .audit import Runner, corpus_for
from .kernel import (
    Score,
    painfuck_admissible,
    propose,
    score_program,
    temperature,
)
from .machine import SUFFIX_ALPHABET
from .search import Stats
from .search import certify as _gadget_certify
from .search import search as _gadget_search
from .targets import SHIPPED_SUFFIX, suffix_spec

#: Spend caps, enforced from the on-disk ledger (plan sections 5, 7).
TOTAL_CAP_CPU_S = 20 * 3600.0
CONTROL_CAP_CPU_S = 2 * 3600.0

#: Chain-state checkpoints land this often (evaluations).
CHECKPOINT_EVERY = 1000

#: The pilot's per-language records are data, not code (control.json,
#: beside this module): the hunt languages in order, the one language
#: whose decoded stream carries an admissibility rule, and the
#: control sets spelled out in the control section below.
_CONTROL = json.loads(
    Path(__file__).with_name("control.json").read_text(encoding="utf-8")
)

#: The pilot's languages, in hunt order (plan section 4).
PILOT_LANGUAGES: tuple[str, ...] = tuple(_CONTROL["pilot_languages"])

#: The language whose candidates must pass the kernel's decoded-stream
#: admissibility rule (plan section 3).
_DECODED_LANGUAGE: str = _CONTROL["decoded_language"]


# --- Admissibility dispatch (plan section 3) -----------------------------


def _admissible(language: str, program: str) -> bool:
    """Whether a candidate for ``language`` may be recorded as a find.

    Only the decoded-stream language has a rule -- its decoded ``y``
    command is random (skip the next command with probability 1/2),
    so the kernel's check decides there; every other language admits
    any candidate the screen scores correct.
    """
    if language == _DECODED_LANGUAGE:
        return painfuck_admissible(program)
    return True


# --- Spend ledger --------------------------------------------------------


class Ledger:
    """CPU-second accounting across runs, in one JSON file on disk.

    Every completed search charges its CPU time here; the pilot's
    caps are checked against these totals before each new search,
    so no sequence of invocations can spend past them unnoticed.
    """

    def __init__(self, path: Path | str) -> None:
        """Load the ledger at ``path`` (an empty one if absent)."""
        self.path = Path(path)
        self.entries: list[dict[str, Any]] = []
        if self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.entries = list(data.get("entries", []))

    def total(
        self,
        *,
        phase: str | None = None,
        language: str | None = None,
    ) -> float:
        """CPU seconds charged, optionally filtered by phase/language."""
        return sum(
            float(entry["cpu_s"])
            for entry in self.entries
            if (phase is None or entry.get("phase") == phase)
            and (language is None or entry.get("language") == language)
        )

    def remaining_total(self) -> float:
        """CPU seconds left under the pilot's overall hard cap."""
        return TOTAL_CAP_CPU_S - self.total()

    def remaining_control(self) -> float:
        """CPU seconds left under the control phase's cap."""
        return CONTROL_CAP_CPU_S - self.total(phase="control")

    def charge(
        self,
        *,
        phase: str,
        language: str,
        cpu_s: float,
        evals: int,
        command: str,
    ) -> None:
        """Record one search's spend and rewrite the ledger file."""
        self.entries.append(
            {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "phase": phase,
                "language": language,
                "cpu_s": round(cpu_s, 3),
                "evals": evals,
                "command": command,
            }
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"entries": self.entries}, indent=1), encoding="utf-8"
        )


def review_required(ledger: Ledger, language: str) -> bool:
    """Whether hunting ``language`` waits on the first-language review.

    The plan funds one hunt language, then requires a review before
    the rest.  A language with hunt entries already is the reviewed
    one (or predates the gate); a fresh language while another has
    hunt entries is gated on ``notes/miner-review.json`` existing.
    """
    hunted = {
        entry.get("language")
        for entry in ledger.entries
        if entry.get("phase") == "hunt"
    }
    return language not in hunted and bool(hunted)


# --- Chain-state checkpoints ---------------------------------------------


def _encode_rng(rng: random.Random) -> list[Any]:
    version, state, gauss = rng.getstate()
    return [version, list(state), gauss]


def _decode_rng(data: list[Any]) -> random.Random:
    rng = random.Random()
    rng.setstate((int(data[0]), tuple(int(x) for x in data[1]), data[2]))
    return rng


def _slug(text: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in text)


def checkpoint_path(directory: Path | str, language: str, table: str) -> Path:
    """The checkpoint file for one (language, table) chain."""
    return Path(directory) / f"{_slug(language)}-{table}.json"


# --- One search ------------------------------------------------------------


def _certify_candidate(
    runner: Runner,
    program: str,
    table: str,
    baseline_reads: tuple[int, ...] | None,
) -> tuple[bool, str]:
    """The certification tier: (passes, why-not) for a screen-correct hit.

    Mirrors the audit's record path: full-table ``certify`` at the
    audit's bounds, then the consumption oracle where it exists.
    """
    if not _admissible(runner.name, program):
        return False, "inadmissible: decoded stream uses the random y command"
    if not runner.certify(program, table):
        return False, "certify failed at the audit's bounds"
    if baseline_reads is not None and runner.reads(program, table) != baseline_reads:
        return False, "consumption differs from the shipped program"
    return True, ""


def _gap_pct(shipped: str, size: int) -> float:
    return round(100.0 * (len(shipped) - size) / len(shipped), 1)


def _append_jsonl(path: Path | None, record: dict[str, Any]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")
        handle.flush()


def _restore_state(
    state: dict[str, Any],
    saved: dict[str, Any],
    record: dict[str, Any],
    shipped: str,
) -> None:
    """Fold a checkpoint's chain state back into a fresh search."""
    for key in (
        "wall_spent",
        "cpu_spent",
        "evals",
        "rejects",
        "restart",
        "step",
        "current",
        "best_program",
        "found",
        "found_size",
        "alt",
    ):
        state[key] = saved[key]
    state["current_score"] = Score(*saved["current_score"])
    state["best_cost"] = saved["best_cost"]
    state["rng"] = _decode_rng(saved["rng"]) if saved["rng"] is not None else None
    if state["found"] is not None:
        record["found"] = state["found"]
        record["found_size"] = state["found_size"]
        record["gap_pct"] = _gap_pct(shipped, state["found_size"])
    record["alt"] = state["alt"]


def _seed_random_restart(
    runner: Runner,
    alphabet: tuple[str, ...],
    table: str,
    shipped: str,
    state: dict[str, Any],
    rng: random.Random,
    per_restart: int,
    consider: Callable[[str, Score], None],
) -> None:
    """Restart B's seeding (plan section 3).

    The best of up to 200 random strings of shipped length guards
    against the shipped layout being a bad basin; the seed scorings
    are evaluations of this restart.
    """
    best_seed: str | None = None
    best_seed_cost: int | None = None
    for _ in range(min(200, per_restart)):
        if state["step"] >= per_restart:
            break
        candidate = "".join(rng.choice(alphabet) for _ in range(len(shipped)))
        scored = score_program(runner, candidate, table)
        state["evals"] += 1
        state["step"] += 1
        consider(candidate, scored)
        cost = scored.cost(len(candidate))
        if best_seed_cost is None or cost < best_seed_cost:
            best_seed, best_seed_cost = candidate, cost
    state["current"] = best_seed if best_seed is not None else shipped
    state["current_score"] = None


def mine_search(
    runner: Runner,
    alphabet: tuple[str, ...],
    table: str,
    *,
    class_label: str,
    phase: str = "hunt",
    eval_budget: int = 50_000,
    restarts: int = 2,
    seed: int = 184_700,
    start_program: str | None = None,
    wall_seconds: float = 1800.0,
    checkpoint: Path | None = None,
    resume: bool = False,
    finds_path: Path | None = None,
    rejects_path: Path | None = None,
) -> dict[str, Any]:
    """Mine one (language, table) pair; return its search record.

    The record follows plan section 3's find-record shape, plus
    ``phase``, ``cpu_s``, ``outcome`` and ``rejects``.  Certified
    finds are streamed to ``finds_path`` the moment they certify,
    and the chain state is checkpointed every ``CHECKPOINT_EVERY``
    evaluations so an interrupted run resumes where it stopped.
    """
    n = len(table).bit_length() - 1
    cpu_began = time.process_time()
    wall_began = time.monotonic()
    record: dict[str, Any] = {
        "language": runner.name,
        "arity": n,
        "table": table,
        "class": class_label,
        "phase": phase,
        "shipped_size": -1,
        "found_size": None,
        "found": None,
        "gap_pct": None,
        "consumption": "n/a",
        "evals": 0,
        "restarts": restarts,
        "seed": seed,
        "wall_s": 0.0,
        "cpu_s": 0.0,
        "outcome": "no_find",
        "alt": None,
        "rejects": 0,
    }

    def finish(outcome: str) -> dict[str, Any]:
        record["outcome"] = outcome
        record["wall_s"] = round(state["wall_spent"] + time.monotonic() - wall_began, 1)
        record["cpu_s"] = round(state["cpu_spent"] + time.process_time() - cpu_began, 1)
        record["evals"] = state["evals"]
        record["rejects"] = state["rejects"]
        return record

    state: dict[str, Any] = {
        "wall_spent": 0.0,
        "cpu_spent": 0.0,
        "evals": 0,
        "rejects": 0,
    }
    lang = esolangs.Language(runner.name)
    try:
        shipped = lang.generate(table)
    except Exception as exc:  # a refusal is a record, not a crash
        record["note"] = f"generate raised {type(exc).__name__}"
        return finish("unsupported")
    if not isinstance(shipped, str):
        record["note"] = "generate produced no char-sized program"
        return finish("unsupported")
    record["shipped_size"] = len(shipped)
    if not runner.certify(shipped, table):
        record["note"] = "shipped program does not evaluate to its table"
        return finish("unverifiable")
    baseline = runner.reads(shipped, table)
    if baseline is not None:
        record["consumption"] = "verified"
    elif not runner.terminating:
        record["consumption"] = "unverified"
    if not alphabet:
        record["note"] = "no corpus alphabet for this language"
        return finish("unsupported")

    per_restart = max(1, eval_budget // max(1, restarts))
    state.update(
        {
            "restart": 0,
            "step": 0,
            "current": shipped,
            "current_score": None,
            "best_program": shipped,
            "best_cost": None,
            "found": None,
            "found_size": None,
            "alt": None,
            "rng": None,
        }
    )
    if resume and checkpoint is not None and checkpoint.exists():
        saved = json.loads(checkpoint.read_text(encoding="utf-8"))
        if (
            saved.get("language") == runner.name
            and saved.get("table") == table
            and saved.get("seed") == seed
            and saved.get("shipped") == shipped
        ):
            _restore_state(state, saved, record, shipped)

    def save_checkpoint() -> None:
        if checkpoint is None:
            return
        checkpoint.parent.mkdir(parents=True, exist_ok=True)
        current_score = state["current_score"]
        checkpoint.write_text(
            json.dumps(
                {
                    "language": runner.name,
                    "table": table,
                    "class": class_label,
                    "phase": phase,
                    "seed": seed,
                    "eval_budget": eval_budget,
                    "restarts": restarts,
                    "shipped": shipped,
                    "wall_spent": state["wall_spent"] + time.monotonic() - wall_began,
                    "cpu_spent": state["cpu_spent"] + time.process_time() - cpu_began,
                    "evals": state["evals"],
                    "rejects": state["rejects"],
                    "restart": state["restart"],
                    "step": state["step"],
                    "current": state["current"],
                    "current_score": (
                        [current_score.wrong, current_score.timeouts]
                        if current_score is not None
                        else [0, 0]
                    ),
                    "best_program": state["best_program"],
                    "best_cost": state["best_cost"],
                    "found": state["found"],
                    "found_size": state["found_size"],
                    "alt": state["alt"],
                    "rng": _encode_rng(state["rng"])
                    if state["rng"] is not None
                    else None,
                }
            ),
            encoding="utf-8",
        )

    def consider(program: str, scored: Score) -> None:
        """Certify-and-record path for a screen-correct candidate."""
        if not scored.correct:
            return
        threshold = (
            state["found_size"] if state["found_size"] is not None else len(shipped)
        )
        if len(program) < threshold:
            ok, why = _certify_candidate(runner, program, table, baseline)
            if ok:
                state["found"] = program
                state["found_size"] = len(program)
                record["found"] = program
                record["found_size"] = len(program)
                record["gap_pct"] = _gap_pct(shipped, len(program))
                _append_jsonl(
                    finds_path,
                    {
                        "event": "find",
                        "language": runner.name,
                        "arity": n,
                        "table": table,
                        "class": class_label,
                        "phase": phase,
                        "shipped_size": len(shipped),
                        "found_size": len(program),
                        "found": program,
                        "gap_pct": record["gap_pct"],
                        "consumption": record["consumption"],
                        "evals": state["evals"],
                        "seed": seed,
                    },
                )
            else:
                state["rejects"] += 1
                _append_jsonl(
                    rejects_path,
                    {
                        "event": "reject",
                        "language": runner.name,
                        "table": table,
                        "program": program,
                        "size": len(program),
                        "reason": why,
                        "evals": state["evals"],
                    },
                )
        elif (
            len(program) == len(shipped) and program != shipped and state["alt"] is None
        ):
            ok, _why = _certify_candidate(runner, program, table, baseline)
            if ok:
                state["alt"] = program
                record["alt"] = program

    bounded = _run_chains(
        runner=runner,
        alphabet=alphabet,
        table=table,
        shipped=shipped,
        state=state,
        per_restart=per_restart,
        restarts=restarts,
        seed=seed,
        start_program=start_program,
        wall_seconds=wall_seconds,
        wall_began=wall_began,
        consider=consider,
        save_checkpoint=save_checkpoint,
    )
    if bounded:
        return finish("find" if state["found"] is not None else "bounded")
    if checkpoint is not None and checkpoint.exists():
        checkpoint.unlink()
    return finish("find" if state["found"] is not None else "no_find")


def _run_chains(
    *,
    runner: Runner,
    alphabet: tuple[str, ...],
    table: str,
    shipped: str,
    state: dict[str, Any],
    per_restart: int,
    restarts: int,
    seed: int,
    start_program: str | None,
    wall_seconds: float,
    wall_began: float,
    consider: Callable[[str, Score], None],
    save_checkpoint: Callable[[], None],
) -> bool:
    """Run the restarts over ``state``; True if the wall bound stopped it.

    Restart A seeds from the shipped program (or ``start_program``
    when a test plants a start point); later restarts seed from
    random strings.  The incumbent best and any certified find live
    in ``state`` throughout, so a checkpoint taken at any boundary
    resumes the search exactly.
    """
    while state["restart"] < restarts:
        restart = state["restart"]
        rng = state["rng"]
        if rng is None:
            rng = random.Random(f"mine:{seed}:{runner.name}:{table}:{restart}")
            state["rng"] = rng
            if restart == 0:
                state["current"] = (
                    start_program if start_program is not None else shipped
                )
                state["current_score"] = None
            else:
                _seed_random_restart(
                    runner,
                    alphabet,
                    table,
                    shipped,
                    state,
                    rng,
                    per_restart,
                    consider,
                )
        if state["current_score"] is None:
            current_score = score_program(runner, state["current"], table)
            state["current_score"] = current_score
            state["evals"] += 1
            state["step"] += 1
            current_cost = current_score.cost(len(state["current"]))
            if state["best_cost"] is None or current_cost < state["best_cost"]:
                state["best_cost"] = current_cost
                state["best_program"] = state["current"]
        save_checkpoint()
        while state["step"] < per_restart:
            if (
                state["evals"] % 256 == 0
                and time.monotonic() - wall_began > wall_seconds
            ):
                save_checkpoint()
                return True
            proposal = propose(state["current"], alphabet, rng)
            scored = score_program(runner, proposal, table)
            state["evals"] += 1
            state["step"] += 1
            consider(proposal, scored)
            cost = scored.cost(len(proposal))
            if state["best_cost"] is None or (cost, len(proposal)) < (
                state["best_cost"],
                len(state["best_program"]),
            ):
                state["best_cost"] = cost
                state["best_program"] = proposal
            delta = cost - state["current_score"].cost(len(state["current"]))
            if delta <= 0 or rng.random() < math.exp(
                -delta / temperature(state["step"], per_restart)
            ):
                state["current"] = proposal
                state["current_score"] = scored
            if state["evals"] % CHECKPOINT_EVERY == 0:
                save_checkpoint()
        state["restart"] += 1
        state["step"] = 0
        state["rng"] = None
        state["current_score"] = None
        save_checkpoint()
    return False


# --- Hunt tables (plan section 6) ------------------------------------------


def _screen_support() -> Any:
    """The fleet-canonical table corpora, loaded from tests/support.

    ``screen_support`` imports ``scripts.benchmark``, so the repo
    root must be importable; running ``python -m superopt`` from the
    root already puts it on ``sys.path``, and this makes it explicit.
    """
    root = str(Path(__file__).resolve().parents[2])
    if root not in sys.path:
        sys.path.insert(0, root)
    return importlib.import_module("tests.support.screen_support")


def named_tables(n: int) -> dict[str, str]:
    """The named family: parity, majority, and, or at arity ``n``."""
    rows = range(1 << n)
    return {
        "parity": "".join(str(row.bit_count() % 2) for row in rows),
        "majority": "".join("1" if row.bit_count() * 2 > n else "0" for row in rows),
        "and": "".join("1" if row == (1 << n) - 1 else "0" for row in rows),
        "or": "".join("0" if row == 0 else "1" for row in rows),
    }


def hunt_tables(n: int) -> list[tuple[str, str]]:
    """(class label, table) pairs for one hunt arity, in plan order."""
    support = _screen_support()
    items: list[tuple[str, str]] = [
        (key, table) for key, table in support.corpus(n).items()
    ]
    items.extend((f"named/{name}", table) for name, table in named_tables(n).items())
    rng = random.Random(184_700 + n)
    for _ in range(12):
        items.append(("random", support.random_table(n, rng)))
    return items


def class_table(n: int, class_label: str) -> str:
    """Resolve one class label at arity ``n`` to its table.

    Accepts a ``screen_support.corpus`` key (``tiled``, ``zero``, ...)
    or a named-family label, bare (``parity``) or prefixed
    (``named/parity``).
    """
    name = class_label.removeprefix("named/")
    if name in named_tables(n):
        return named_tables(n)[name]
    corpus = _screen_support().corpus(n)
    if class_label in corpus:
        return str(corpus[class_label])
    known = sorted(corpus) + [f"named/{key}" for key in named_tables(n)]
    raise ValueError(f"unknown class {class_label!r}; known: {', '.join(known)}")


# --- The control set (plan sections 2 and 5) -------------------------------

#: Control 2 pairs: (language, table, recorded found size).  A pair is
#: in scope only while its premise lives on current main: the shipped
#: program is strictly larger than the recorded find, and the recorded
#: find still certifies and consumption-matches on the current
#: interpreter.  Re-scoped 2026-10-20 (verification log:
#: notes/rescope-2026-10-20.log) after the first gate run failed on
#: premises the fix phase had retired: FALSE 00 and 11, Caballo 11 and
#: Circuit Diagram 01 now ship the recorded find itself (shipped ==
#: found size), and Eval 00/11 ship at the found size, so six of the
#: original ten pairs are un-rediscoverable by construction.  FALSE 01
#: joins from the old Control 3: its v2 certificate was against the
#: pre-#23 spelling (shipped ``^1&.`` at 4); #23 re-spelled the pair
#: to 16 chars while ``^1&.`` still computes it (re-verified), so it is a
#: live gap, not a minimal pair.  ArrowQueue 00 is promoted from the
#: secondary set: its premise re-verified by certification (it is a
#: termination-mode pair, so consumption is unmeasurable there, as
#: the audit already flagged).
CONTROL_GAPS: tuple[tuple[str, str, int], ...] = tuple(
    (language, table, int(found)) for language, table, found in _CONTROL["control_gaps"]
)
#: Termination-mode pairs kept report-only.  Unary 00's recorded find
#: is the empty program; its current shipped form is a CompressedText
#: object rather than text, so the miner records it unsupported.
CONTROL_SECONDARY: tuple[tuple[str, str, int], ...] = tuple(
    (language, table, int(found))
    for language, table, found in _CONTROL["control_secondary"]
)
#: Audit-certified minimal pairs: the miner must record zero finds.
#: A pair qualifies only while its current shipped program is
#: byte-identical to the program the v2 audit certified (checked
#: against the audit-era tree).  FALSE 01 was disqualified by the
#: 2026-10-20 re-scope (re-spelled by #23; it is a Control 2 pair
#: now); Bitwise Cyclic Tag 00 takes its place -- shipped ``0,$0``
#: byte-identical in both trees, as are Smallfuck 00 and Taglate 00.
CONTROL_MINIMAL: tuple[tuple[str, str], ...] = tuple(
    (language, table) for language, table in _CONTROL["control_minimal"]
)
#: Control 2's pass bar: at least 9 rediscoveries, or all-but-one of
#: the qualifying pairs when fewer than 10 qualify (the 2026-10-20
#: re-scope qualified 6, so the bar is 5).
CONTROL_PASS_COUNT = 9 if len(CONTROL_GAPS) >= 10 else len(CONTROL_GAPS) - 1


def harness_control(max_length: int = 6) -> bool:
    """Control 1: the v1 positive control, as ``superopt control`` runs it."""
    spec = suffix_spec()
    stats = Stats()
    result = _gadget_search(spec, SUFFIX_ALPHABET, max_length, stats)
    if result.length is None or result.hits != (SHIPPED_SUFFIX,):
        return False
    return all(_gadget_certify(hit, spec) for hit in result.hits)


# --- Command drivers (used by superopt.cli) ---------------------------------


class _Contexts:
    """Per-language Runner/corpus cache for one command invocation."""

    def __init__(self) -> None:
        self.runners: dict[str, Runner] = {}
        self.alphabets: dict[str, tuple[str, ...]] = {}

    def get(self, language: str) -> tuple[Runner, tuple[str, ...]]:
        if language not in self.runners:
            self.runners[language] = Runner(language)
            self.alphabets[language] = corpus_for(language).alphabet
        return self.runners[language], self.alphabets[language]


def _run_search(
    contexts: _Contexts,
    *,
    language: str,
    table: str,
    class_label: str,
    phase: str,
    eval_budget: int,
    restarts: int,
    seed: int,
    wall_seconds: float,
    checkpoint_dir: Path,
    resume: bool,
    out_path: Path,
    finds_path: Path,
    rejects_path: Path,
    ledger: Ledger,
    command: str,
) -> dict[str, Any]:
    """One search, streamed to disk and charged to the ledger."""
    runner, alphabet = contexts.get(language)
    record = mine_search(
        runner,
        alphabet,
        table,
        class_label=class_label,
        phase=phase,
        eval_budget=eval_budget,
        restarts=restarts,
        seed=seed,
        wall_seconds=wall_seconds,
        checkpoint=checkpoint_path(checkpoint_dir, runner.name, table),
        resume=resume,
        finds_path=finds_path,
        rejects_path=rejects_path,
    )
    _append_jsonl(out_path, record)
    ledger.charge(
        phase=phase,
        language=runner.name,
        cpu_s=float(record["cpu_s"]),
        evals=int(record["evals"]),
        command=command,
    )
    found = (
        f" -> find {record['found']!r} ({record['found_size']} chars)"
        if record["outcome"] == "find"
        else ""
    )
    print(
        f"  {record['language']} table {table} [{class_label}]: "
        f"{record['outcome']} ({record['evals']} evals, "
        f"{record['cpu_s']}s cpu){found}",
        flush=True,
    )
    return record


def run_control(
    *,
    ledger: Ledger,
    out_path: Path,
    finds_path: Path,
    rejects_path: Path,
    checkpoint_dir: Path,
    eval_budget: int = 20_000,
    seed: int = 184_700,
    wall_seconds: float = 1800.0,
) -> int:
    """The control gate: harness sanity, gap rediscovery, negative control.

    Exit codes: 0 = gate passed; 1 = a control failed; 2 = a spend
    cap stopped the gate before it could finish.
    """
    contexts = _Contexts()
    if not harness_control():
        print("control 1 (v1 harness): FAILED")
        return 1
    print("control 1 (v1 harness): passed")

    def caps_ok() -> bool:
        if ledger.remaining_total() <= 0:
            print("cap: the pilot's 20 CPU-hour total is spent; gate stops")
            return False
        if ledger.remaining_control() <= 0:
            print("cap: the control phase's 2 CPU-hour budget is spent")
            return False
        return True

    def probe(language: str, table: str, label: str) -> dict[str, Any]:
        return _run_search(
            contexts,
            language=language,
            table=table,
            class_label=label,
            phase="control",
            eval_budget=eval_budget,
            restarts=2,
            seed=seed,
            wall_seconds=wall_seconds,
            checkpoint_dir=checkpoint_dir,
            resume=False,
            out_path=out_path,
            finds_path=finds_path,
            rejects_path=rejects_path,
            ledger=ledger,
            command="mine-control",
        )

    rediscovered = 0
    for language, table, found_size in CONTROL_GAPS:
        if not caps_ok():
            return 2
        record = probe(language, table, "control")
        if record["outcome"] == "find" and record["found_size"] <= found_size:
            rediscovered += 1
    print(
        f"control 2 (gap rediscovery): {rediscovered}/{len(CONTROL_GAPS)} "
        f"(bar: {CONTROL_PASS_COUNT})"
    )
    for language, table, found_size in CONTROL_SECONDARY:
        if not caps_ok():
            return 2
        record = probe(language, table, "control-secondary")
        hit = record["outcome"] == "find" and record["found_size"] <= found_size
        verdict = "rediscovered" if hit else "not rediscovered"
        print(f"  secondary {language} {table}: {verdict} (report only)")
    manufactured = 0
    for language, table in CONTROL_MINIMAL:
        if not caps_ok():
            return 2
        record = probe(language, table, "control-minimal")
        if record["outcome"] == "find":
            manufactured += 1
    print(f"control 3 (no manufactured gaps): {manufactured} finds (bar: 0)")
    passed = rediscovered >= CONTROL_PASS_COUNT and manufactured == 0
    print(f"control gate {'PASSED' if passed else 'FAILED'}")
    return 0 if passed else 1


def run_one(
    *,
    language: str,
    arity: int,
    table: str | None,
    class_label: str | None,
    ledger: Ledger,
    out_path: Path,
    finds_path: Path,
    rejects_path: Path,
    checkpoint_dir: Path,
    eval_budget: int = 50_000,
    restarts: int = 2,
    seed: int = 184_700,
    wall_seconds: float = 1800.0,
    resume: bool = False,
) -> int:
    """Mine a single (language, table); the table comes from --table or --class."""
    if ledger.remaining_total() <= 0:
        print("cap: the pilot's 20 CPU-hour total is spent; refusing to search")
        return 2
    resolved = table if table is not None else class_table(arity, class_label or "")
    label = class_label if class_label is not None else "explicit"
    _run_search(
        _Contexts(),
        language=language,
        table=resolved,
        class_label=label,
        phase="one",
        eval_budget=eval_budget,
        restarts=restarts,
        seed=seed,
        wall_seconds=wall_seconds,
        checkpoint_dir=checkpoint_dir,
        resume=resume,
        out_path=out_path,
        finds_path=finds_path,
        rejects_path=rejects_path,
        ledger=ledger,
        command="mine-one",
    )
    return 0


def run_hunt(
    *,
    language: str,
    arities: tuple[int, ...] = (2, 3, 4),
    ledger: Ledger,
    out_path: Path,
    finds_path: Path,
    rejects_path: Path,
    checkpoint_dir: Path,
    review_marker: Path,
    eval_budget: int = 50_000,
    restarts: int = 2,
    seed: int = 184_700,
    wall_seconds: float = 1800.0,
    budget_cpu_s: float | None = None,
) -> int:
    """Hunt one language over the plan's table set, arities ascending.

    Stops at the invocation's CPU budget (the per-language stop),
    at the pilot's total cap, or when the table set is done.  A
    language with no hunt history while another language has some
    is refused until the first-language review marker exists.
    """
    if review_required(ledger, Runner(language).name) and not review_marker.exists():
        print(
            f"review gate: {language} has no hunt history but another "
            "language does; the plan requires the first-language review "
            f"first (write {review_marker} after reviewing, then re-run)"
        )
        return 2
    contexts = _Contexts()
    began = time.process_time()
    for arity in arities:
        for label, table in hunt_tables(arity):
            if ledger.remaining_total() <= 0:
                print("cap: the pilot's 20 CPU-hour total is spent; hunt stops")
                return 2
            if budget_cpu_s is not None and time.process_time() - began >= budget_cpu_s:
                print(
                    f"budget: {budget_cpu_s:.0f}s CPU for this invocation "
                    "is spent; hunt stops"
                )
                return 0
            _run_search(
                contexts,
                language=language,
                table=table,
                class_label=label,
                phase="hunt",
                eval_budget=eval_budget,
                restarts=restarts,
                seed=seed,
                wall_seconds=wall_seconds,
                checkpoint_dir=checkpoint_dir,
                resume=False,
                out_path=out_path,
                finds_path=finds_path,
                rejects_path=rejects_path,
                ledger=ledger,
                command="mine-hunt",
            )
    return 0
