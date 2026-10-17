"""The CLI's own help text: the usage line and the per-command pages.

Kept apart from the code it describes because it is the largest thing in the
interface and the least like the rest of it -- prose that ``--help`` prints
verbatim. Capability-specific examples follow the current registry.
"""

from __future__ import annotations

import json
import shlex

from esolangs.generation.wrap import DEFAULT_WIDTH
from esolangs.registry import LANGUAGES, SourceKind


def _capability_examples() -> tuple[str, str]:
    """Return supported template and dialect commands, or empty examples."""
    templates = ""
    dialects = ""
    for name, lang in sorted(LANGUAGES.items()):
        if lang.boolean is None or lang.source_kind is not SourceKind.TEXT:
            continue
        if lang.generator_max_inputs is not None and lang.generator_max_inputs < 2:
            continue
        quoted = shlex.quote(name)
        if not templates and lang.parameterized:
            templates = f"  esolangs generate --bits 10 {quoted} 0110"
        if not dialects and lang.dialect_values:
            for key, values in sorted(lang.dialect_values.items()):
                if not values:
                    continue
                settings = shlex.quote(
                    json.dumps({key: values[-1]}, separators=(",", ":"))
                )
                setting = shlex.quote(f"{key}={values[-1]}")
                dialects = (
                    f"  esolangs generate --settings {settings} {quoted} 0110\n"
                    f"  esolangs generate --set {setting} {quoted} 0110"
                )
                break
    return templates, dialects


_TEMPLATE_EXAMPLE, _DIALECT_EXAMPLES = _capability_examples()
_TERMINATION_NAMES = ", ".join(
    name
    for name, lang in sorted(LANGUAGES.items())
    if lang.contract.answer_mode == "termination"
)

USAGE = f"""usage: esolangs <command> [...]

commands:
  Generator-made (the API invents source from a truth table):
    generate [--width [N] | --balance] [--bits BITS] [--scale N]
             [--settings JSON] [--set KEY=VALUE] [--plain]
             <language> <truth-table>
                                print a program computing a truth table
                                (--width wraps it; --bits fills a template)
  Caller-supplied (you supply the program):
    run [--timeout S] [--isolated] [--max-output N] [--max-memory BYTES]
        [--seed N] [--scale N] [--settings JSON]
        [--set KEY=VALUE] <language> <file>
                                run a program through its interpreter
  Contract adapters (your data in, checked data out):
    encode <language> <bits>    print the stdin that feeds those bits
    read-answer <language>      read a program's output on stdin and print
                                the answer bit it carries
  Catalog:
    list [--details] [--json] [--generator | --interpreter-only]
         [--grep REGEX]
                                list languages matching their capabilities
    describe [--json] [--spec] <language>
                                print how that language reads its input and
                                where it puts the answer (--spec prints the
                                interpreter's own description of it)

Language names are case-insensitive.  `esolangs <command> --help` describes
one command in full; `--version` prints the version.  -s is short for
--settings.  A truth table is 2^n bits, most significant first; its length
sets the input count (0110 is two-input XOR).

exit codes: 0 success, 1 the program broke, 2 the ask was wrong, 70 internal
error (a bug in esolangs), 120 stdout closed early, 124 the timeout ran out,
130 interrupted.

examples:
  esolangs list
  esolangs describe brainfuck
  esolangs encode brainfuck 10
  esolangs generate brainfuck 0110 > prog.txt
  esolangs generate --width brainfuck 10010110
{_TEMPLATE_EXAMPLE}
  esolangs encode brainfuck 10 | esolangs run brainfuck prog.txt \\
    | esolangs read-answer brainfuck
"""


