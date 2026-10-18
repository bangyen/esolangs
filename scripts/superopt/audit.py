"""Small-end audit: shipped Boolean programs against certified minima.

For one language and one truth table, the audit asks only whether a
program *shorter than the shipped one* computes the table.  Candidates
are strings over the character set the language's own generator emits
(so every token sequence the generator could write is among them),
enumerated in increasing length.  A candidate counts only if it
reproduces the table on every row *and* consumes exactly the inputs
the shipped program consumes -- reading all inputs is part of a
generated program's contract (a caller downstream is handed what is
left), so a shorter text that ignores its input is not the same
artefact.  Consumption is enforced where the interpreter can be driven
through a scripted IO that counts reads; where it cannot, a gap is
recorded flagged as consumption-unverified, and a certificate is
unaffected either way (exhaustion covers the consuming programs too).

Execution is the repo's own: rows are answered through the public
``run``/``read_answer`` pair for printing languages, and through
``_iter_evaluate`` -- the generator tests' certification path -- for
the languages that answer by terminating.  Winners are re-certified
over the full table by a separate, no-early-exit evaluation before
they are recorded.
"""

from __future__ import annotations

import importlib
import signal
import time
from dataclasses import dataclass, field
from itertools import product

import esolangs
from esolangs.raster import Raster
from esolangs.registry import LANGUAGES, resolve
from esolangs.runtime._evaluate import _evaluate, _iter_evaluate
from esolangs.runtime._program import Program
from esolangs.runtime.io import ScriptedIO

#: Bounds on one row through the public runner: shipped programs at
#: these arities finish far inside them; a candidate past them is
#: treated as not answering.
_MAX_STEPS = 20_000
_ROW_TIMEOUT = 5.0
#: Per-row bound for termination-mode rows (the repo default is 5 s).
_TERM_TIMEOUT = 2.0
#: Wall guard on one scripted-IO consumption probe.
_ORACLE_TIMEOUT = 5.0


def tables(arity: int) -> tuple[str, ...]:
    """Every truth table of ``arity`` inputs, in counting order."""
    return tuple(format(c, f"0{2**arity}b") for c in range(2 ** (2**arity)))


def row_bits(row: int, n: int) -> list[int]:
    """A table row's input bits, most significant first."""
    return [row >> (n - 1 - i) & 1 for i in range(n)]


def discriminating_order(table: str) -> tuple[int, ...]:
    """Row indices by discriminating power, most discriminating first.

    Rows whose expected bit is rarer in the table come first (the v1
    rule for equality specs).  Heuristic only: it affects how soon a
    bad candidate dies, never the verdict.
    """
    counts = {bit: table.count(bit) for bit in "01"}
    return tuple(sorted(range(len(table)), key=lambda i: (counts[table[i]], i)))


class _OracleTimeoutError(Exception):
    """A consumption probe ran past its wall guard."""


def _alarm(_sig: int, _frame: object) -> None:
    raise _OracleTimeoutError


