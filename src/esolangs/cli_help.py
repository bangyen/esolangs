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
  generate [--width [N] | --balance] [--bits BITS] [--scale N] <language> <truth-table>
                              print a program computing a truth table
                              (--width wraps it; --bits fills a template)
  describe [--json] [--spec] <language>
                              print how that language reads its input and
                              where it puts the answer (--spec prints the
                              interpreter's own description of it)
  run [--timeout S] [--judge] [--table T] [--seed N] [--scale N] <language> <file>
                              run a program through its interpreter
                              (--judge prints the answer bit instead)
  check-stdin [--table T] <language>
                              judge stdin against what that language reads,
                              without running anything
  read-answer <language>      read a program's output on stdin and print
                              the answer bit it carries
  answer [--timeout S] <language> <truth-table> <bits>
                              generate, feed those bits, run, and print the
                              one answer bit
  evaluate [--timeout S] [--inputs N | --table T] <language> <program-file>
                              run every input row and print the observed
                              table; --table also checks the expected result
  debug [--steps N] [--timeout S] [--watch-cell I] [--stdin S] [--tui]
        [--break-at N] [--break-on-cell I=V] [--break-on-output S]
        [--table T] <language> <file>
                              run under the debugger and report where it
                              stopped, plus any watched cell's history;
                              --tui steps interactively instead, showing the
                              program with the current op highlighted; its
                              own footer lists the keys, and `esolangs debug
                              --help` names them

Language names are case-insensitive.  `esolangs <command> --help` describes
one command in full; `--version` prints the version.

examples:
  esolangs list
  esolangs describe Fargo
  esolangs encode Grapheme 10
  esolangs generate Circlefuck 0110
  esolangs generate --width brainfuck 10010110
  esolangs generate --bits 10 Minifuck 0110
  esolangs run Circlefuck hello.txt
  esolangs answer brainfuck 0110 10
  esolangs evaluate --table 10010110 Fargo program.txt
  esolangs encode LaserFuck 10 | esolangs run --judge LaserFuck prog.txt
  esolangs debug --steps 20 --watch-cell 0 brainfuck prog.txt
"""


HELP = {
    "encode": """usage: esolangs encode <language> <bits>

Print the stdin that feeds <bits> to a <language> program, so it can be
piped straight into `esolangs run`:

    esolangs encode Taglate 101 | esolangs run Taglate prog.txt

Most languages read one 0/1 line per bit and this is no more than what you
would have typed.  Four are not most languages, and each fails silently if
you guess: Grapheme spells its bits %/A, Clockwise wants them all on one
line, Fargo wants the row index as one decimal number, and Taglate pads an
odd input count with a leading zero line.  `esolangs describe <language>`
prints which of those you are dealing with.

A language whose generator embeds the inputs in the program reads no stdin
at all; `esolangs generate --bits` builds those.
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
                         [--scale N] <language> <truth-table>

Print a program in <language> computing <truth-table>.

The table is a binary string of length 2**n indexed by the inputs, most
significant first, so its length sets the input count: 0110 is two-input
XOR, 10010110 is three-input.  The program reads one input per line and
prints the result.

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
""",
    "run": """usage: esolangs run [--timeout S] [--judge] [--table T] [--seed N]
                    [--scale N] <language> <program-file>

Run a program through its interpreter and print what it writes.

The program is read from <program-file>; its input is this command's stdin.
Most languages read one line per input bit, but four do not: Grapheme reads
%/A rather than 0/1, Clockwise takes every bit on one line, Fargo takes the
row index as one decimal number, and Taglate pads an odd input count with a
leading zero.  Stdin is checked against that shape -- this command warns,
`--judge` refuses -- but a wrong shape that still looks legitimate answers
the wrong row, so let `esolangs encode` spell it:

    esolangs encode Taglate 101 | esolangs run Taglate prog.txt

Output is written verbatim, so it can be piped byte for byte; a trailing
newline is added only when stdout is a terminal.  Whatever the program
printed before a failure is written too, then the error on stderr.

exit codes: 0 ran, 1 the program broke while running, 2 the ask was wrong
(unknown language, malformed program, unreadable file), 124 the bound ran
out, 130 interrupted.

options:
  --timeout SECONDS  stop the run after this long rather than hanging.
                     Unbounded by default.  Four languages answer 1 by
                     *not* terminating -- 123, ArrowQueue, Crement and
                     Vandevelo -- so a timeout there is the answer, not a
                     failure.
  --scale N          override detected raster scale; 1 preserves native pixels.
  --seed N           fix the random draws so the run repeats.  Eight
                     languages draw: Befunge, Fish, LaserFuck, Modulous,
                     Painfuck, Super SNUSP, Thue and thisthat.  A seed for a language
                     that draws nothing is refused rather than ignored.
  --table TABLE      the truth table the program was generated from.  Adds
                     the bit *count* to the stdin check, which a shape
                     check cannot do alone: three lines fed to a two-input
                     program is only wrong relative to an arity.
  --judge            print the answer bit instead of the raw output.  Ten
                     languages do not simply print it -- six dump their
                     whole final state, four answer by terminating -- and
                     those four need `--timeout`.

examples:
  printf '1\n0\n' | esolangs run brainfuck prog.txt
  printf '1\n0\n' | esolangs run --judge --timeout 5 brainfuck prog.txt
""",
    "answer": """usage: esolangs answer [--timeout S] <language> <truth-table> <bits>

Generate a program for <truth-table>, feed it <bits>, run it, and print the
single answer bit.

This generates and runs one row. Everything it does was
already possible -- generate to a file, encode the bits, pipe them in, judge
the output -- but that is four commands and a temporary file, and the
encoding step is the one people get wrong.  Nothing here can be
mis-encoded: the bits go in as bits.

  esolangs answer brainfuck 0110 10        -> 1
  esolangs answer Fargo 10010110 101       -> 1
  esolangs answer "A Painter Ant" 0110 01  -> 1

Works for every language, including those whose generators embed
their inputs, those that dump their whole final state, and the four that
answer by not terminating -- for those a bound is needed, and the default
below is applied.

options:
  --timeout SECONDS  bound the run.  Defaults to 5 seconds for the four
                     languages whose answer for a 1 is that the program
                     never stops, and to none for the rest.
""",
    "evaluate": """usage: esolangs evaluate [--timeout S] [--inputs N | --table T]
                          <language> <program-file>

Run the supplied program on every Boolean input row and print its observed
truth table. No program is generated. Text, PNG sources, and parameterized
templates are supported; templates are filled separately for every row.

options:
  --inputs N        enumerate N inputs, from 1 to 64, MSB first.
  --table TABLE     infer the input count and compare the observed table with
                     TABLE. Exits 1 on mismatch and names the differing rows.
                     Mutually exclusive with --inputs; one is required.
  --timeout SECONDS  bound each row. Defaults to 30 seconds, or 5 for
                     termination answers. Repeated states prove divergence;
                     the deadline is a backstop for growth, not an answer.

examples:
  esolangs evaluate --inputs 2 brainfuck program.txt
  esolangs evaluate --table 0110 brainfuck program.txt
""",
    "check-stdin": """usage: esolangs check-stdin [--table T] <language>

Read stdin and say whether it is what <language> wants, without running a
program.

Exits 0 and says nothing when it is fine.  Otherwise it names what is wrong
and exits 2 -- the wrong alphabet, a shape the language cannot read, a row
index with a leading zero, and with --table the wrong bit count or an index
out of range.

Without --table it judges *shape*, and for most languages a shape is not a
count.  Clockwise wants every bit on one line; Fargo wants one row index.
For those two a stray line is a shape error and is caught.  Of the rest,
every language but Taglate reads a line per bit; Taglate reads a line per
bit plus a padding one -- and for all of them one line, three lines and no
lines at all are equally well shaped.  An empty stdin passes `check-stdin
brainfuck`, which is the trap worth naming: only --table knows how many
bits the program wanted.

This checks Boolean input explicitly. `run --judge` applies it as a refusal;
plain `run` accepts arbitrary input.

examples:
  esolangs encode Grapheme 10 | esolangs check-stdin Grapheme
  printf '1\\n0\\n1\\n' | esolangs check-stdin --table 0110 brainfuck
""",
    "describe": """usage: esolangs describe [--json] [--spec] <language>

Print what a language does with its input bits and where it puts the answer.

The fields are the ones the Python API returns from `esolangs.describe`:
its state model and interpreter, whether it has a truth-table generator and
whether that generator embeds the bits (`--bits`) or reads them from stdin,
the input shape and alphabet, and how to find the answer in the output.

This exists because those facts decided every wrong answer anyone got out
of this tool, and the only place they were readable was a Python session.

options:
  --spec      print the interpreter's own description of the language: its
              command table, and where this implementation differs from the
              wiki page.  Every language carries one, they run to a
              few thousand characters, and they are the best documentation
              here for *writing* a program rather than generating one.
  --json      print `esolangs.describe` verbatim as JSON.  The default
              layout is for reading and loses things on the way: a pair
              prints as `0 1` with no way back to two values, an empty
              field is dropped rather than shown as empty, the closing
              `input` line is a sentence this command composes and not a
              key at all, and for template languages
              `input_shape` and `input_encoding` are left out entirely --
              they describe an stdin those programs never read, and the
              `input` line says so instead.  --json is the dict, exactly,
              those two included.

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
they are refused here and named: use `run --judge --timeout S` instead.

examples:
  esolangs encode LaserFuck 10 | esolangs run LaserFuck p.txt \
    | esolangs read-answer LaserFuck
  esolangs generate --bits 01 123 0110 > p123.txt
  esolangs run --judge --timeout 10 123 p123.txt
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
  --stdin TEXT         feed TEXT to the program as its input, one line per
                       newline.  The only way to give a debugged program
                       input, since the Python API cannot feed a live
                       debugger either.
  --table T            check the stdin against the shape and alphabet T's
                       arity implies, before running.
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