HELP = {
    "encode": """usage: esolangs encode <language> <bits>

Print the stdin that feeds <bits> to a <language> program, so it can be
piped straight into `esolangs run`:

    esolangs encode brainfuck 101 | esolangs run brainfuck prog.txt

Character readers take adjacent 0/1 characters. Numeric readers take
whitespace-delimited tokens; string readers take lines. Other contracts
use a different alphabet, a row index, or padded input.
`esolangs describe <language>` prints the encoding.

A language whose generator embeds the inputs in the program reads no stdin
at all; `esolangs generate --bits` builds those.

example:
  esolangs encode brainfuck 10  # prints 10
""",
    "list": """usage: esolangs list [--details] [--json]
                     [--generator | --interpreter-only] [--grep REGEX]

List matching languages, one per line. Filters combine with AND; filter on
any other fact with `list --json --details | jq`.

options:
  --details   add a marker column per language:
                gen    has a boolean generator
                tmpl   that generator returns a template rather than a
                       runnable program -- see `esolangs generate --help`
                ex     a committed program beside its language modules
                int    interpreter-only: a classic kept for coverage, with
                       no generator, so `generate` refuses it
  --json      print a JSON array: names, or capability records with --details
  --generator restrict to languages with a Boolean generator
  --interpreter-only restrict to languages without a Boolean generator
  --grep REGEX
              select languages whose spec (`describe --spec`) matches,
              case-insensitively

examples:
  esolangs list --generator --details
  esolangs list --json --details | jq -r '.[] | select(.shape == "lookup") | .name'
""",
    "generate": f"""usage: esolangs generate [--width [N] | --balance] [--bits BITS]
                         [--scale N] [--settings JSON] [--set KEY=VALUE]
                         [--plain] <language> <truth-table>

Print a program in <language> computing <truth-table>.

The table is a binary string of length 2**n indexed by the inputs, most
significant first, so its length sets the input count: 0110 is two-input
XOR, 10010110 is three-input.  How the program takes its inputs and
prints the result depends on the language; `esolangs describe <language>`
says (one input per line, adjacent bit characters, and so on).

Some languages instead return a *template*: their generators embed the
inputs in the code rather than reading them, leaving a run of `$` per input
as long as the code that will replace it.  Running one unfilled is refused.
`esolangs list --details` marks them `tmpl`; pass --bits to get a runnable
program instead of the template.

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
               after --settings.
  --plain      export compressed text as ordinary source text.  Without it,
               compressed text is written as gzip and a raster as PNG --
               binary bytes, so redirect them to a file.
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
               the requested width, and `none` ignores it, because
               the language's newlines are semantic or it rejects them.  A
               template wraps with each input's run kept whole, so every
               row it fills to has the same breaks; a layout language lays
               it out instead.  A bare --width takes the
               default, so the next word is read as the language, not as a
               width.

examples:
  esolangs generate brainfuck 0110
{_TEMPLATE_EXAMPLE}
{_DIALECT_EXAMPLES}
""",
    "run": """usage: esolangs run [--timeout S] [--isolated] [--max-output N]
                    [--max-memory BYTES] [--seed N]
                    [--scale N] [--settings JSON] [--set KEY=VALUE]
                    <language> <program-file>

Run a program through its interpreter and print what it writes.

The program is read from <program-file>; its input is this command's stdin.
Input is consumed verbatim using the language's character, number, or
string reads. For generated Boolean programs, `esolangs encode` spells the
input characters, numeric tokens, or lines.

    esolangs encode brainfuck 101 | esolangs run brainfuck prog.txt

Output is written verbatim, so it can be piped byte for byte; a trailing
newline is added only when stdout is a terminal.  Whatever the program
printed before a failure is written too, then the error on stderr.

exit codes: 0 ran, 1 the program broke while running, 2 the ask was wrong
(unknown language, malformed program, unreadable file), 70 internal error (a
bug in esolangs), 120 stdout closed early, 124 the timeout ran out,
130 interrupted.

options:
  --isolated         run in a subprocess; portable deadline, default 30 seconds.
  --max-output N     cap isolated output in Unicode characters (including zero).
  --max-memory BYTES cap Linux worker address space; requires --isolated.
  --timeout SECONDS  stop the run after this long rather than hanging.
                     Unbounded by default.
  --scale N          override detected raster scale; 1 preserves native pixels.
  -s, --settings JSON    dialect overrides; describe lists supported settings.
  --set KEY=VALUE    one dialect override without JSON, repeatable and applied
                     after --settings.
  --seed N           fix the random draws so the run repeats.  `esolangs
                     describe --json <language>` reports `random` for the
                     languages that draw.  A seed for a language that draws
                     nothing is refused rather than ignored.
examples:
  printf '10' | esolangs run brainfuck prog.txt
  printf '10' | esolangs run --timeout 5 brainfuck prog.txt
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
    "read-answer": f"""usage: esolangs read-answer <language>

Read a program's output on stdin and print the answer bit it carries.

For most languages the answer is the last thing printed and this is barely
more than `tail`.  For some it is not: several dump their entire final machine
state, and the answer sits in a tagged memory value or the current marked
cell. `esolangs describe <language>` reports the answer convention.

The languages that answer by terminating have no output to read, so they
are refused here.  A generated program in one halts for 0 and diverges for
1: run it with `--timeout S` and observe whether it halts.  A timeout leaves
the answer undecided.  They are:
  {_TERMINATION_NAMES}

examples:
  esolangs generate brainfuck 0110 > p.txt
  esolangs encode brainfuck 10 | esolangs run brainfuck p.txt \\
    | esolangs read-answer brainfuck
""",
}
