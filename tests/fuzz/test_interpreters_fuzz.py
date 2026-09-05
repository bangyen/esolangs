"""Fuzz every interpreter, plus deeper alphabet fuzzing where it is safe.

Every registered interpreter runs a seeded set of mutations of two seeds --
its sample program and a generator-built one -- plus a hostile short source,
driven through a bounded VM.  The small ``FUZZ`` table adds unrestricted
alphabet fuzzing for languages whose random programs must terminate --
halting or rejecting -- rather than legitimately looping.

The corpus is seeded from the generators because the samples alone barely
reach an interpreter: a median of five characters, so a sweep over all 64
languages executed a median of twelve steps each and Container executed
nothing at all.  Adding generated seeds and drawing edits from each seed's
own alphabet multiplies executed steps by 3.9x and leaves no language at
zero.  A variant that outlives the step cap is then handed to cycle
detection, which *proves* the verdict for 44 of the 52 that reach it; the
remaining 8 are the unbounded-growth class and keep the SIGALRM backstop.
"""

import importlib
import os
import random
import re
import signal
import time
from collections.abc import Callable
from contextlib import suppress
from unittest.mock import patch

import pytest

from esolangs.exceptions import EsolangError
from esolangs.interpreters.io import IO
from esolangs.registry import LANGUAGES, RUNNERS
from esolangs.vm import make_vm, run_until_halt, run_until_halt_or_cycle
from tests.samples import SAMPLES

# interpreter module -> instruction alphabet; input is mocked below.
FUZZ = {
    "queue_based.bitdeque": "PUSHINJECTEJECTPOPINVERT",
    "register_based.minsky_swap": "+~*",
    "other.lamfunc": "p eq i cb lb fb vs vg F . x 0 1",
}

# ArrowQueue, back, Between, Jaune, Point Break, and RAM0 are
# not fuzzed here: they have unconditional, goto, or directional loops
# (Jaune's ?/! jumps, Point Break's POINT/END), so a random program may
# legitimately never terminate and the "terminates" invariant does not
# apply to them.


_HOSTILE = "!?+-*/[]{}()<>;:,. 01az\n"


def _generated_seed(language: str) -> str | None:
    """Return a generator-built program for ``language``, or ``None``.

    The mutation corpus used to be seeded from ``SAMPLES`` alone, and those
    programs are tiny: a median of five characters, with Container's the
    empty string.  Mutating five characters barely reaches an interpreter --
    a sweep over all 64 languages executed a median of twelve steps each,
    one step per variant, and Container executed nothing at all.

    Every registered language has a generator, and their output is the
    corpus this file was missing: text generators emit a median of 97
    characters.  Seeding from them multiplied executed steps by 3.7x, and
    4.0x together with the per-seed alphabet below.

    Generators are called exactly as ``test_fuzz_generators.py`` calls them
    -- a text generator takes the text to print, a boolean generator a
    truth-table string whose length implies the arity -- and the boolean
    fallback covers the seventeen languages with no text generator (2.4x
    there).  ``random.seed`` is set by the caller because some generators
    draw from the global RNG, and the suite runs under xdist.
    """
    language_data = LANGUAGES[language]
    generator = language_data.text
    if generator is not None:
        with suppress(Exception):
            return generator("a")
    boolean_generator = language_data.boolean
    if boolean_generator is not None:
        with suppress(Exception):
            return boolean_generator("0110")
    return None


def _mutate(
    seed: str, stdin: str, rng: random.Random, alphabet: str
) -> list[tuple[str, str]]:
    """Return four single-edit variants of ``seed``: inserts and deletions."""
    variants = []
    for _ in range(4):
        if not seed:
            variants.append((rng.choice(alphabet), stdin))
        elif rng.randrange(2):
            at = rng.randrange(len(seed) + 1)
            variants.append((seed[:at] + rng.choice(alphabet) + seed[at:], stdin))
        else:
            at = rng.randrange(len(seed))
            variants.append((seed[:at] + seed[at + 1 :], stdin))
    return variants


