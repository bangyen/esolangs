"""The CLI's own help text: the usage line and the per-command pages.

Kept apart from the code it describes because it is the largest thing in the
interface and the least like the rest of it -- prose that ``--help`` prints
verbatim. Capability-specific examples follow the current registry.
"""

from __future__ import annotations

import shlex

from esolangs.cli.hints import _as_argument
from esolangs.registry import Catalog, SourceKind, get_catalog
from esolangs.runtime._json import record_dumps
from esolangs.runtime.memory import repr_value
from esolangs.runtime.source_hints import can_render_argument, display_label


def _capability_examples(
    catalog: Catalog | None = None, *, encoding: str = "utf-8"
) -> tuple[str, str]:
    """Return supported template and dialect commands, or empty examples."""
    templates = ""
    dialects = ""
    catalog = get_catalog(catalog)
    for name, lang in sorted(catalog.languages.items()):
        if templates and dialects:
            break
        schema = lang.runtime.dialect_schema
        needs_dialect = not dialects and schema is not None
        if lang.runtime.source_kind is not SourceKind.TEXT or (
            templates and not needs_dialect
        ):
            continue
        quoted = _as_argument(name, catalog=catalog, encoding=encoding)
        if quoted is None:
            continue
        backend = lang.backend
        if backend is None or (
            backend.max_inputs is not None and backend.max_inputs < 2
        ):
            continue
        if not templates and backend.template is not None:
            templates = f"  esolangs generate --bits 10 {quoted} 0110"
        if not dialects and schema is not None:
            for key, values in sorted(schema.choices.items()):
                value = values[-1]
                settings = shlex.quote(record_dumps({key: value}))
                operand = repr_value(value) if isinstance(value, int) else value
                setting = shlex.quote(f"{key}={operand}")
                dialects = f"  esolangs generate --settings {settings} {quoted} 0110"
                if can_render_argument(setting, encoding):
                    dialects += f"\n  esolangs generate --set {setting} {quoted} 0110"
                break
    return templates, dialects


_TERMINATION_HELP = """The languages that answer by terminating are {names}.
{meaning}
Program output carries no answer. Use `esolangs run --execution-timeout S`
and observe whether it halts. A timeout leaves the answer undecided."""

USAGE = """usage: esolangs <command> [...]

commands:
  Generator-made (the API invents source from a truth table):
    generate [--width [N] | --balance] [--bits BITS] [--scale N]
             [--settings JSON] [--set KEY=VALUE] [--plain | --gzip]
             <language> <truth-table>
                                print a program computing a truth table
                                (--width wraps it; --bits fills a template)
  Caller-supplied (you supply the program):
    run [--execution-timeout S] [--total-timeout S] [--preparation-timeout S]
        [--isolated] [--max-output N] [--max-memory BYTES] [--max-steps N]
        [--seed N] [--scale N] [--settings JSON] [--set KEY=VALUE]
        <language> <file>
                                run a program through its interpreter
  Contract adapters (your data in, checked data out):
    encode-inputs <language> <bits>
                                print the stdin that feeds those bits
    read-answer <language>      read a program's output on stdin and print
                                the answer bit it carries
  Catalog:
    list [--details] [--json] [--generator | --interpreter-only]
         [--grep REGEX] [--source-kind KIND] [--input-shape SHAPE]
         [--answer-mode MODE] [--inputs N [--all-tables]]
                                list languages matching their capabilities
    describe [--json] [--spec] <language>
                                print how that language reads its input and
                                where it puts the answer (--spec prints the
                                interpreter's own description of it)

Language names are case-insensitive.  `esolangs <command> --help` (-h)
describes one command in full; `--version` (-V) prints the version.  -s is
short for --settings.  A truth table is 2^n bits, most significant first; its
length sets the input count (0110 is two-input XOR).

exit codes: 0 success, 1 the program broke, 2 the ask was wrong, 70 internal
error (a bug in esolangs), 120 stdout unavailable, 124 a budget ran out
(time, steps, output, memory), 130 interrupted.

examples:
  esolangs list
  esolangs describe brainfuck
  esolangs encode-inputs brainfuck 10
  esolangs generate brainfuck 0110 > prog.txt
  esolangs generate --width brainfuck 10010110
  esolangs encode-inputs brainfuck 10 | esolangs run brainfuck prog.txt \\
    | esolangs read-answer brainfuck
"""


