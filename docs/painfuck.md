# Painfuck: the implemented reading of the repeat operators

The [wiki page](https://esolangs.org/wiki/Painfuck) defines `c`, `t` and `y`
one application at a time and never says what *repeating* them means.  This
file records what `src/esolangs/interpreters/tape_based/painfuck.py`
implements and why; the interpreter's docstring is authoritative for the
command set and is not restated here.

## `c` and `t` runs: one count, not one per character

Each run is *one* count: `ccc` is `7**3` and `ttt` is `3**3`.  The two differ
in what they can consume.  `c` sits before its command and runs it outright,
so `cp` runs `p` seven times; `t` sits after one that has already executed
and can only add, so `pt` runs `p` four times — once itself, three more from
the `t`.  A `t` cannot retroactively cancel the application that already
happened.

The command before a `t` run may itself be a `c` run, and then the `t` adds
applications of *that*: `ct` is four `c`s, `7 ** 4`.  Both runs are read at
dispatch rather than letting the `t` execute on its own, which would have to
hand a count backward to a command already gone — and no such handoff leaves
`pt` and `ct` both right.

The wiki specifies neither the composition nor the run lengths, so this is
the implementation's reading of "do the last command 3 times" rather than a
quoted rule.  No generated program pairs the two: every `t` run one emits
follows a `p` or an `s`.

## A repeated `y` is `n` decisions, not one

`y` binds forward to the next command exactly as `c` and `v` do; the open
question is whether repeating it makes *one* decision or *n*.  This
implementation makes n: a run of `rep` repeats draws `rep` flips, each
dropping one application of the bound command, so `rep - heads` of them run
and the survivor count is binomial in `rep`.  `cyp` therefore spans
`{0, 2, ..., 14}`, weighted by `Binomial(7, 1/2)`.

The two readings rejected, and why:

- **One decision for the whole run** — any heads skips the command outright,
  giving `cyp` in `{0, 2}` with the skip probability rising to 127/128.
  Coherent, and it keeps `y` meaning "this either happens or it does not"; it
  loses because it discards the repeat count, which `c` exists to supply.
  Under it `cyp` can never exceed `p` applied once, so the seven is spent on
  tuning a probability rather than on the command.
- **Rebinding without gating** — the shape `c`/`v`/`t` use literally, which
  the retired cross-check also had: the first heads rebinds the repeated
  command and the remaining repeats *execute* it.  That inverts the
  instruction, since the command `y` names is then the one that runs most
  (`cyp` left 12), and it makes the skip count geometric rather than
  binomial, because the draw stops at the first heads.

All three readings agree when `rep` is 1, the only case the wiki describes,
so nothing here contradicts it.

The cross-check was written alongside this interpreter rather than from an
independent source, so its agreement was never evidence about the
composition — it shared this implementation's reading of the same gap.