def _expired_at(deadline: float) -> Callable[[], bool]:
    """Return a ``stop`` predicate that is true once ``deadline`` passes.

    A named factory rather than an inline lambda so the deadline is bound
    per call instead of captured from the enclosing loop variable.
    """
    return lambda: time.monotonic() > deadline


#: Longest integer a mutated program may contain before the fuzzer skips it.
#:
#: Factor's program *is* an integer and ``make_vm`` factors it with sympy
#: before any step runs, so a mutation that turns a 60-digit factorable
#: number into a 62-digit semiprime costs unbounded, uninterruptible C time
#: -- ``scripts/verify_no_exception_leaks.py`` documents the same wedge and
#: bounds it with a subprocess kill.  A fuzz test cannot pay that, and the
#: fix that file suggests is this one: guard the digit length.  Twelve
#: digits factor instantly and still exercise every path that a longer
#: number would, since the interpreter's behaviour does not depend on the
#: operand's size.
_MAX_OPERAND_DIGITS = 12


def _affordable_variant(program: str) -> bool:
    """Return whether ``program`` is cheap enough to hand to ``make_vm``.

    Screens the program text rather than the language: any language whose
    program is a numeral pays this cost, and a name list would go stale.
    """
    return not any(
        len(run) > _MAX_OPERAND_DIGITS for run in re.findall(r"\d+", program)
    )


def _drives_cheaply(language: str, seed: str) -> bool:
    """Return whether ``seed`` runs its first steps fast enough to fuzz.

    A step is not a unit of work, and on Factor the work is not even in a
    step: its generated program is a 60-odd-digit semiprime, and the
    interpreter hands that to ``sympy.factorint`` while *constructing* the
    machine.  Factoring a semiprime that size does not finish, so the cost
    is paid inside ``make_vm`` before a step budget exists -- which is why
    neither a step cap nor a deadline checked between steps bounds it.
    Polynomial's 8th-degree seed factors the same way.

    So cost is screened before the seed joins the corpus rather than bounded
    during it, and the screen times construction as well as a short driven
    prefix.  It screens by measured cost rather than by a list of slow
    languages, because a list would go stale the moment a generator changed.

    The screen cannot be made airtight, and the repo already knows why:
    ``scripts/verify_no_exception_leaks.py`` records that a SIGALRM cannot
    land inside sympy's uninterruptible C, so bounding Factor there needed
    a subprocess with a hard kill -- far too heavy for a unit test.  The
    cheap half of its own suggested remedy, "a digit-length guard on
    Factor's mutants", is what :func:`_affordable_variant` applies below:
    keep the operand small enough that factoring it is never the cost.
    """
    if not _affordable_variant(seed):
        return False
    deadline = time.monotonic() + 1.0
    try:
        vm = make_vm(language, seed, "")
    except (EsolangError, ValueError, EOFError, SystemExit):
        return False
    if time.monotonic() > deadline:
        return False  # construction alone blew the budget (Factor, Polynomial)
    with suppress(EsolangError, ValueError, EOFError, SystemExit):
        run_until_halt(vm, limit=8, stop=lambda: time.monotonic() > deadline)
    return time.monotonic() <= deadline


def _mutated_sources(language: str) -> list[tuple[str, str]]:
    """Return short hostile variants of ``language``'s programs.

    Every interpreter gets this fuzzer, including languages with generators:
    generated programs cover the intended language, while these edits
    exercise parser and runtime boundaries that generation cannot produce.

    Two seed families, because they reach different code.  The sample is the
    only one carrying stdin, so it keeps the input-reading paths; the
    generated program is long enough for an edit to land somewhere other
    than the first instruction.  Inserts are drawn from the seed's own
    characters -- a generic pool was rejected at the parser by 102 of 384
    variants, never reaching the interpreter -- but one variant of each
    family still inserts from :data:`_HOSTILE`, since a character the
    language does not define is exactly the parser boundary a generator
    cannot produce.
    """
    program, stdin = SAMPLES[language]
    rng = random.Random(sum(map(ord, language)))
    variants = [(program, stdin)]
    variants += _mutate(program, stdin, rng, _HOSTILE)

    # Some generators draw from the global RNG; seed it so xdist workers and
    # reruns build the same corpus.
    random.seed(sum(map(ord, language)))
    seed = _generated_seed(language)
    if seed is not None and _drives_cheaply(language, seed):
        variants.append((seed, ""))
        variants += _mutate(seed, "", rng, "".join(sorted(set(seed))) or _HOSTILE)
        variants += _mutate(seed, "", rng, _HOSTILE)[:1]

    variants.append(("".join(rng.choice(_HOSTILE) for _ in range(12)), ""))
    return variants