_HELP = {
    "encode-inputs": """usage: esolangs encode-inputs <language> <bits>

Print the stdin that feeds <bits> to a <language> program, so it can be
piped straight into `esolangs run`:

    esolangs encode-inputs brainfuck 101 | esolangs run brainfuck prog.txt

Character readers take adjacent 0/1 characters. Numeric readers take
whitespace-delimited tokens; string readers take lines. Other contracts
use a different alphabet, a row index, or padded input.
`esolangs describe <language>` prints the encoding.

Some generators embed the bits in source using `esolangs generate --bits`.
Those programs need no stdin for their input bits. Handwritten programs
follow the interpreter's input rules.

example:
  esolangs encode-inputs brainfuck 10  # prints 10
""",
    "list": """usage: esolangs list [--details] [--json]
                     [--generator | --interpreter-only] [--grep REGEX]
                     [--source-kind KIND] [--input-shape SHAPE]
                     [--answer-mode MODE] [--inputs N [--all-tables]]

List matching languages, one per line, well-known first (`--json` keeps
the Python API's name order). Filters combine with AND; filter on
other facts with `list --json --details | jq`.

options:
  --details   add a marker column per language:
                gen    has a boolean generator
                tmpl   that generator returns a template rather than a
                       runnable program -- see `esolangs generate --help`
                ex     a committed program beside its language modules
                int    interpreter-only: a classic kept for coverage, with
                       no generator, so `generate` refuses it
                known  well-known: at least 50 esolangs wiki backlinks
              then `max-inputs=N` and any table-dependent restriction
  --json      print a JSON array: names, or capability records with --details
  --generator restrict to languages with a Boolean generator
  --interpreter-only restrict to languages without a Boolean generator
  --source-kind KIND
              text or raster
  --input-shape SHAPE
              Boolean input shape: line_per_bit, char_stream,
              char_stream_cyclic, row_index, row_number, or template
              (generated programs embed their input bits in source)
  --answer-mode MODE
              output, dump, or termination
  --inputs N  generators whose declared cap permits N inputs (N >= 1);
              table-dependent restrictions can still refuse generation
  --all-tables
              with --inputs, require support for every table at that arity
  --grep REGEX
              select languages whose spec (`describe --spec`) matches,
              case-insensitively

examples:
  esolangs list --generator --details
  esolangs list --source-kind text --input-shape char_stream --answer-mode output
  esolangs list --inputs 8 --details
  esolangs list --json --details | jq -r '.[]|select(.generator_shape=="lookup").name'
""",
    "generate": """usage: esolangs generate [--width [N] | --balance] [--bits BITS]
                         [--scale N] [--settings JSON] [--set KEY=VALUE]
                         [--plain | --gzip] <language> <truth-table>

Print a program in <language> computing <truth-table>.

The table is a binary string of length 2**n indexed by the inputs, most
significant first, so its length sets the input count: 0110 is two-input
XOR, 10010110 is three-input.  Use - for <truth-table> to read it from
stdin as UTF-8 through EOF, ignoring surrounding whitespace.

`esolangs describe <language>` shows how the program takes inputs and
prints the result.

Some generators embed the inputs in source. They return a *template* with
one placeholder run per input, as long as its replacement. Fill the template
before running it through the Python API. The CLI prints literal source,
which `esolangs run` interprets as written. `esolangs list --details` marks
these generators `tmpl`. Pass --bits to print the filled program.

For text and gzip output, repeat non-default --settings or --set options on
`esolangs run`. PNG files carry their dialect settings.

options:
  --bits BITS  fill a template's input slots with these bits, one character
               per input, and print the runnable program.  Substituting them
               by hand does not work: each language spells a set-input its
               own way, and a 0/1 in the slot is a different program.
  --scale N    enlarge raster pixels by N after layout (default 1).
  -s, --settings JSON
               dialect overrides; describe lists supported settings.
  --set KEY=VALUE
               one dialect override without JSON, repeatable and applied
               after --settings. The last value for each key wins.
  --plain      export compressed text as ordinary source text.  Without it,
               compressed text is written as gzip.  A raster is always PNG
               -- binary bytes, so redirect it to a file.
  --gzip       export any text program as gzip; excludes --plain.
               Raster programs retain PNG and reject this option.
  --balance    pick the layout fitting the smallest on-screen square: text
               minimizes max(columns, 2 * rows) (a cell is about twice as
               tall as wide), a raster max(width, height). Ties prefer shorter
               source, then smaller width; excludes --width.
  --width [N]  wrap the program to N columns (default {DEFAULT_WIDTH}) so it
               is readable in a diff.  Breaks only between whole tokens.
               `esolangs describe <language>` reports which of three
               things it does, as `width_effect`: `wrap` reflows the
               finished program between whole tokens, `layout` hands the
               width to the generator as a *hint*, so routing may exceed
               the requested width, and `none` ignores it. A template
               wraps with each input's run kept whole, so every
               row it fills to has the same breaks; a layout language lays
               it out instead. If --width has no integer operand, it uses
               the default. Use --width=N to make the value explicit.

examples:
  esolangs generate brainfuck 0110
{_TEMPLATE_EXAMPLE}
{_DIALECT_EXAMPLES}
""",
    "run": """usage: esolangs run [--execution-timeout S] [--total-timeout S]
                    [--preparation-timeout S] [--isolated] [--max-output N]
                    [--max-memory BYTES] [--max-steps N] [--seed N]
                    [--scale N] [--settings JSON] [--set KEY=VALUE]
                    <language> <program-file>

Run a program through its interpreter and print what it writes.

Use - as <program-file> to read source from stdin for interpreters that
take no runtime input. Use ./- for a file named -.
Interpreters with input support receive piped stdin as UTF-8, read through
EOF. They consume it verbatim using the language's character, number, or
string reads.
For generated Boolean programs, `esolangs encode-inputs` spells the input
characters, numeric tokens, or lines.

    esolangs encode-inputs brainfuck 101 | esolangs run brainfuck prog.txt

For generated text and gzip, repeat the non-default --settings or --set
options used with `esolangs generate`. PNG files carry their dialect settings.

Piped output is written verbatim as UTF-8. A trailing newline is added
only when stdout is a terminal. Partial output is written before the error
on stderr. Text containing a surrogate cannot be sent to a pipe as UTF-8.

exit codes: 0 ran, 1 the program broke or its output cannot be encoded,
2 the ask was wrong (unknown language, malformed program, unreadable file),
70 internal error (a bug in esolangs), 120 stdout unavailable, 124 a budget
ran out (time, steps, output, memory), 130 interrupted.

options:
  --isolated         run in a subprocess. The default total is 30 seconds
                     plus any --execution-timeout.
  --max-output N     cap output in Unicode characters (including zero); implies
                     --isolated.
  --max-memory BYTES cap worker address space (Linux only); implies --isolated.
  --max-steps N      bound commands cooperatively; combines with isolation and seed.
  --execution-timeout SECONDS
                     bound acquisition and execution separately. Worker
                     startup uses the total and preparation deadlines.
  --total-timeout SECONDS
                     bound acquisition, worker startup, preparation, and execution.
                     The CLI delivers output to stdout afterward.
  --preparation-timeout SECONDS
                     bound acquisition, worker startup, and preparation.
  --scale N          override detected raster scale; 1 preserves native pixels.
  -s, --settings JSON    dialect overrides; describe lists supported settings.
  --set KEY=VALUE    one dialect override without JSON, repeatable and applied
                     after --settings. The last value for each key wins.
  --seed N           fix the random draws so the run repeats.  `esolangs
                     describe --json <language>` reports `random` for the
                     languages that draw.  A seed for a language that draws
                     nothing is refused rather than ignored.
examples:
  printf '10' | esolangs run brainfuck prog.txt
  printf '10' | esolangs run --execution-timeout 5 brainfuck prog.txt
""",
    "describe": """usage: esolangs describe [--json] [--spec] <language>

Print what a language does with its input bits and where it puts the answer.

The default layout is contract-first: how the bits go in, where the answer
comes out, whether a truth-table generator exists and whether it embeds the
bits (`--bits`) or reads them from stdin, and any dialect choices.  A details
section follows with the fields that decide how to drive a generated
program.  This exists because those facts decided every wrong answer anyone
got out of this tool, and the only place they were readable was a Python
session.

options:
  --spec      print the interpreter's own description of the language: its
              command table, and where this implementation differs from the
              wiki page.  Every language carries one, they run to a
              few thousand characters, and they are the best documentation
              here for *writing* a program rather than generating one.
              With --json, the spec as one JSON string.
  --json      print `esolangs.describe` verbatim as JSON: every key the
              Python API returns, including the full spec text, dialect
              settings and example paths that the default layout
              summarizes or omits.

examples:
  esolangs describe brainfuck
  esolangs describe --json brainfuck
  esolangs describe --spec brainfuck
""",
    "read-answer": """usage: esolangs read-answer <language>

Read a program's output on stdin through EOF and print the answer bit it
carries. At a terminal, paste the output and send EOF when done.

For most languages the answer is the last thing printed and this is barely
more than `tail`.  For some it is not: several dump their entire final machine
state, and the answer sits in a tagged memory value or the current marked
cell. `esolangs describe <language>` reports the answer convention.

{_TERMINATION_HELP}

examples:
  esolangs generate brainfuck 0110 > p.txt
  esolangs encode-inputs brainfuck 10 | esolangs run brainfuck p.txt \\
    | esolangs read-answer brainfuck
""",
}


