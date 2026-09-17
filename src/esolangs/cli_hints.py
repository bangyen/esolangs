"""What the CLI says when something is wrong, and how it judges an answer.

The hints are the difference between a tool that refuses and one that says
why: a template mistaken for a program, a truth table in the file slot, an
input whose alphabet the language does not spell.  Each is a pure function of
what was seen, so none of them can decide anything.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from difflib import get_close_matches

from esolangs import LanguageInfo, _terminates, check_stdin
from esolangs.exceptions import EsolangError, ExecutionTimeoutError, TemplateError
from esolangs.registry import SUGGESTION_CUTOFF

# A watched cell's history longer than this is printed abridged: the whole
# thing was one line of 486 comma-separated values for a 486-step program,
# which buries the ends that are actually read.
_HISTORY_SHOWN = 40


#: A run stopped by its ``--timeout``, following timeout(1).  Distinct from
#: a program error's 1, which it shared: for the three languages that answer
#: by not terminating, the timeout is the *answer*, and a script had no way
#: to tell that from the program having broken.
_TIMEOUT_EXIT = 124


def _exit_code(exc: EsolangError) -> int:
    """Return the exit code ``exc`` should leave behind.

    Derived rather than written at each site, because it was written at
    each site: ``run`` and ``debug`` exited 124 on a bound running out and
    ``evaluate``, ``verify`` and ``answer`` exited 1 on the same event, so
    a script could not use one code to mean "the bound ran out".  The
    124 is the only exit code this CLI documents a meaning for, in ``run
    --help``, and three of the five commands did not honour it.

    A ``ValueError`` is misuse and stays 2; everything else is 1.
    """
    if isinstance(exc, ExecutionTimeoutError):
        return _TIMEOUT_EXIT
    return 2 if isinstance(exc, ValueError) else 1


#: The two input shapes whose bit count cannot be recovered from stdin.
#: Every other language reads a line per bit, so a run can compare what it
#: took against what it was given; these two read a single line -- all the
#: bits at once, or a row index -- and a wrong count is indistinguishable
#: from a right one without knowing the arity.
_UNCOUNTABLE_SHAPES = ("one_line", "row_index")


def _template_hint(exc: TemplateError, language: str) -> str:
    """Re-point a template refusal at the CLI flag that fills the slots.

    The library's message names ``esolangs.instantiate(...)``, which is the
    right answer for a Python caller and a dead end for someone who has
    only ever typed ``esolangs``.
    """
    message = str(exc)
    pointer = "fill them with esolangs.instantiate("
    if pointer not in message:
        return message
    head = message.split(pointer)[0]
    return (
        f"{head}fill them with: esolangs generate --bits <bits> "
        f"{_as_argument(language)} <table>"
    )


def _shell_hint(message: str, language: str) -> str:
    """Re-point ``encode``'s refusal at the flag that does the same job.

    Same problem as :func:`_template_hint` and the sibling it was written
    for: ``encode Minifuck 10`` was answered with "pass the bits to
    instantiate() instead", and ``instantiate()`` is not a thing you can
    type at a shell.  The flag that embeds bits is ``generate --bits``.
    """
    pointer = "pass the bits to instantiate() instead"
    if pointer not in message:
        return message
    head = message.split(pointer)[0]
    return (
        f"{head}embed them in the program instead: "
        f"esolangs generate --bits <bits> {_as_argument(language)} <table>"
    )


def _looks_like_a_table(value: str) -> bool:
    """Whether ``value`` is a power-of-two run of 0s and 1s."""
    if not value or set(value) - {"0", "1"}:
        return False
    n = len(value).bit_length() - 1
    return len(value) == 2**n and n >= 1


def _swapped_hint(language: str, table: str) -> str:
    """Return a hint when the language and truth-table arguments look swapped.

    ``generate 0110 brainfuck`` was answered with "unknown language: 0110",
    which is true and unhelpful: a power-of-two run of 0s and 1s in the
    language slot is a swap, not a language nobody has implemented.
    """
    looks_like_table = bool(language) and not set(language) - {"0", "1"}
    if not looks_like_table:
        return ""
    n = len(language).bit_length() - 1
    if len(language) != 2**n or n < 1:
        return ""
    return (
        f"; {language!r} looks like a truth table -- the language comes "
        f"first: esolangs generate {table} {language}"
    )


def _did_you_mean(word: str, known: Iterable[str]) -> str:
    """Return a ``did you mean`` clause for ``word``, or an empty string.

    Language names have had suggestions for a while and option names had
    none, so ``--wdith 40`` was a flat "unknown option" while ``Brainfck``
    got helped.  Same cutoff as :func:`esolangs.registry.resolve` uses.
    """
    close = get_close_matches(word, sorted(known), n=2, cutoff=SUGGESTION_CUTOFF)
    if not close:
        return ""
    return f"; did you mean {' or '.join(close)}?"


def _abridge(history: Sequence[object]) -> str:
    """Render a watch history, eliding the middle of a long one."""
    if len(history) <= _HISTORY_SHOWN:
        return str(history)
    head = ", ".join(str(v) for v in history[: _HISTORY_SHOWN // 2])
    tail = ", ".join(str(v) for v in history[-_HISTORY_SHOWN // 2 :])
    return f"[{head}, ... {len(history) - _HISTORY_SHOWN} more ..., {tail}]"


def _shape_warning(facts: LanguageInfo, stdin: str, table: str | None = None) -> str:
    """Return the library's complaint about ``stdin``, or ``''``.

    The checks themselves live in :func:`esolangs.check_stdin` now.  They
    were written here, and a Python caller had no way to reach them -- the
    one place the API was weaker than this command line, and the guards in
    question are the ones every reader of this package trips over.  Two
    copies would have drifted, as two copies of a check in this repository
    have twice before.
    """
    if not facts["reads_input"]:
        return ""
    try:
        check_stdin(str(facts["name"]), stdin, table)
    except EsolangError as exc:
        # Some of these already name the exact command; appending the
        # generic pointer to those said "esolangs encode" twice in one line.
        tail = (
            ""
            if "esolangs encode" in str(exc)
            else ("; `esolangs encode` builds the right stdin")
        )
        return f"{exc}{tail}"
    return ""


def _decode_note(exc: UnicodeDecodeError) -> str:
    """Describe where a decode failed, without the codec's full sentence."""
    return f"invalid UTF-8 at byte {exc.start}"