@pytest.mark.parametrize("language", sorted(RUNNERS))
def test_every_interpreter_fuzzes_mutated_sources(language: str) -> None:
    """Fuzz every registered interpreter through bounded VM execution.

    A variant still running at the step cap used to end the check there,
    which reports nothing: a truncated run and a hung one look identical.
    Where the cap is reached, cycle detection re-runs the variant and
    usually *proves* the verdict instead -- of the 52 variants that reach
    the cap, 44 are provably non-halting rather than merely unfinished.

    The remaining 8 are the unbounded-growth class, which no cycle
    detector can catch (A Painter Ant's paint grows monotonically, so its
    state never repeats; AddSubJump and Suffolk are the others) and which
    ``run_until_halt_or_growth`` cannot decide either, since that
    certificate is tape-shaped.  They keep the
    SIGALRM backstop this file already uses, rather than an exemption list
    naming them -- a hardcoded list of exempt languages is how this suite
    silently lost twelve interpreters once before.
    """
    for program, stdin in _mutated_sources(language):
        if not _affordable_variant(program):
            continue  # a numeral too long to factor; see _MAX_OPERAND_DIGITS
        try:
            vm = make_vm(language, program, stdin)
            # A step is not a unit of time.  Factor's generated seed is a
            # 67-digit number and Polynomial's an 8th-degree polynomial, so
            # a hundred *steps* of either is minutes of arithmetic.  The
            # budget is what bounds the fuzzer, so it is spent in seconds
            # as well as steps, and a variant that runs out of either is
            # simply one the fuzzer stops driving -- not a failure.
            deadline = time.monotonic() + 0.5
            if run_until_halt(vm, limit=100, stop=_expired_at(deadline)):
                continue
            if time.monotonic() > deadline:
                continue  # out of time, not proven stuck: nothing to decide
            if os.name != "posix":
                continue  # signal.alarm is POSIX-only; the cap stands alone
            # Still going at the cap: try to decide it on a fresh machine.
            # Brent's detector is unbounded, so the alarm bounds it.
            old_handler = signal.signal(signal.SIGALRM, _on_alarm)
            signal.alarm(1)
            try:
                run_until_halt_or_cycle(make_vm(language, program, stdin))
            except _TimeoutError:
                pass  # undecided: the growth class, not a failure
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)
        except (EsolangError, ValueError, EOFError, SystemExit):
            pass  # rejection and exhausted input are documented outcomes


class _TimeoutError(Exception):
    """Raised by the alarm handler when a random program does not terminate."""


def _on_alarm(_signum: int, _frame: object) -> None:
    raise _TimeoutError("interpreter did not terminate on a random program")


@pytest.mark.skipif(os.name != "posix", reason="signal.alarm is POSIX-only")
@pytest.mark.parametrize("module", sorted(FUZZ))
def test_random_programs_terminate(module: str) -> None:
    random.seed(sum(map(ord, module)))
    alphabet = FUZZ[module]
    run = importlib.import_module("esolangs.interpreters." + module).run
    old_handler = signal.signal(signal.SIGALRM, _on_alarm)
    try:
        for _ in range(25):
            program = "".join(
                random.choice(alphabet) for _ in range(random.randint(1, 24))
            )
            signal.alarm(3)
            try:
                with patch("builtins.input", return_value="0"):
                    run(program, io=IO())
            except _TimeoutError:
                pytest.fail(f"{module} hung on a random program")
            except Exception:
                pass  # rejecting a random program is a valid termination
            finally:
                signal.alarm(0)
    finally:
        signal.signal(signal.SIGALRM, old_handler)