COMMANDS = tuple(_HELP)


def command_synopsis(command: str) -> str:
    """Return the usage line or lines without resolving examples."""
    return _HELP[command].split("\n\n", 1)[0]


def help_text(
    command: str, *, catalog: Catalog | None = None, encoding: str = "utf-8"
) -> str:
    """Render one command's help, loading synthesis for generation help."""
    text = _HELP[command]
    if command == "generate":
        from esolangs.generation.wrap import DEFAULT_WIDTH

        template, dialects = _capability_examples(catalog, encoding=encoding)
        text = text.format(
            DEFAULT_WIDTH=DEFAULT_WIDTH,
            _TEMPLATE_EXAMPLE=template,
            _DIALECT_EXAMPLES=dialects,
        )
    elif command == "read-answer":
        terminating = {
            name: lang.contract.answer_values
            for name, lang in sorted(get_catalog(catalog).languages.items())
            if lang.contract.answer_mode == "termination"
        }
        if not terminating:
            return text.replace("{_TERMINATION_HELP}\n\n", "")
        meaning = (
            "For their generated programs, halting means 0 and divergence means 1."
            if all(bits == ("halts", "diverges") for bits in terminating.values())
            else "`esolangs describe <language>` reports what its termination means."
        )
        text = text.replace(
            "{_TERMINATION_HELP}",
            _TERMINATION_HELP.format(
                names=", ".join(map(display_label, terminating)), meaning=meaning
            ),
        )
    return text