def _stdin_hint(facts: LanguageInfo) -> str:
    """Return a clause naming what this language wants on stdin, if anything.

    A language whose generator embeds its inputs usually wants nothing, and
    saying so is most of the help: the reader who typed `esolangs run RAM0
    prog.txt` and watched it wait was waiting for input the program was
    never going to ask for.

    *Usually*, not always -- the flag says the generated program reads no
    stdin, and three of those seventeen languages have an input command a
    hand-written program may still use.  So this suggests and does not
    skip.
    """
    if not facts["reads_input"] and facts["parameterized"]:
        return (
            f"; {facts['name']}'s generated programs embed their inputs and "
            f"read no stdin, so there is probably nothing to send -- close it"
        )
    return "; try: esolangs encode <language> <bits> | ..."

    # No note about ``--table`` here.  The first draft printed one whenever
    # it was absent, which is every call that is simply checking a shape --
    # advice on correct input, which is the thing this CLI has spent several
    # rounds removing.  ``check-stdin --help`` says what the flag adds.


def _input_sentence(facts: LanguageInfo) -> str:
    """Describe this language's stdin in one line, with an example.

    Composed from ``input_shape`` and ``input_encoding`` rather than stored,
    so a language that declares a new shape is described by declaring it.
    """
    zero, one = facts["input_encoding"]
    shape = str(facts["input_shape"])
    example = f"{one}{zero}"
    if shape == "row_index":
        return 'one decimal row index, e.g. "2" for the bits 10'
    if shape == "one_line":
        return f'every bit on one line, e.g. "{example}"'
    lines = f"{one}\\n{zero}"
    if shape == "line_per_bit_padded":
        return (
            f'one line per bit, e.g. "{lines}" -- and an odd count above one '
            f"is padded with a leading {zero} line"
        )
    return f'one line per bit, e.g. "{lines}"'


def _diverging_answer(
    name: str, source: str, stdin: str, bound: float, facts: LanguageInfo
) -> str:
    """Return the answer bit for a language that answers by terminating.

    By *proof* rather than by waiting.  This used to run the row under the
    bound and read a timeout as the 1 -- so ``answer --timeout 20`` on a
    1-row took twenty seconds, and raising the bound made it strictly
    slower, which is the opposite of what a bound should mean.  ``verify``
    settles four rows of the same language in a fifth of a second because
    it uses the repeated-state proof; ``answer --help`` calls itself
    "``verify`` for one row" and was the one place the proof had not
    reached.

    The clock stays as the backstop it was always meant to be: a loop that
    grows without bound never repeats a state, so it still has to be timed
    out.
    """
    encoding = facts["answer_encoding"]
    return _terminates(
        name,
        source,
        stdin,
        bound,
        str(encoding.index("halts")),
        str(encoding.index("diverges")),
    )


def _as_argument(language: str) -> str:
    """Return ``language`` spelled the way a shell needs it.

    Twelve of the 65 names contain a space, and the package prints
    commands containing them -- ``describe`` ends with ``esolangs describe
    --spec A Painter Ant``, and the template hint offers ``esolangs
    generate --bits <bits> A Painter Ant <table>``.  Copy-pasting either
    gives ``unexpected argument: 'Painter'``, so the tool was emitting
    commands it cannot itself parse.
    """
    return f'"{language}"' if " " in language else language
