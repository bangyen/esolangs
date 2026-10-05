"""The CLI's own help text: the usage line and the per-command pages.

Kept apart from the code it describes because it is the largest thing in the
interface and the least like the rest of it -- prose that ``--help`` prints
verbatim, with no logic to read.
"""

from __future__ import annotations

from esolangs.tools.wrap import DEFAULT_WIDTH

USAGE = """usage: esolangs <command> [...]

commands:
  list [--details] [--json]   list the supported languages
  encode <language> <bits>    print the stdin that feeds those bits
  generate [--width [N] | --balance] [--bits BITS] [--scale N]
           [--settings JSON] [--set KEY=VALUE] [--portable]
           <language> <truth-table>
                              print a program computing a truth table
                              (--width wraps it; --bits fills a template)
  describe [--json] [--spec] <language>
                              print how that language reads its input and
                              where it puts the answer (--spec prints the
                              interpreter's own description of it)
  run [--timeout S] [--isolated] [--max-output N] [--max-memory BYTES]
      [--seed N] [--scale N] [--settings JSON]
      [--set KEY=VALUE] [--portable] <language> <file>
                              run a program through its interpreter
  suggest <language> <program-file>
                              preview unambiguous command spelling edits
  read-answer <language>      read a program's output on stdin and print
                              the answer bit it carries
  debug [--steps N] [--timeout S] [--watch-cell I] [--stdin S] [--tui]
        [--break-at N] [--break-on-cell I=V] [--break-on-output S]
        [--settings JSON] [--set KEY=VALUE] [--portable]
        <language> <file>
                              run under the debugger and report where it
                              stopped, plus any watched cell's history;
                              --tui steps interactively instead, showing the
                              program with the current op highlighted; its
                              own footer lists the keys, and `esolangs debug
                              --help` names them

Language names are case-insensitive.  `esolangs <command> --help` describes
one command in full; `--version` prints the version.  Short forms: -p is
--portable and -s is --settings.  A truth table is 2^n bits,
most significant first; its length sets the input count (0110 is two-input XOR).

examples:
  esolangs list
  esolangs describe Fargo
  esolangs encode Grapheme 10
  esolangs generate Circlefuck 0110
  esolangs generate --width brainfuck 10010110
  esolangs generate --bits 10 Minifuck 0110
  esolangs run Circlefuck hello.txt
  esolangs generate Fargo 10010110 > fargo.txt
  esolangs encode LaserFuck 10 | esolangs run LaserFuck prog.txt \
    | esolangs read-answer LaserFuck
  esolangs debug --steps 20 --watch-cell 0 brainfuck prog.txt
"""