class Runner:
    """Answer rows of one language through the repo's own machinery."""

    def __init__(self, name: str) -> None:
        """Bind the language and its contract facts."""
        self.name = resolve(name)
        self.language = esolangs.Language(self.name)
        facts = LANGUAGES[self.name]
        self.parameterized = bool(facts.parameterized)
        self.terminating = facts.contract.answer_mode == "termination"
        self._module: object | None = None
        self._module_tried = False

    def answer_row(self, program: Program, bits: list[int]) -> str:
        """One row's answer bit for a printing language.

        Mirrors ``_row_answerer``: templates fill per row with empty
        stdin, plain programs read ``encode_inputs(bits)``.
        """
        source: Program = program
        stdin = esolangs.encode_inputs(self.name, bits)
        if self.parameterized:
            source = esolangs.instantiate(self.name, program, bits)
            stdin = ""
        out = esolangs.run(
            self.name,
            source,
            stdin=stdin,
            timeout=_ROW_TIMEOUT,
            max_steps=_MAX_STEPS,
        )
        return esolangs.read_answer(self.name, out)

    def check(self, program: str, table: str) -> tuple[bool, int]:
        """Early-exit verdict: (correct, rows actually evaluated).

        Printing languages check rows in discriminating order;
        termination languages stream ``_iter_evaluate`` in its counting
        order.  Order never changes the verdict.
        """
        n = len(table).bit_length() - 1
        if self.terminating:
            rows = 0
            try:
                answers = _iter_evaluate(
                    self.name, program, inputs=n, timeout=_TERM_TIMEOUT
                )
                for i, answer in enumerate(answers):
                    rows += 1
                    if answer != table[i]:
                        return False, rows
            except Exception:
                return False, rows
            return rows == len(table), rows
        rows = 0
        try:
            for i in discriminating_order(table):
                rows += 1
                if self.answer_row(program, row_bits(i, n)) != table[i]:
                    return False, rows
        except Exception:
            return False, rows
        return True, rows

    def certify(self, program: Program, table: str) -> bool:
        """Full-table re-verification, natural row order, no early exit.

        The separate check a search hit must pass before it is
        recorded; also how a shipped program is verified before its
        size is trusted as the bar.
        """
        n = len(table).bit_length() - 1
        try:
            if self.terminating:
                return (
                    _evaluate(self.name, program, inputs=n, timeout=_TERM_TIMEOUT)
                    == table
                )
            return all(
                self.answer_row(program, row_bits(i, n)) == table[i]
                for i in range(len(table))
            )
        except Exception:
            return False

    # The consumption oracle: drive the interpreter module through a
    # ScriptedIO that counts reads.  Best-effort -- where the module
    # cannot be driven this way (grid code forms, dialect entry
    # points), it reports None and gaps go in flagged instead.

    def _interpreter_module(self) -> object | None:
        if not self._module_tried:
            self._module_tried = True
            lang_id = LANGUAGES[self.name].id
            try:
                self._module = importlib.import_module(
                    f"esolangs.languages.{lang_id}.interpreter"
                )
            except Exception:
                self._module = None
        return self._module

    def reads(self, program: Program, table: str) -> tuple[int, ...] | None:
        """Per-row read counts of ``program``, or None if unmeasurable.

        The runnable source is the program itself, or per-row
        templates filled by instantiation.  A row that over-reads
        (past the supplied input) or raises settles the whole program
        as unmeasurable only when the failure is in the driving, not
        the program -- callers compare against the shipped baseline
        measured the same way, so a form mismatch shows up there too.
        """
        module = self._interpreter_module()
        if module is None or self.terminating:
            return None
        n = len(table).bit_length() - 1
        counts: list[int] = []
        signal.signal(signal.SIGALRM, _alarm)
        try:
            for i in range(len(table)):
                bits = row_bits(i, n)
                if self.parameterized:
                    source: object = esolangs.instantiate(self.name, program, bits)
                    stdin = ""
                else:
                    source, stdin = program, esolangs.encode_inputs(self.name, bits)
                counted = self._reads_one(module, source, stdin)
                if counted is None:
                    return None
                counts.append(counted)
        except Exception:
            return None
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
        return tuple(counts)

    @staticmethod
    def _reads_one(module: object, source: object, stdin: str) -> int | None:
        """Read count for one row, trying the text and row-list forms."""
        run = getattr(module, "run", None)
        if run is None:
            return None
        text = source if isinstance(source, str) else str(source)
        for code in (text, text.splitlines()):
            io = ScriptedIO(stdin)
            signal.setitimer(signal.ITIMER_REAL, _ORACLE_TIMEOUT)
            try:
                run(code, io)
            except _OracleTimeoutError:
                raise
            except Exception:
                continue
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)
            if io.past_end:
                return None
            return io.reads
        return None


@dataclass(frozen=True)
class Corpus:
    """A language's emitted character set and shipped sizes."""

    alphabet: tuple[str, ...]
    sizes: dict[int, dict[str, int]]
    corpus_arities: tuple[int, ...]


def corpus_for(name: str, *, arity3_size_cap: int = 2000) -> Corpus:
    """Collect the generator's emitted characters and shipped sizes.

    Corpus: every table of arity 1 and 2, plus every arity-3 table
    when the arity-2 worst size is small (a monster's arity-3
    emissions would swamp the collection for no vocabulary the small
    arities do not already show).  Characters are taken from programs
    under 20,000 chars; a language whose programs are all longer
    (Malbolge: 59,049) yields an empty alphabet and is out of scope.
    """
    lang = esolangs.Language(name)
    sizes: dict[int, dict[str, int]] = {}
    chars: set[str] = set()
    arities = [1, 2]
    for arity in arities:
        sizes[arity] = {}
        for table in tables(arity):
            try:
                program = lang.generate(table)
            except Exception:
                continue
            if isinstance(program, Raster):
                continue
            sizes[arity][table] = len(program)
            if len(program) < 20_000:
                chars |= set(str(program))
    if sizes.get(2) and max(sizes[2].values()) <= arity3_size_cap:
        sizes[3] = {}
        for table in tables(3):
            try:
                program = lang.generate(table)
            except Exception:
                continue
            if isinstance(program, Raster):
                continue
            sizes[3][table] = len(program)
            if len(program) < 20_000:
                chars |= set(str(program))
        arities.append(3)
    return Corpus(tuple(sorted(chars)), sizes, tuple(arities))