HELP = {
    "suggest": """usage: esolangs suggest <language> <program-file>

Preview command spelling corrections with 1-based line and column numbers.
Accepts every language; spelling edits cover Modulous, Bitdeque, Packlang,
BrainIf, Grapheme and Collatz Multiverse. Other languages explain why no edits
are offered. Edits fix keyword case or a unique
one-edit match (insertion, deletion, substitution or adjacent swap).
Modulous and Bitdeque preview commands; Bitdeque skips GOTO targets.
Packlang previews required package, datatype, Then and Do keywords. Variable
and function names, comments and speculative declarations are untouched.
Ambiguous matches and operands receive no proposed edit.
BrainIf previews required command words; Grapheme previews letter case throughout
the source, including literals; Collatz Multiverse previews DO/NOT PRINT after
a valid assignment.

The program is neither run nor modified. Apply chosen edits yourself, then
run the program to check its behavior. No suggestions does not mean valid.

example:
  esolangs generate Modulous 0110 > program.txt
  esolangs suggest Modulous program.txt
""",
    "encode": """usage: esolangs encode <language> <bits>

Print the stdin that feeds <bits> to a <language> program, so it can be
piped straight into `esolangs run`:

    esolangs encode Taglate 101 | esolangs run Taglate prog.txt

Character readers take adjacent 0/1 characters. Numeric readers take
whitespace-delimited tokens; string readers take lines. Grapheme spells
its bits %/A, Fargo takes one decimal row index, and Taglate pads an odd
input count with a leading zero character. `esolangs describe <language>`
prints the encoding.

A language whose generator embeds the inputs in the program reads no stdin
at all; `esolangs generate --bits` builds those.

example:
  esolangs encode brainfuck 10 -> 10
""",
    "list": """usage: esolangs list [--details] [--json]

List the supported languages, one per line.

options:
  --details   add a marker column per language:
                gen    has a boolean generator
                tmpl   that generator returns a template rather than a
                       runnable program -- see `esolangs generate --help`
                ex     a committed program in examples/
                int    interpreter-only: a classic kept for coverage, with
                       no generator, so `generate` refuses it
  --json      print a JSON array instead: names alone, or with --details
              an object per language carrying the same three facts as
              booleans, so nobody has to parse the marker column.
""",
    "generate": f"""usage: esolangs generate [--width [N] | --balance] [--bits BITS]
                         [--scale N] [--settings JSON] [--set KEY=VALUE]
                         [--portable] <language> <truth-table>

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
  -p, --portable   write JSON retaining source, dialect choices, and template setters.
  --scale N    enlarge raster pixels by N after layout (default 1).
  -s, --settings JSON  dialect overrides, e.g. '{{"expression_syntax":"postfix"}}'.
  --set KEY=VALUE  one dialect override without JSON, repeatable and applied
               after --settings, e.g. --set expression_syntax=postfix.
  --balance    minimize the rendered width/height difference across supported
               layouts. Ties prefer shorter source, then smaller width. Tokens
               and routing can prevent a square; excludes --width.
  --width [N]  wrap the program to N columns (default {DEFAULT_WIDTH}) so it
               is readable in a diff.  Breaks only between whole tokens.
               `esolangs describe <language>` reports which of three
               things it does, as `width_effect`: `wrap` reflows the
               finished program between whole tokens, `layout` hands the
               width to the generator as a *hint* (LaserFuck asked for 10
               gives 18, asked for 200 gives 56, because it folds runs
               rather than breaking lines), and `none` ignores it, because
               the language's newlines are semantic or it rejects them.  A
               template wraps with each input's run kept whole, so every
               row it fills to has the same breaks; a layout language lays
               it out instead.  A bare --width takes the
               default, so the next word is read as the language, not as a
               width.

examples:
  esolangs generate brainfuck 0110
  esolangs generate --bits 10 Minifuck 0110
  esolangs generate --portable --settings '{{"expression_syntax":"postfix"}}' \\
      Alight 0110 > p.json
  esolangs generate --set expression_syntax=postfix Alight 0110
""",
    "run": """usage: esolangs run [--timeout S] [--isolated] [--max-output N]
                    [--max-memory BYTES] [--seed N]
                    [--scale N] [--settings JSON] [--set KEY=VALUE]
                    [--portable] <language> <program-file>

Run a program through its interpreter and print what it writes.

The program is read from <program-file>; its input is this command's stdin.
Input is consumed verbatim using the language's character, number, or
string reads. For generated Boolean programs, `esolangs encode` spells the
input characters, numeric tokens, or lines.

    esolangs encode Taglate 101 | esolangs run Taglate prog.txt

Output is written verbatim, so it can be piped byte for byte; a trailing
newline is added only when stdout is a terminal.  Whatever the program
printed before a failure is written too, then the error on stderr.

exit codes: 0 ran, 1 the program broke while running, 2 the ask was wrong
(unknown language, malformed program, unreadable file), 124 the bound ran
out, 130 interrupted.

options:
  --isolated         run in a subprocess; portable deadline, default 30 seconds.
  --max-output N     cap isolated output in Unicode characters (including zero).
  --max-memory BYTES cap Linux worker address space; requires --isolated.
  --timeout SECONDS  stop the run after this long rather than hanging.
                     Unbounded by default.  Four languages answer 1 by
                     *not* terminating -- 123, ArrowQueue, Crement and
                     Vandevelo -- so a timeout there is the answer, not a
                     failure.
  --scale N          override detected raster scale; 1 preserves native pixels.
  -p, --portable         load JSON saved by generate --portable.  The language
                     may be omitted because the JSON names it.
                     --settings overrides individual saved choices.
  -s, --settings JSON    dialect overrides, e.g. '{"eof":"zero"}'.
  --set KEY=VALUE    one dialect override without JSON, repeatable and applied
                     after --settings.
  --seed N           fix the random draws so the run repeats.  Eight
                     languages draw: Befunge, Fish, LaserFuck, Modulous,
                     Painfuck, Super SNUSP, Thue and thisthat.  A seed for a language
                     that draws nothing is refused rather than ignored.
examples:
  printf '1\n0\n' | esolangs run brainfuck prog.txt
  printf '1\n0\n' | esolangs run --timeout 5 brainfuck prog.txt
  esolangs generate --portable --set expression_syntax=postfix Alight 0110 > p.json
  esolangs encode Alight 10 | esolangs run --portable Alight p.json \
    | esolangs read-answer Alight
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
  --json      print `esolangs.describe` verbatim as JSON: every key the
              Python API returns, including the interpreter path, the full
              spec text, proof metadata, and example paths that the default
              layout summarizes or omits.

examples:
  esolangs describe Fargo
  esolangs describe "A Painter Ant"
  esolangs describe --json brainfuck
  esolangs describe --spec Unsquare
""",
    "read-answer": """usage: esolangs read-answer <language>

Read a program's output on stdin and print the answer bit it carries.

For most languages the answer is the last thing printed and this is barely
more than `tail`.  For ten it is not: six dump their entire final machine
state, and the answer sits at a fixed place in it -- RAM0's on its `z:`
line, A Painter Ant's as the mark on the ant's own cell (`o` for 0, `@`
for 1).  Working that out by hand meant generating all four rows and
diffing them.

The four languages that answer by terminating have no output to read, so
they are refused here and named: run with `--timeout S` and observe whether it halts.

examples:
  esolangs encode LaserFuck 10 | esolangs run LaserFuck p.txt \
    | esolangs read-answer LaserFuck
  esolangs generate --bits 00 123 0110 > p123.txt
  esolangs run --timeout 10 123 p123.txt
""",
    "debug": """usage: esolangs debug [options] <language> <program-file>

Run a program under the breakpoint/watch VM and report where it stopped.

Prints whether the machine halted, its final instruction position, its
output, any watched cell's history, and any error it raised (a debugged
program is one you are already unsure of, so a raise is reported rather
than propagated).

options:
  --steps N            stop after N commands.  The default is unbounded,
                       which hangs on a program that never halts.
  --watch-cell I       record memory cell I after every step and print the
                       history.  A long history is abridged; --steps bounds
                       it exactly.
  --break-on-output S  stop once S has been written, with S still the last
                       thing written.
  --break-at N         stop when the instruction position reaches N,
                       before executing it.
  --break-on-cell I=V  stop while memory cell I still holds V.
  --timeout SECONDS    stop the run after this long, reporting
                       `stopped: timeout`.  Like --steps this bounds a
                       program that never halts, which is what the four
                       terminate-as-answer languages are.
  --stdin TEXT         feed TEXT verbatim using the language's input unit.
                       The only way to give a debugged program
                       input, since the Python API cannot feed a live
                       debugger either.
  -p, --portable       load JSON saved by generate --portable.  The language
                       may be omitted because the JSON names it.
                       --settings overrides individual saved choices.
  -s, --settings JSON  dialect overrides shared with generate and run.
  --set KEY=VALUE      one dialect override without JSON, repeatable and
                       applied after --settings.
  --tui                step through the program in an interactive
                       full-screen view.  hjkl move the selector, t marks
                       a breakpoint under it, space steps, b steps back, c
                       continues to the next breakpoint or the halt, r runs
                       to the end, q leaves.  Needs a terminal to read keys
                       from.

Every flag above is also listed by `esolangs --help`.  This text used to
name four of the nine, which made the summary more informative than the
page that is supposed to expand it.
""",
}