def approx(n: int) -> str:
    """A short magnitude for a candidate count too big to print exactly."""
    if n < 10**15:
        return f"{n:,}"
    return f"~1e{len(str(n)) - 1}"


def space_below(alphabet_size: int, size: int) -> int:
    """Candidate strings strictly shorter than ``size``."""
    if size <= 0:
        return 0
    if alphabet_size == 0:
        return 1
    if alphabet_size == 1:
        return size
    return int((alphabet_size**size - 1) // (alphabet_size - 1))


@dataclass
class Outcome:
    """One (language, table) audit verdict."""

    language: str
    table: str
    shipped_size: int
    outcome: str  # gap | certified | bounded | priced_out | unverifiable
    found: str | None = None
    candidates: int = 0
    rows: int = 0
    seconds: float = 0.0
    complete_length: int = -1
    space: int = 0
    note: str = ""


@dataclass
class _Search:
    runner: Runner
    table: str
    alphabet: tuple[str, ...]
    shipped_size: int
    baseline_reads: tuple[int, ...] | None
    candidate_cap: int | None
    wall_seconds: float
    candidates: int = 0
    rows: int = 0
    began: float = field(default_factory=time.monotonic)

    def over_budget(self) -> bool:
        """Whether the candidate cap or the wall budget is spent."""
        if self.candidate_cap is not None and self.candidates >= self.candidate_cap:
            return True
        return time.monotonic() - self.began > self.wall_seconds

    def run(self) -> Outcome:
        """Enumerate lengths below the shipped size, in order."""
        outcome = Outcome(
            language=self.runner.name,
            table=self.table,
            shipped_size=self.shipped_size,
            outcome="bounded",
            space=space_below(len(self.alphabet), self.shipped_size),
        )
        for length in range(self.shipped_size):
            for combo in product(self.alphabet, repeat=length):
                if self.candidates % 256 == 0 and self.over_budget():
                    return self._finish(outcome, complete=length - 1)
                candidate = "".join(combo)
                self.candidates += 1
                ok, rows = self.runner.check(candidate, self.table)
                self.rows += rows
                if not ok:
                    continue
                if self.baseline_reads is not None:
                    counted = self.runner.reads(candidate, self.table)
                    if counted != self.baseline_reads:
                        continue
                if self.runner.certify(candidate, self.table):
                    outcome.outcome = "gap"
                    outcome.found = candidate
                    return self._finish(outcome, complete=length - 1)
            outcome.complete_length = length
        outcome.outcome = "certified"
        return self._finish(outcome, complete=self.shipped_size - 1)

    def _finish(self, outcome: Outcome, *, complete: int) -> Outcome:
        outcome.candidates = self.candidates
        outcome.rows = self.rows
        outcome.seconds = time.monotonic() - self.began
        outcome.complete_length = complete
        if outcome.outcome == "bounded":
            if self.candidate_cap is not None and self.candidates >= self.candidate_cap:
                outcome.note = f"candidate cap {self.candidate_cap} reached"
            else:
                outcome.note = f"wall budget {self.wall_seconds:.0f}s reached"
        return outcome


def audit_pair(
    runner: Runner,
    corpus: Corpus,
    arity: int,
    table: str,
    *,
    candidate_cap: int | None,
    wall_seconds: float,
) -> Outcome:
    """Audit one (language, table): verify shipped, then search below it.

    The shipped program is certified first -- a pair whose shipped
    program does not evaluate to its table is a harness or runner
    problem, recorded ``unverifiable`` and never searched.
    """
    shipped_size = corpus.sizes[arity][table]
    lang = esolangs.Language(runner.name)
    try:
        shipped = lang.generate(table)
    except Exception as exc:
        return Outcome(
            runner.name,
            table,
            shipped_size,
            "unverifiable",
            note=f"generate raised {type(exc).__name__}",
        )
    if not runner.certify(shipped, table):
        return Outcome(
            runner.name,
            table,
            shipped_size,
            "unverifiable",
            note="shipped program does not evaluate to its table",
        )
    baseline = runner.reads(shipped, table)
    search = _Search(
        runner=runner,
        table=table,
        alphabet=corpus.alphabet,
        shipped_size=shipped_size,
        baseline_reads=baseline,
        candidate_cap=candidate_cap,
        wall_seconds=wall_seconds,
    )
    outcome = search.run()
    if baseline is None and outcome.outcome == "gap":
        outcome.note = "consumption unverified (no scripted-IO oracle)"
    return outcome


def audit_language(
    name: str,
    arity: int,
    *,
    candidate_cap: int | None,
    wall_seconds: float,
    bounded_multiple: int = 20,
) -> tuple[Corpus, list[Outcome]]:
    """Audit every table of one language at one arity.

    Pairs whose space exceeds ``bounded_multiple`` times the candidate
    cap are not run at all: ``priced_out``, with the space and the
    implied cost at the language's measured per-candidate rate in the
    note.  Cheaper pairs run cheapest-first.
    """
    corpus = corpus_for(name)
    runner = Runner(name)
    outcomes: list[Outcome] = []
    if not corpus.alphabet:
        for table in tables(arity):
            outcomes.append(
                Outcome(
                    runner.name,
                    table,
                    corpus.sizes[arity].get(table, -1),
                    "priced_out",
                    note="no alphabet extractable: every emitted program "
                    "is >= 20,000 chars",
                )
            )
        return corpus, outcomes
    pairs = sorted(
        tables(arity),
        key=lambda t: space_below(len(corpus.alphabet), corpus.sizes[arity].get(t, 0)),
    )
    for table in pairs:
        if table not in corpus.sizes[arity]:
            outcomes.append(
                Outcome(
                    runner.name,
                    table,
                    -1,
                    "unsupported",
                    note="generate produced no char-sized program at this "
                    "arity (a Raster, or a refusal)",
                )
            )
            continue
        space = space_below(len(corpus.alphabet), corpus.sizes[arity][table])
        if candidate_cap is not None and space > bounded_multiple * candidate_cap:
            outcomes.append(
                Outcome(
                    runner.name,
                    table,
                    corpus.sizes[arity][table],
                    "priced_out",
                    space=space,
                    note=f"space {approx(space)} strings below shipped size "
                    f"exceeds {bounded_multiple}x the candidate cap",
                )
            )
            continue
        outcomes.append(
            audit_pair(
                runner,
                corpus,
                arity,
                table,
                candidate_cap=candidate_cap,
                wall_seconds=wall_seconds,
            )
        )
    return corpus, outcomes


def audit_fleet(
    names: list[str],
    arity: int,
    *,
    budget_seconds: float,
    candidate_cap: int | None,
    wall_seconds: float,
) -> list[tuple[str, Corpus, list[Outcome]]]:
    """Audit languages cheapest-first until the global budget is spent.

    A pair not started because the budget ran out is recorded
    ``priced_out`` with that reason -- never silently skipped.  A
    single pair may overshoot the budget by at most its own wall
    bound.
    """
    began = time.monotonic()
    priced: list[tuple[str, Corpus, int]] = []
    for name in names:
        corpus = corpus_for(name)
        total = sum(
            space_below(len(corpus.alphabet), size)
            for size in corpus.sizes[arity].values()
        )
        priced.append((name, corpus, total))
    priced.sort(key=lambda item: item[2])
    results: list[tuple[str, Corpus, list[Outcome]]] = []
    for name, corpus, _total in priced:
        runner = Runner(name)
        outcomes: list[Outcome] = []
        for table in tables(arity):
            space = space_below(
                len(corpus.alphabet), corpus.sizes[arity].get(table, -1)
            )
            if table not in corpus.sizes[arity]:
                outcomes.append(
                    Outcome(
                        runner.name,
                        table,
                        -1,
                        "unsupported",
                        space=space,
                        note="generate produced no char-sized program at this "
                        "arity (a Raster, or a refusal)",
                    )
                )
            elif not corpus.alphabet:
                outcomes.append(
                    Outcome(
                        runner.name,
                        table,
                        corpus.sizes[arity].get(table, -1),
                        "priced_out",
                        space=space,
                        note="no alphabet extractable: every emitted program "
                        "is >= 20,000 chars",
                    )
                )
            elif time.monotonic() - began > budget_seconds:
                outcomes.append(
                    Outcome(
                        runner.name,
                        table,
                        corpus.sizes[arity][table],
                        "priced_out",
                        space=space,
                        note="global budget spent before this pair",
                    )
                )
            elif candidate_cap is not None and space > 20 * candidate_cap:
                outcomes.append(
                    Outcome(
                        runner.name,
                        table,
                        corpus.sizes[arity][table],
                        "priced_out",
                        space=space,
                        note=f"space {approx(space)} strings below shipped size "
                        "exceeds 20x the candidate cap",
                    )
                )
            else:
                outcomes.append(
                    audit_pair(
                        runner,
                        corpus,
                        arity,
                        table,
                        candidate_cap=candidate_cap,
                        wall_seconds=wall_seconds,
                    )
                )
        results.append((name, corpus, outcomes))
    return results
