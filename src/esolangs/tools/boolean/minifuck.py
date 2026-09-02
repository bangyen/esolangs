"""Boolean-function generator for Minifuck (parameterized convention).

Minifuck's only input is ``.`` reading a byte when the eight-cell pool is
zero, which a boolean program cannot use without disturbing the pool it is
about to print.  So this follows the parameterized convention described in
:mod:`esolangs.tools.boolean.parameterized`: the template's ``{Xi}``
placeholders become ``[<`` (bit 1) or ``xx`` (bit 0) -- equal width, so no
instantiation leaks its inputs through its length -- and the harness builds
one program per input combination.

Four facts about the language carry the whole construction, each checked
against the interpreter rather than argued from the spec:

* ``[`` on a 1-cell clears it, XORs into ``ptr+1``, and skips one
  instruction; control flow rejoins after that single slot, so only *state*
  diverges, never the instruction stream.
* ``[x`` therefore advances the pointer exactly one cell whatever the crossed
  cell holds, which makes rightward walks position-deterministic over
  arbitrary junk.
* A ``[x``-walk leaves ``cell_i = NOT(old_i XOR w_{i-1})`` -- the complement
  of the running prefix-XOR of everything crossed.  The transform is affine
  and invertible, so re-crossing the stored bits loses nothing.
* ``<`` never writes and clamps at 0, so a long enough run of ``<``
  reconverges every path for free.

**How a program is built.**  Embed each input once, separated by one of
:data:`_SEPS`; walk to ``_BASE - 1``; emit a suffix (a run of ``[``, or for
one table a string with ``<`` interleaved); then run the endgame, which sets
the pool, relays a cell's value into the *pointer* -- values cannot travel
left in this language, but the pointer can -- and prints one ASCII digit.

The choice of ``(separator, settle count, suffix, accumulator)`` is what
makes a table build, and that choice is **derived, not stored**: the product
is small enough to walk, so :func:`_derive_staging` enumerates it in a fixed
order and takes the first entry that prints.  Each candidate is run and its
rows compared against the table, so nothing is accepted on a recorded claim.
The one pair whose suffix no bracket run spells is answered by the
sculpted route below, which is why no third suffix family is carried here.

The selection rule is the load-bearing part, and it is why the enumeration
tests rather than predicts: the accumulator that works is the one whose
column reads correctly **at the read**, not the cell holding the answer
beforehand.  Those differ, because the walk out applies the running
prefix-XOR -- an AND column can arrive as a constant, and XOR can arrive as a
projection.  Choosing pre-walk covers 10 of the 16 two-input tables and looks
nearly right, which is the trap.

A table and its complement share a staging: the endgame tries both read
polarities and prints ``NOT(v XOR cell7)``, so the complement costs nothing.

**Coverage.**  Every table at ``n <= 3`` builds from a staging, with no
search: 16 of 16 at two inputs, 256 of 256 at three.  All but one pair are
derived, and the derivation is done for a whole arity at a time -- measured,
0.15s for two inputs and 2.4s for three, against minutes if each table sweeps
for itself.  So the first three-input table costs the arity and the other
255 are free; that is the trade deriving makes against storing.

Four inputs is *partial* and staged anyway.  The name-order enumeration
reaches 15404 of the 64594 fully essential four-input tables (23.9%),
four-input XOR among them.  What buys those is one widening of the suffix --
a single ``<`` inside the bracket run, enumerated after every pure run.  A
two-insert family one step wider existed here and was removed: it served a
single three-input pair that the sculpted route now builds.
Partial coverage is worth gating on because a miss is not a failure: it falls
through to the searches below, which is why those remain -- a missing staging
degrades rather than raises.  What a four-input table does pay for is the
derivation, which at this arity cannot stop early; see
:data:`_STAGED_ARITIES`.

A second pass once took the arity to **60942 of 64594 (94.35%)** by
complementing inputs as they land.  It has been removed: every table it
placed is one the sculpted route below also builds, and it cost a
300-second whole-arity sweep to place them.  ``docs/walls.md`` keeps the
mechanism and the measurement.

**The remaining 3652 fall to the sculpted route**, :func:`_mux`, which is a
different construction rather than another coordinate on this one -- and it
still embeds each input exactly once.  Each input is *weighted as it lands*:
a restoring read repeated ``k`` times displaces the pointer by ``k`` times
the bit, so giving input ``i`` weight ``2**(n-1-i)`` leaves the pointer
holding the row's binary expansion.  That is affine and injective, so the
``2**n`` rows arrive at ``2**n`` *distinct pointer positions* by
construction, with nothing searched for.  Separated rows can then be edited
individually: the printed column is fixed one row at a time from the highest
position down, each round exact for its target row and provably unable to
disturb the rows above it, so the loop terminates in at most ``2**n``
rounds.  With it the arity is closed: all 64594 fully-essential four-input
tables build, the 3652 verified row by row on the shipped interpreter, and
five inputs is reached on every table sampled (200 of 200, five-input XOR
among them).  See the comment block above :data:`_MUX_BASE` for the
mechanism and the measurements.

Five inputs is staged on the same terms and a far thinner slice: the family
produces 24582 fully-essential 32-bit columns against 4294642034 such tables,
so this is 0.00057% of the arity rather than a quarter of it.  It ships for
the reason four did -- a miss costs nothing but the fall-through.  The one
thing that had to change is the spelling: a derivation over all ``2**32``
tables cannot run, so the enumeration is asked for the table it wants -- see
:func:`_derived_plans`, which every arity now uses that way.  What catches
the rest is the sculpted route, which since its separation became a
construction reaches five as readily as four: 200 of 200 sampled
fully-essential five-input tables build and print every row.

Paying that per table is what makes a *screen* worth having, and there is
one: everything the endgame emits after the suffix is GF(2)-affine in the
columns standing at that point, so a printed column lies in their span.  A
table in no staging's span cannot be printed by any of them, and
:func:`_span_admits` says so in about 3.6 milliseconds where the enumeration
takes 143 seconds to find nothing.  It only ever declines, so no table that
built before builds differently now.
A table that ignores some inputs is solved at the arity it uses and renumbered
back, so a wide table with a narrow core is as cheap as that core.

Nothing here is hand-tracked: :class:`_Joint` runs all ``2**n`` instantiations
in lockstep as the template is emitted, every choice is made against the
simulated truth, and :func:`minifuck` raises rather than returning a program
it has not seen print the table.

``docs/walls.md`` carries the history this docstring used to: which
mechanisms were disproved outright, which were merely unfound, what the
runtime-read model reaches, and how the staged route came to cover tables the
searches fail on.
"""

import re
from collections import deque
from collections.abc import Callable, Iterator
from functools import cache

from esolangs.tools.boolean.helpers import (
    _validate_shape,
    _validate_truth_table,
    essential_inputs,
    read_at,
)

__all__ = ["minifuck"]

# What an acceptance callback keeps: each search names its own result type,
# and returning None means "keep looking".

# Where the embedded bits start.  The pool is cells 0..7, so the working area
# begins past it with a little room for the walk-in.
_BASE = 16

# What separates one embedded bit from the next.  A plain ``[x`` run leaves
# the prefix-XORs too correlated for the one-sided tests the endgame makes;
# the ``<`` steps back over a cell so the parities stay distinguishable.
#
# The separator decides the affine picture the whole construction reads from,
# and the first two here were picked by hand.  That turned out to be the
# binding constraint rather than a detail: between them they leave only 92
# distinct columns standing, and 112 of the 120 tables the searches could not
# reach were absent from the tape entirely rather than merely hard to print.
# Enumerating short strings over the same alphabet fixed that -- the three
# added below carry 118 of those 120, and the searches never had to change.
# Only the first two are used by the routes that scan separators (the
# degenerate path and the fallback searches); the rest are reached by the
# staging enumeration, so adding one costs those routes nothing.
_SEPS = ("[x<[x", "[x[x[x", "[<[<[", "[[[[[", "[x[<[")
_SEP = _SEPS[0]

# The separators the scanning routes try.  Widening this would multiply every
# search's cost; the plan reaches the others directly instead.
_SCAN_SEPS = _SEPS[:2]

# How far the bits and their working area reach, for sizing the windows.
_SPAN = 6

# The pool spells ASCII '0' (0b00110000) or '1' (0b00110001), so cells 0..6
# are fixed and cell 7 carries the answer.
_POOL = (0, 0, 1, 1, 0, 0, 0)

# The two reads.  ``[<`` leaves the pointer at ``(acc-1) + v``; ``[x<[<``
# leaves it at ``(acc-1) + NOT v``, restores the cell, and flips its
# neighbour unconditionally.  The printed digit is ``NOT(v XOR cell7)`` and
# every reachable pool conserves that XOR, so the read polarity -- not the
# pool -- is what makes a table and its complement both printable.
_READS = ("[<", "[x<[<")

# Depth cap for the column search, a joint search over 2**n machines whose
# cost is exponential in the cap; this is the smallest value covering every
# two-input table.  (The pool no longer has one: see :data:`_POOL_CODES`.)
_COLUMN_DEPTH = 13

# The parked search is the fallback, and the deepest of the three; it needs
# 15 to cover the XOR family.  ``_PARKED_LIMIT`` candidates are collected
# because which one survives the endgame is settled by running it.
_PARKED_DEPTH = 15
_PARKED_LIMIT = 12

# Re-crossings of the bit region before the parked search.  Each advances the
# affine state, which offers the search a different set of columns.
_SETTLE = 2


class _Sim:
    """A Minifuck machine fed one instruction at a time.

    The shipped interpreter takes its whole program up front, which an
    emitter cannot do -- it must advance a machine and branch on the result.
    This mirrors ``_Machine.step`` exactly while accepting instructions
    singly.  ``dead`` marks the one transition a parameterized program must
    never take: a ``.`` on a zero pool reads a byte of input.
    """

    __slots__ = ("dead", "out", "ptr", "skip", "tape")

    def __init__(self, size: int) -> None:
        """Start with a zeroed tape of ``size`` cells at the origin."""
        self.tape = [0] * size
        self.ptr = 0
        self.out: list[str] = []
        self.dead = False
        self.skip = False

    def copy(self) -> "_Sim":
        """Return an independent copy, for branching a search or a probe."""
        clone = _Sim.__new__(_Sim)
        clone.tape = list(self.tape)
        clone.ptr = self.ptr
        clone.out = list(self.out)
        clone.dead = self.dead
        clone.skip = self.skip
        return clone

    def key(self) -> tuple[object, ...]:
        """Return the whole state, hashable, so a search can dedup on it."""
        return (tuple(self.tape), self.ptr, tuple(self.out), self.dead, self.skip)

    @staticmethod
    def restore(key: tuple[object, ...]) -> "_Sim":
        """Rebuild the machine :meth:`key` described.

        The inverse of :meth:`key`, so a memo can hold states rather than
        machines and hand back something the probes can step.
        """
        tape, ptr, out, dead, skip = key
        clone = _Sim.__new__(_Sim)
        clone.tape = list(tape)  # type: ignore[call-overload]
        clone.ptr = ptr  # type: ignore[assignment]
        clone.out = list(out)  # type: ignore[call-overload]
        clone.dead = dead  # type: ignore[assignment]
        clone.skip = skip  # type: ignore[assignment]
        return clone

    def exec(self, ins: str) -> None:
        """Execute one instruction, mirroring ``_Machine.step``."""
        if self.dead:
            return
        if self.skip:
            self.skip = False
            return
        if ins == "<":
            if self.ptr:
                self.ptr -= 1
        elif ins in ".[":
            self.ptr += 1
            if self.ptr + 1 >= len(self.tape):
                self.tape.append(0)
            self.tape[self.ptr] ^= 1
            if ins == ".":
                value = int("".join(map(str, self.tape[:8])), 2)
                if value:
                    self.out.append(chr(value))
                else:
                    self.dead = True
            elif not self.tape[self.ptr]:
                self.tape[self.ptr + 1] ^= 1
                self.skip = True


def _set_bit(bit: int) -> str:
    """Return the ``{Xi}`` fill writing ``bit`` at ``ptr+1``.

    Both spellings are two characters and leave the pointer where they found
    it, so every instantiation has the same length -- without that, the
    program's length would leak the inputs it is meant to be evaluating.
    """
    return "[<" if bit else "xx"


class _Joint:
    """The ``2**n`` instantiations, advanced in lockstep as code is emitted."""

    def __init__(self, n: int, size: int = 512) -> None:
        """Start one machine per row of the truth table."""
        self.n = n
        self.rows = [[(r >> (n - 1 - k)) & 1 for k in range(n)] for r in range(2**n)]
        self.ms = [_Sim(size) for _ in self.rows]
        self.parts: list[str] = []

    def emit(self, code: str) -> None:
        """Append code and run it on every row, keeping them in lockstep."""
        self.parts.append(code)
        for m in self.ms:
            for ch in code:
                m.exec(ch)

    def emit_setter(self, i: int) -> None:
        """Emit the ``{Xi}`` placeholder, simulating each row with its bit."""
        self.parts.append("{X" + str(i) + "}")
        for bits, m in zip(self.rows, self.ms, strict=True):
            for ch in _set_bit(bits[i]):
                m.exec(ch)

    def fork(self) -> "_Joint":
        """Return a copy, for trying a continuation without committing."""
        clone = _Joint.__new__(_Joint)
        clone.n = self.n
        clone.rows = self.rows
        clone.ms = [m.copy() for m in self.ms]
        clone.parts = list(self.parts)
        return clone

    def col(self, cell: int) -> tuple[int, ...]:
        """Return ``cell``'s value across the rows -- the function it holds."""
        return tuple(m.tape[cell] for m in self.ms)

    def ptrs(self) -> tuple[int, ...]:
        """Return each row's pointer, so callers can see divergence."""
        return tuple(m.ptr for m in self.ms)

    def printed(self) -> list[str]:
        """Return what each row has printed so far."""
        return ["".join(m.out) for m in self.ms]

    def template(self) -> str:
        """Return the emitted template, ``{Xi}`` placeholders included."""
        return "".join(self.parts)


def _walk_to(j: _Joint, target: int) -> None:
    """Walk right to ``target`` with ``[x``, which is safe over any junk."""
    ptrs = set(j.ptrs())
    if len(ptrs) != 1:
        raise ValueError(f"walk needs a converged pointer, got {ptrs}")
    cur = ptrs.pop()
    if target < cur:
        raise ValueError(f"cannot walk left with [x ({cur} -> {target})")
    j.emit("[x" * (target - cur))


def _clamp(j: _Joint) -> None:
    """Clamp every row's pointer to 0.  ``<`` never writes, so this is free."""
    j.emit("<" * (max(j.ptrs()) + 1))


# What complements the bit a setter just wrote.  ``<`` steps back over the
# cell the setter used and ``[`` flips it, which cascades into the setter's
# own cell -- so the bit standing there is inverted, and the pointer is left
# where the setter left it.
#
# The trailing character is not padding.  That cascade sets the interpreter's
# skip flag, and a gadget that ends there eats the *next* instruction of the
# template, shifting every later embedding by a cell; the third character
# feeds the skip instead.  Measured rather than reasoned: the two-character
# ``<[`` passes a probe that compares tape and pointer, and the tables built
# on it printed 0 of 12 on the real interpreter.  ``skip`` is part of the
# state, and a probe that omits it reports a gadget that is not one.
_FLIP = "<[x"


def _embed(
    n: int,
    settle: int = 0,
    sep: str = _SEP,
    flips: int = 0,
) -> _Joint:
    """Emit the embed: each ``{Xi}`` once, separated by :data:`_SEP`.

    The separator is not arbitrary.  A plain run of ``[x`` leaves the bits'
    prefix-XORs too correlated for the one-sided tests the endgame can make,
    and the XOR family becomes unreachable; ``[x<[x`` steps back over one
    cell so the parities stay distinguishable.  ``settle`` re-crosses the
    region that many times, which advances the affine state and offers the
    searches a different set of columns.

    ``flips`` is a mask of the inputs whose bit is complemented as it lands,
    and it defaults to what this always did.  It is a *derivation coordinate*
    rather than post-processing: the gadget writes the live tape and leaves
    interpreter state behind, so a joint that did not emit it would be
    simulating a different program than the one that ships.  The pass that
    varied it has been removed (see below); the parameter stays because the
    coordinate is real and cheap to keep open.

    The setters are emitted in ascending name order whatever the mask says --
    the gadget goes *after* the setter it complements, never in place of a
    different one -- so a flipped embed satisfies the slot-order invariant
    ``tests/tools/test_boolean_parameterized.py`` holds every generator to.
    """
    j = _Joint(n)
    _walk_to(j, _BASE - 1)
    for i in range(n):
        j.emit_setter(i)
        if (flips >> i) & 1:
            j.emit(_FLIP)
        j.emit("[x")
        if i + 1 < n:
            j.emit(sep)
    for _ in range(settle):
        _clamp(j)
        _walk_to(j, _BASE - 1)
    return j


def _search[Hit](
    j: _Joint,
    accept: Callable[[list[_Sim], str], Hit | None],
    maxlen: int,
) -> Hit | None:
    """Breadth-first over ``<[x`` from the live joint state.

    ``accept`` sees the advanced machines and returns a result (or None).
    Searching from the *live* state is what makes the junk already on the
    tape part of the starting condition rather than a precondition to
    establish -- and the search must start with the pointer in the data, not
    at the origin: a depth-``d`` walk from cell 0 never reaches cell
    ``_BASE``, so every state it can see is input-independent.
    """
    root = tuple(m.copy() for m in j.ms)
    seen = {tuple(m.key() for m in root)}
    queue = deque([(root, "")])
    while queue:
        states, prog = queue.popleft()
        if len(prog) >= maxlen:
            continue
        for ch in "<[x":
            new = []
            for m in states:
                clone = m.copy()
                clone.exec(ch)
                new.append(clone)
            # A dead row can no longer be steered, so a state holding one is
            # not worth expanding.  Nothing in the alphabet below kills a row
            # -- only a print does -- so this fires on a state that arrived
            # dead, not on one this search killed.
            if any(m.dead for m in new):
                continue
            key = tuple(m.key() for m in new)
            if key in seen:
                continue
            seen.add(key)
            code = prog + ch
            if not any(m.skip for m in new):
                hit = accept(new, code)
                if hit is not None:
                    return hit
            queue.append((tuple(new), code))
    return None


# The pool codes: one construction at five parameters.
#
# They read as five unrelated strings and are not.  One law runs through all
# of it:
#
#     **a run of k brackets carries a mark right by ceil(k / 2) cells**,
#     leaving a pending skip when k is odd
#
# -- verified from marks at cells 2 to 5 for runs of 1 to 8.  Read forwards
# that law describes a walk; read backwards it *builds* one, which is what
# :func:`_step` does.  Asking for a carry of ``c`` fixes the bracket run at
# ``2 * c - 1``, or ``2 * c`` where the pending skip is not wanted, and a run
# of ``<`` then sets how far behind its mark the pointer ends up.  So a code
# is a sequence of steps, and the default step -- carry the mark one cell,
# leave the pointer one behind it -- spells itself ``'[<'``.
#
# Every code is that default repeated, with exactly one step -- the core --
# carrying two instead of one.  How many steps, and which one is the core, is
# most of the construction:
#
#     steps  core   overrides                     code
#       2      0    backs 4 at step 1             '[[[<[<<<<'
#       4      1    --                            '[<[[[<[<[<'
#       5      2    --                            '[<[<[[[<[<[<'
#       5      3    backs 2 at step 0             '[<<[<[<[[[<[<'
#       5      3    backs 2 at 2, even run at 4   '[<[<[<<[[[<[[<<<'
#
# Two of the five need no override at all: they are the construction indexed
# by where the mark goes, and nothing else.  The overrides are the informative
# part, and each is one of the two free variables the law leaves open.
#
# ``backs`` is the pointer, and the walk is clean only when the pointer sits
# just left of the mark.  The last code widens it to 2 at step 2, which is why
# that code arrives at cell 3 with the pointer at 1 rather than 2 and the core
# then spreads marks over cells 2..4 instead of carrying one.  A plain default
# there would mark cell 3 and walk cleanly; what the widened step buys is the
# pointer.
#
# Neither widening is slack, and the fourth code is the one that proves it
# cannot be read off a blank tape.  Narrowed to the default its trace on an
# empty tape is *identical* -- mark at 6, pointer at 5 -- because ``<`` clamps
# at cell 0 and both spellings start there.  On the live states the endgame
# actually presents, the pool cells are already set, so the opening ``[``
# fires and the pointer is no longer at 0 when the second ``<`` runs.  The
# two spellings then walk different tapes and land the pool two cells apart.
# Narrowed and ablated the way the searches-stubbed test ablates a whole code,
# the default spelling strands 18 tables at ``n == 3`` -- the same 18 that
# dropping the code strands, so the widening *is* the code.
#
# ``odd`` is the pending skip, and one step in the family turns it off.  The
# same code's last step wants a carry of one *without* the skip, which the law
# spells as an even run -- the only even bracket run in the five.  A carry
# alone does not determine the spelling, and this step is what proves it.
#
# The same law is why the mirrors were derivable and why exactly two flips
# existed.  A mirror is its setter plus a bracket run, and the two that work --
# ``'[' * 4 + '<'`` and ``'[' * 6 + '<'`` -- are the runs displacing a mark by
# +2 and +3, which is what the two end positions need.  Odd runs fail because
# they leave the pending skip; that is the real reason, not the parity of k.
#
# This is worth stating because every surface measure says the opposite.
# Pairwise edit distance runs 2 to 7, prefix-factoring an exact regex makes it
# *longer* (73 characters against 64), and the minimal DFA finds only one pair
# converging.  All true, and all measuring spelling rather than behaviour: the
# structure is in what the strings do to the tape.
#
# Setting the pool is not a search: across every table at ``n <= 3`` the
# breadth-first search this replaced returned one of a handful of strings, and
# trying candidates in turn reproduces its answer on every call the generator
# makes.  Each is still checked against the same acceptance test the search
# applied, so a code is accepted on exactly the evidence it always was.
#
# A lookup keyed on ``(cell7, walk_out)`` would *not* work, which is why this
# is a list tried in turn rather than a table: the same pair takes different
# codes, and sometimes none, depending on the state the staging leaves behind.
#
# **Why five, when the endgame asks about two orientations.**  Every one of
# these answers only ``cell7 == 0``; not one satisfies ``cell7 == 1``.  That
# looks like half a list and is not, because **a missing pool is not fatal**.
# ``_try_print`` forks the same state for both orientations and both reads, so
# a refusal is one failed attempt among four and another attempt answers the
# table.  Measured with the fallback searches stubbed to raise -- so a
# fallthrough would be a hard failure rather than a slow success -- these five
# build and run all 272 tables at ``n <= 3`` while ``_find_pool`` returns None
# on 17145 of 34516 calls.  Half the calls fail and nothing is lost.
#
# That measurement is the one to repeat before adding a code.  An earlier
# version of this list carried ten strings, the extra five being the
# ``cell7 == 1`` mirrors; they cost 136 changed templates and bought nothing,
# which only became visible when the ablation was run with the searches
# stubbed.  Ablating with the fallthrough open reports success either way,
# because the searches quietly rebuild whatever the pool list drops.
#
# **Would re-adding them help now?**  Worth answering here because the drop was
# measured at ``n <= 3`` only, and the four-input work below turns on exactly
# the orientation the mirrors served.  Measured rather than argued: the mirrors
# reach *more* sites than the closure pair found below -- 367 of 367 harvested
# three-input sites against 307, and the same 400 of 400 at sixteen rows, where
# two of them cover site-for-site what that pair covers (they are distinct
# functions with identical coverage).  So on reach they would do the job.
#
# It still does not help, and that was run rather than inferred: with the
# mirrors installed, four-input XOR makes 1016 pool lookups, all 1016 succeed,
# and the build fails -- the same numbers the closure pair gives.  Serving the
# orientation closes *sites* and builds no table.  What the drop got right was
# the conclusion; what it could not have known is that the surplus reach is
# real and simply has nothing to fix -- every table at ``n <= 3`` already
# builds.  As an implementation they are also dominated: ten strings of length
# 14 to 23, of which four cover anything and two matter, against a pair at 11
# and 14.
#
# The flips themselves are one step each under the law below: ``'[[[[<'`` is
# ``_step(2, 1, odd=False)`` and ``'[[[[[[<'`` is ``_step(3, 1, odd=False)``.
# That is why exactly those two worked and the odd runs did not, which
# a492a2ea recorded as a fact before there was a vocabulary to state it in.
#
# **The missing orientation is not missing, and the space is catalogued.**
# The mirrors made ``cell7 == 1`` look reachable only by appending a flip to a
# shipped code.  It is not: sweeping *every* string over ``{'[', '<'}`` up to
# length 16 -- 131070 of them -- against harvested sites leaves 1464 usable
# pool codes, 448 of them answering ``cell7 == 1`` natively.  Nothing shorter
# than eleven characters works at all, which the sweep settles rather than
# bounds, and the count by length runs 8, 32, 54, 162, 314, 894 from eleven to
# sixteen.  The list of five is a choice out of a large space, not a scarce
# find.
#
# One law falls out and it is exact, not sampled.  **No code serves both
# orientations.**  Per site that is forced: a code's effect on a fixed state is
# deterministic, so it lands one value in cell 7 and can satisfy at most one
# target.  Measured across sites as well, no code answers ``cell7 == 0``
# anywhere and ``cell7 == 1`` elsewhere -- each of the 1464 is bound to one
# orientation.  So the list being "half a list" is the shape of the space, not
# an accident of these five strings.
#
# **Two codes close the other half.**  A breadth-first search over reachable
# joint states -- which answers "can *any* string do this", at any length, not
# just short ones -- finds every one of 120 sampled four-input sites reachable.
# The shipped five answer the 60 at ``cell7 == 0`` and none of the 60 at
# ``cell7 == 1``, and that entire gap closes with::
#
#     _step(4, 3, odd=False)                  '[[[[[[[[<<<'     148 sites
#     _step() + _step(5, 2, odd=False)        '[<[[[[[[[[[[<<'   52 sites
#
# Together with the shipped five that is 400 of 400 harvested sixteen-row
# sites, against 200 for the shipped five alone.  Appended last they change
# nothing at ``n <= 3``: all 272 templates are byte-identical and the
# out-of-name-order count stays at 10, because the shipped five are tried first
# and win every call they already answered.
#
# **And it buys no tables, which is the point.**  With both appended, the
# four-input tables that fail still fail -- and the instrumented runs say why
# that is conclusive rather than suggestive.  On both tables tried,
# ``_find_pool`` never once returns None: four-input XOR makes 1016 lookups and
# all 1016 succeed, and a second failing table makes 296 and all 296 succeed.
# Both still fail to build.  There is no pool lookup left to satisfy, so the
# pool is not the constraint; the ``n >= 4`` limit is search depth and no pool
# code can raise it.  See :data:`_STAGED_ARITIES`.
#
# That is what closes this line of attack.  The earlier reading -- "the wall is
# search depth" -- was inferred from a one-in-two hit rate, which is consistent
# with the pool being a partial constraint.  A hit rate of one leaves no room
# for that: better pool codes cannot help, because there is nothing left for
# them to fix.
#
# Depth alone is not the whole answer either.  Raising :data:`_COLUMN_DEPTH`
# and :data:`_PARKED_DEPTH` together by four and by eight, with the two codes
# above in place, does not build four-input XOR within ten minutes either way.
# So "search depth" names where the constraint lives, not a setting that would
# lift it; what a wider arity needs is a cheaper route, which is what
# :data:`_STAGED_ARITIES` gates.
#
# The family also regenerates what the list already has: complete substitutes
# for the third code (a dropped-code gap of 22 tables refilled by either of two
# ``'[<[<' + core`` members) and for the fourth (18 tables, refilled by a
# ``k == 6`` member with a long ``'<<<'`` tail).  No substitute was found for
# the fifth among the three candidates tried.
#
# None of this argues for adding a code.  The shipped five strand nothing, the
# two above are free but buy nothing measurable, and expressing them would need
# :data:`_PLANS` to carry a per-step carry (both use carries of 4 and 5, where
# every shipped step carries 1 or 2).  It is recorded so the questions "is the
# other orientation out of reach?" and "can better pool codes raise the arity
# cap?" are answered -- no and no -- without re-running the search.
#
# **What the mirrors were.**  Recorded because it is a real property of the
# space and would otherwise be rediscovered the hard way.  The codes pair up:
# for four of the five there is a string answering a state at ``cell7 == 1``
# exactly where the setter answers it at ``cell7 == 0``, and the mirror is
# mechanically just "flip cell 7" -- run a pair on one state and the tapes
# agree everywhere else.  The mirrors are even *derivable*, by appending a
# member of the family ``'[' * k + '<'``: ``k == 4`` serves the setters ending
# at cell 5 and ``k == 6`` those ending at cell 4.
#
# Exactly those two ``k`` work, measured over ``k`` in 1..10, and the reason is
# not parity -- 2, 8 and 10 fail as surely as the odd ones.  The flip has to
# leave cell 7 *set* and still stop where the remaining walk preserves the
# pool.  For the setter ending at cell 5, ``k`` of 1, 3, 5 and 6 all leave the
# pool correct but with cell 7 clear, which is the wrong orientation, and
# ``k >= 7`` overshoots the walk entirely.
#
# The same fact rules out a uniform rule and explains the ordering below.  The
# codes finish at four different pointer positions (1, 2, 4, 5), so "flip cell
# 7 from where I stopped" depends on where that is.  Nor can the pointer be
# normalised first: ``'<<<<<'`` lands every code on cell 0 and ``<`` never
# writes, yet it destroys them -- the walk out is ``[x`` repeated from wherever
# the code stopped and every ``[x`` rewrites the cell it crosses, so moving the
# end left lengthens the walk and scribbles over the pool just set.  Measured
# on one site: the tape at the end of the code is identical either way, but a
# 3-step walk leaves ``0011000`` and an 8-step walk leaves ``0101110``.  A pool
# code therefore sets the pool *and* stops where the remaining walk will
# preserve it, and the four end positions are each paired with the walk
# lengths they must survive.
#
# Ordered shortest first, so the emitted program is no longer than before.
#
# The list is deliberately not minimal, and the trim was measured rather than
# left open.  Ablated one at a time with the searches stubbed, three of the
# five are load-bearing -- dropping the third, fourth or fifth strands 22, 18
# and 10 tables.  The first two strand nothing, and removing both keeps every
# table correct while cutting the build from 10.7s to 7.1s, which is the trap:
# it also pushes eight tables off :func:`_reconverged` onto a route that cannot
# sort their slots, taking the out-of-name-order count from ten to eighteen.
# Coverage and correctness are the loud properties and slot order is the quiet
# one, so all five stay.  ``test_dropping_a_pool_code_is_measured_not_assumed``
# pins that, and will say so if the slot-order cost ever disappears.
def _step(carry: int = 1, backs: int = 1, *, odd: bool = True) -> str:
    """One step of a pool code: carry a mark right, then walk the pointer back.

    This is the ``ceil(k / 2)`` law inverted.  A run of ``k`` brackets carries
    a mark right by ``ceil(k / 2)`` and leaves a pending skip when ``k`` is
    odd, so asking for a carry of ``c`` fixes the run at ``2 * c - 1`` when
    the skip is wanted and ``2 * c`` when it is not.  The trailing ``<`` runs
    set how far behind the mark the pointer ends up, which is the second free
    variable: the carry is clean only from just left of the mark.
    """
    return "[" * (2 * carry - odd) + "<" * backs


# Each plan is ``(steps, core, overrides)``: how many steps the code walks,
# which one is the core, and the steps that are not the default.  A default
# step carries the mark one cell and leaves the pointer one behind it; the
# core carries two.  Two of the five need no override at all -- they are the
# construction indexed by where the mark goes, and nothing else.
#
# An override is ``(backs, odd)`` for the step it names, so the two free
# variables stay visible side by side.
#
# **Why these values, and not a shorter description.**  The plans do not
# compress further, which was measured rather than assumed.  ``core`` is not
# derivable from the finished code: on a blank tape every plan with
# ``core > 0`` ends at ``mark = steps + 1`` and ``pointer = steps`` whatever
# the core's index -- verified for ``steps`` 1 to 40 -- so the blank-tape
# outcome cannot pick it.  It is pinned on live states instead, and the two
# properties split the way they do for the codes themselves.  Moving the core
# strands tables at every alternative for three of the plans -- 22 for the
# third, 18 for the fourth, 6 for the fifth -- which for the third and fourth
# is exactly what dropping those codes outright costs.  The second plan's core
# strands nothing at any alternative and is pinned by the quiet property
# instead: slot order goes from 10 out-of-name-order templates to 18, the same
# cost the ablation records for the non-stranding codes.
#
# Only the first plan's core moves freely, and that is not a fact about the
# core.  That code answers no site at ``n <= 3`` at all -- it is one of the two
# the ablation finds strands nothing -- so every spelling of it looks free at
# the arity being measured.  The two spellings are genuinely different
# functions, leaving marks at cells 1, 2, 4 against a single mark at 3.
_PLANS: tuple[tuple[int, int, dict[int, tuple[int, bool]]], ...] = (
    (2, 0, {1: (4, True)}),
    (4, 1, {}),
    (5, 2, {}),
    (5, 3, {0: (2, True)}),
    (5, 3, {2: (2, True), 4: (3, False)}),
)


def _render(steps: int, core: int, overrides: dict[int, tuple[int, bool]]) -> str:
    """Spell one plan out as a pool code."""
    codes = []
    for i in range(steps):
        backs, odd = overrides.get(i, (1, True))
        codes.append(_step(carry=2 if i == core else 1, backs=backs, odd=odd))
    return "".join(codes)


_POOL_CODES = tuple(_render(*plan) for plan in _PLANS)


def _pool_reaches(j: _Joint, code: str, cell7: int, walk_out: int) -> bool:
    """Whether ``code`` leaves the pool correct once walked out.

    The pool must read ``0011000`` plus ``cell7`` at print time, and the walk
    out to the accumulator crosses it -- so what matters is the pool *after*
    that walk, not at the moment the code ends.
    """
    target = (*_POOL, cell7)
    probe = [m.copy() for m in j.ms]
    for char in code:
        for m in probe:
            m.exec(char)
    if any(m.dead or m.skip for m in probe):
        return False
    if len({m.ptr for m in probe}) != 1:
        return False
    steps = walk_out - probe[0].ptr
    if steps < 0:
        return False
    for _ in range(steps):
        for char in "[x":
            for m in probe:
                m.exec(char)
    for cell in range(8):
        col = {m.tape[cell] for m in probe}
        if len(col) != 1 or probe[0].tape[cell] != target[cell]:
            return False
    return True


# What :func:`_find_pool_cached` probes with.  The verdict is invariant in
# the walk out (measured over 9..39, no ``(site, code)`` pair changes answer),
# so the search needs *a* value and not the caller's; naming one here is what
# lets the memo key omit it.  The smallest legal accumulator, since
# :func:`_endgame` rejects anything under 8 and the probe should sit where
# every caller's does or further left.
_PROBE_WALK_OUT = 9


@cache
def _find_pool_cached(
    site: tuple[tuple[object, ...], ...],
    cell7: int,
    codes: tuple[str, ...],
) -> str | None:
    """:func:`_find_pool` keyed on the joint's state, memoised.

    The search is the build's hot spot -- it walks every pool code through
    every row of the joint, and re-running it is most of what a derivation
    would otherwise spend its time on.  Almost all of it is repeated, because
    the same joint state is reached from many plans: at four inputs, 474170
    hits against 8390 misses, a 98.3% hit rate.

    (The "56 million ``_Sim.exec`` calls" and "30167 calls to 572 sites" this
    docstring used to quote were measured when ``walk_out`` was still in the
    key, so they describe a memo that was splitting entries -- kept out of the
    numbers above rather than carried forward as though they still held.)

    ``walk_out`` is *not* a parameter, which is the whole point -- see
    :func:`_find_pool` for why the verdict does not depend on it.  It was one
    once, and that silently halved the memo: the verdict is invariant in
    ``walk_out`` but the key was not, so every accumulator split one entry
    into many.  The hit rate ran at 50% while this docstring claimed 98%, and
    dropping ``walk_out`` from the key took the whole four-input derivation
    from 330s to 76s and the three-input one from 6.6s to 2.4s, with every
    template byte-identical.  A cache key that disagrees with the prose is worth
    more than a comment: this now takes only what the answer depends on, so
    the two cannot drift apart again.

    The search still needs *a* ``walk_out`` to probe with, and by the same
    invariance any will do, so the miss path uses :data:`_PROBE_WALK_OUT`.
    That is not a default standing in for the caller's value -- it is the
    statement that the value cannot matter, which the invariance measurement
    backs and :func:`_find_pool` documents.

    ``codes`` *is* in the key, and is the reason this takes the list as an
    argument rather than reading the module global.  The pool codes are
    ablated -- dropped one at a time to measure what each is worth -- and a
    memo that outlived a swap would answer for a list that is no longer in
    force, reporting that a dropped code stranded nothing because the old
    answer was still cached.
    """
    j = _Joint.__new__(_Joint)
    j.ms = [_Sim.restore(k) for k in site]
    for code in codes:
        if _pool_reaches(j, code, cell7, _PROBE_WALK_OUT):
            return code
    return None


def _find_pool(j: _Joint, cell7: int, walk_out: int) -> str | None:
    """Return a pool code for this orientation, or None if none fits.

    ``walk_out`` decides whether a code is *asked*, not whether it fits: the
    verdict is invariant in it.  Measured over walk_outs 9 to 39, no
    ``(site, code)`` pair changes answer -- 0 of 1000 at four and eight rows,
    0 of 300 at sixteen.  That follows from the affine picture, since cells
    0..7 after the walk depend only on what was crossed before them, and it
    is why arity reaches the pool codes only through the joint's rows and
    window state rather than through how far right the accumulator sits.

    That invariance is what lets the memo below drop ``walk_out`` from its
    key: two calls differing only in it are the same question.  ``walk_out``
    is therefore accepted and not forwarded -- it stays in the signature
    because callers reason in terms of their own accumulator, and dropping it
    would push the invariance argument out to every call site.
    """
    del walk_out
    return _find_pool_cached(tuple(m.key() for m in j.ms), cell7, tuple(_POOL_CODES))


def _endgame(j: _Joint, acc: int, read: str, cell7: int) -> None:
    """Set the pool, relay ``acc`` into the pointer, and print one digit.

    The walk back to the pool is measured from the read's *entry*: a
    constant-1 column diverges every row alike, so the pointer's minimum sits
    one cell further right than for a column with a zero row, and measuring
    from there would short the walk by one.
    """
    if acc < 8:
        raise ValueError("accumulator must sit past the pool")
    code = _find_pool(j, cell7, acc - 1)
    if code is None:
        raise ValueError("no pool pattern for this orientation")
    j.emit(code)
    _walk_to(j, acc - 1)
    j.emit(read)
    j.emit("<" * (acc - 7))
    # ``_find_pool`` accepts a code only after checking the pool *past* the
    # walk out, which is the state reached here -- so this is that check
    # restated on what was actually emitted rather than on a simulated walk.
    # It is an AssertionError rather than a ValueError deliberately: the two
    # disagreeing is a bug in the pair, and ``_try_print`` swallows every
    # ValueError, which would turn it into a silently skipped accumulator.
    for cell in range(8):
        if len(set(j.col(cell))) != 1:
            raise AssertionError(f"pool cell {cell} is input-dependent")
    j.emit("[x.")


def _complement(column: tuple[int, ...]) -> tuple[int, ...]:
    """Flip every row of a column."""
    return tuple(1 - bit for bit in column)


# Derived columns, keyed by ``(template, accumulator, orientation)``.  A plain
# dict rather than ``lru_cache`` because the key is computed from the mutable
# ``_Joint`` rather than being its arguments, and because ``None`` is a real
# answer here -- the sentinel keeps it distinguishable from a miss.
#
# ``_derived_plans.cache_clear`` empties this too, because a caller asking for
# a cold derivation means a cold one: tests harvest ``_find_pool`` call sites
# from a build and assert they saw hundreds, which a warm column cache cuts to
# seventeen.  Clearing the plan cache alone would leave that trap in place.
_PRINTED_COLUMNS: dict[tuple[str, int, int], tuple[int, ...] | None] = {}
_MISSING = object()


def _printed_column(j: _Joint, acc: int, cell7: int) -> tuple[int, ...] | None:
    """Return what the ``'[x<[<'`` read prints here, without printing it.

    The endgame is not a search: what it prints is fixed by the tape once the
    pool is set and the walk has run.  Emitting the pool code and walking to
    ``acc - 1`` leaves the pointer one cell short of the answer, and the read
    then reports the cell at ``ptr + 1`` -- directly for ``'[x<[<'`` and
    complemented for ``'[<'``, which is the only difference between the two.
    So one walk yields both reads' columns, and neither has to be run.

    This is the same value :func:`_endgame` would print, derived rather than
    observed.  Checked against it over every ``(separator, settle, bracket
    run, accumulator, orientation)`` at two, three and four inputs: 15600
    columns, no disagreement.  :func:`_confirm` re-checks each one that is
    actually used, so a divergence would surface as a miss rather than as a
    wrong program.

    Returns None when this orientation has no pool pattern or the walk cannot
    reach, which are the two conditions :func:`_endgame` raises on.

    Memoised on the staging's own template, because what this derives does not
    depend on which tables are wanted: the whole-arity spelling computes each
    column once and matches it against every table, while the table-major one
    would recompute the identical column for every build.  Measured at three
    inputs, the enumeration visits 12612 distinct ``(staging, accumulator,
    orientation)`` triples however many tables are asked for -- 8 builds make
    46790 calls and 40 make 206488, both over that same 12612 -- so the cache
    is what lets asking per table cost what asking for the arity does.
    """
    key = (j.template(), acc, cell7)
    hit = _PRINTED_COLUMNS.get(key, _MISSING)
    if hit is not _MISSING:
        return hit  # type: ignore[return-value]
    code = _find_pool(j, cell7, acc - 1)
    if code is None:
        _PRINTED_COLUMNS[key] = None
        return None
    probe = j.fork()
    probe.emit(code)
    try:
        _walk_to(probe, acc - 1)
    except ValueError:
        _PRINTED_COLUMNS[key] = None
        return None
    column = tuple(probe.col(probe.ms[0].ptr + 1))
    _PRINTED_COLUMNS[key] = column
    return column


def _confirm(
    j: _Joint, acc: int, read: str, cell7: int, column: tuple[int, ...]
) -> bool:
    """Whether the endgame really prints ``column`` here.

    The derivation above settles which accumulator answers a table; this runs
    the endgame that was chosen and checks it, so nothing is recorded on the
    strength of the algebra alone.  It is the same standard the enumeration
    has always applied -- a staging is accepted on the evidence of its own
    output -- narrowed to the accumulators that are about to be used.

    :func:`_endgame` also asserts the pool is input-independent, a side
    condition the derivation does not model; a failure there is a bug in the
    pair rather than a miss, so it is left to propagate.
    """
    probe = j.fork()
    try:
        _endgame(probe, acc, read, cell7)
    except ValueError:
        return False
    printed = probe.printed()
    if any(len(digit) != 1 for digit in printed):
        return False
    return tuple(int(digit) for digit in printed) == column


def _try_print(j: _Joint, truth_table: str, acc: int) -> _Joint | None:
    """Try every read and orientation at ``acc``; return one that prints."""
    for read in _READS:
        for cell7 in (0, 1):
            probe = j.fork()
            try:
                _endgame(probe, acc, read, cell7)
            except ValueError:
                continue
            if probe.printed() == list(truth_table):
                return probe
    return None


def _find_column(
    j: _Joint, target: tuple[int, ...], window: int, maxlen: int
) -> tuple[str, int] | None:
    """Find code after which some cell holds ``target`` (or its complement)."""
    comp = tuple(1 - v for v in target)

    def accept(new: list[_Sim], code: str) -> tuple[str, int] | None:
        for cell in range(1, window):
            col = tuple(m.tape[cell] for m in new)
            if col in (target, comp):
                return code, cell
        return None

    return _search(j, accept, maxlen)


def _find_parked(
    j: _Joint, target: tuple[int, ...], window: int, maxlen: int, limit: int
) -> list[tuple[str, int]]:
    """Find states holding ``target`` with the pointer parked to read it.

    Producing the column is not enough on its own: walking back to it
    re-crosses, and so changes, the very cell.  Requiring the pointer to sit
    immediately left of the answer removes that walk, and several candidates
    are collected because which one survives the endgame is decided by
    running it, not by predicting it.
    """
    comp = tuple(1 - v for v in target)
    hits: list[tuple[str, int]] = []

    def accept(new: list[_Sim], code: str) -> list[tuple[str, int]] | None:
        ptrs = {m.ptr for m in new}
        if len(ptrs) != 1:
            return None
        cell = ptrs.pop() + 1
        if not 8 <= cell < window:
            return None
        col = tuple(m.tape[cell] for m in new)
        if col in (target, comp):
            hits.append((code, cell))
            if len(hits) >= limit:
                return hits
        return None

    return _search(j, accept, maxlen) or hits


# The columns a degenerate table can be built from: a constant, one of the
# first two inputs, or one of their complements.  A table depending on at
# most one input is exactly one of these, which is why naming them is enough.
_DEGENERATE_COLUMNS = ("const1", "~b0", "b0", "const0", "~b1", "b1")


def _column_of(name: str, n: int) -> tuple[int, ...] | None:
    """Return the column ``name`` stands for, or None if this arity has no such bit.

    ``b1`` does not exist at one input, and it must come back as None rather
    than as some default: an all-zero stand-in would match wherever
    ``const0`` does, and the route would carry a duplicate cell that means
    nothing.
    """
    rows = range(2**n)
    if name in ("const0", "const1"):
        return tuple(int(name == "const1") for _ in rows)
    negated = name.startswith("~")
    bit = int(name.lstrip("~")[1:])
    if bit >= n:
        return None
    return tuple((((r >> (n - 1 - bit)) & 1) ^ negated) for r in rows)


@cache
def _degenerate_cells(n: int) -> dict[str, int]:
    """Find where the embed leaves the constants and the first two inputs.

    These were six written-down cell numbers, and the reason they were
    constant is also the reason they need not be written down: the carry
    chain preserves ``b0`` and ``b1`` individually before the prefix-XOR
    starts mixing, so the cells holding them can simply be *read off* the
    embedded tape.  Measured, this reproduces the six exactly at every arity
    the route serves.

    Later inputs are not separable here at any settle count -- the affine
    transform fixes which bits stay apart -- but a column search finds them
    in a fraction of a second, which is why the degenerate path still beats
    the ladder without being wholly search-free.

    Only the default settle count is meaningful: :func:`_degenerate` embeds
    with it, and re-crossing the region moves these columns elsewhere.
    """
    joint = _embed(n, sep=_SEP)
    _clamp(joint)
    wanted = {
        name: column
        for name in _DEGENERATE_COLUMNS
        if (column := _column_of(name, n)) is not None
    }
    found: dict[str, int] = {}
    for cell in range(1, _BASE + n * _SPAN + 8):
        column = joint.col(cell)
        for name, target in wanted.items():
            if name not in found and column == target:
                found[name] = cell
    return found


def _degenerate(
    truth_table: str, n: int, *, fixed_cells_only: bool = False
) -> str | None:
    """Build a table depending on at most one input, without the ladder.

    Such a table is a constant, a projection, or a negated projection, and
    every one of those already stands as a *column* somewhere after the
    embed -- at a known cell for the first two inputs, and at a cheaply
    searched one beyond that.  So the whole construction is: find the cell
    holding the answer, then run the endgame on it.

    This is the piece that composes upward: a table with ``k`` essential
    inputs is a ``k``-input problem whatever its arity, so four of the
    fourteen three-input orbits are handled here for free.

    ``fixed_cells_only`` stops after the six known cells, skipping the column
    search.  That is for the caller who has a working fallback and wants a
    cheap *attempt* rather than an answer: the search costs about five
    seconds to fail at ``n == 3`` and the lookup under one, and every table
    the name-order caller below wins is won at the lookup.
    """
    want = tuple(int(c) for c in truth_table)
    base = _embed(n, sep=_SEP)
    _clamp(base)

    # The fixed cells first, then a search for the rest.
    candidates = list(_degenerate_cells(n).values())
    for acc in candidates:
        hit = _try_print(base, truth_table, acc)
        if hit is not None:
            return hit.template()

    if fixed_cells_only:
        return None

    probe = _embed(n, sep=_SEP)
    _clamp(probe)
    _walk_to(probe, _BASE - 1)
    found = _find_column(probe, want, _BASE + n * _SPAN + 14, _COLUMN_DEPTH)
    if found is None:
        return None
    probe.emit(found[0])
    _clamp(probe)
    for acc in range(9, _BASE + n * _SPAN + 14):
        hit = _try_print(probe, truth_table, acc)
        if hit is not None:
            return hit.template()
    return None


def _project(truth_table: str, essential: list[int], n: int) -> str:
    """Rewrite the table over its essential inputs only.

    A table that ignores some of its inputs is a smaller table wearing extra
    ones.  Reading it at the essential positions gives that smaller table,
    which is a ``len(essential)``-input problem however wide the original was.

    The read itself is :func:`read_at`, shared with
    :func:`permute_truth_table` -- a permutation is the case where every
    input is essential, so nothing is held back.
    """
    return read_at(truth_table, essential, n)


# How far to search for a reconverging reset, and how many to try.  The
# first one is found at length 12 and is the one that builds, but the cap is
# a little higher so the search is not pinned to that exact string.
_RESET_DEPTH = 13
_RESET_LIMIT = 4


def _find_reset(ignored: int, maxlen: int = _RESET_DEPTH) -> list[str]:
    """Find code after which the ignored inputs leave no trace.

    The setters for the inputs a table ignores still have to be emitted --
    the harness has a bit for every input -- and emitting them first is what
    keeps the placeholders in name order.  They do write the tape, though,
    so what follows must erase the difference: this searches for a suffix
    after which all ``2**ignored`` rows are in *identical* states.

    Identical, not blank.  A blank tape is unreachable -- the all-ones row
    ends a cell to the right of the others and ``<`` clamps without writing,
    so the rows cannot be driven back to the origin together -- but they can
    be driven to a common non-blank state, which is all the rest of the
    construction needs.
    """
    j = _Joint(ignored)
    for i in range(ignored):
        j.emit_setter(i)
    hits: list[str] = []

    def accept(new: list[_Sim], code: str) -> list[str] | None:
        if len({m.key() for m in new}) != 1:
            return None
        hits.append(code)
        return hits if len(hits) >= _RESET_LIMIT else None

    _search(j, accept, maxlen)
    return hits


def _reconverged(truth_table: str, essential: list[int], n: int) -> str | None:
    """Build by emitting the ignored inputs first, then erasing them.

    ``_lift`` puts the ignored placeholders last, which leaves name order.
    The alternative is to emit them *first* -- ``{X0}``..``{Xn-1}`` stays
    ascending -- and then reconverge the rows so nothing downstream can tell
    which bits they were.  After that the table is a one-input problem in its
    single essential input, and the rest is the embed geometry every other
    degenerate table uses.

    The walk to ``_BASE - 1`` before the essential setter is what makes this
    cheap rather than a fresh search: it reproduces the standard embed, so
    the essential input lands on the cells :func:`_degenerate_cells` finds,
    and the fixed-cell lookup decides in a fraction of a second.  The
    junk the reset leaves behind is not a problem -- the rows are identical
    by then, so it is a constant starting condition, which is exactly what
    the searches here are built to run from.
    """
    if not 1 <= len(essential) <= 2:
        return None
    ignored = [i for i in range(n) if i not in essential]
    if ignored != list(range(len(ignored))):
        # The ignored inputs have to be the *leading* ones for emitting them
        # first to keep the order ascending.
        return None

    # Where to look for the answer once the ignored inputs are gone.  One
    # essential input leaves a projection, which stands at a known cell; two
    # leave a two-input table, which has a staging of its own -- so replay
    # that staging and read its own accumulator rather than scanning.  The
    # scan is what costs: at two essential inputs it turns a 0.5s build into
    # seconds without reaching anything the staging does not.
    if len(essential) == 1:
        setup: tuple[int, int, int, int] | None = None
        accumulators: tuple[int, ...] = tuple(_degenerate_cells(n).values())
    else:
        inner = _project(truth_table, essential, n)
        plan = _derive_staging(inner, 2)
        if plan is None:
            return None
        sep_index, settle, brackets, acc = plan
        # Every two-input staging is a plain bracket run; the literal-suffix
        # form is only used by the one stored three-input exception, and
        # replaying it here would need the walk this route does not make.
        if not isinstance(brackets, int):
            return None
        setup = (sep_index, settle, brackets, acc)
        accumulators = (acc,)

    for reset in _find_reset(len(ignored)):
        j = _Joint(n)
        for i in ignored:
            j.emit_setter(i)
        j.emit(reset)
        if len({m.key() for m in j.ms}) != 1:
            continue
        _walk_to(j, _BASE - 1)
        if setup is None:
            j.emit_setter(essential[0])
            j.emit("[x")
        else:
            sep_index, settle, brackets, _acc = setup
            for slot, i in enumerate(essential):
                j.emit_setter(i)
                j.emit("[x")
                if slot + 1 < len(essential):
                    j.emit(_SEPS[sep_index])
            # The staging's settle count, replayed the way ``_embed`` does
            # it: re-crossing the bit region advances the affine state, and
            # the accumulator was chosen against the state that produces.
            # The enumeration hands back ``settle == 1`` for AND and NAND,
            # and six three-input tables project onto one of those, so
            # ignoring the field would replay them against the wrong tape.
            for _ in range(settle):
                _clamp(j)
                _walk_to(j, _BASE - 1)
            _clamp(j)
            _walk_to(j, _BASE - 1)
            j.emit("[" * brackets + "<")
        _clamp(j)
        for acc in accumulators:
            hit = _try_print(j, truth_table, acc)
            if hit is not None:
                return hit.template()
    return None


# The staged construction: one ``(separator, settle, suffix, accumulator)``
# per complement pair, *derived* rather than stored.
#
# The embed leaves an affine picture -- every cell holds a linear form in the
# input bits plus the one nonlinear term the ``[`` cascade computes -- and a
# plain run of ``k`` brackets from ``_BASE - 1`` sweeps that picture forward,
# exposing a different function at each step.  So the whole problem is: pick
# the separator, the bracket count and the accumulator, then hand the result
# to the endgame every other route already uses.
#
# Which is small enough to *enumerate*.  :func:`_stagings` gives the order --
# 5 separators x 2 settle counts x 29 bracket counts x 26 accumulators -- and
# a table is built by the first entry that prints it, so no table of answers
# is needed.
#
# :func:`_derived_plans` runs that enumeration for a whole arity at once,
# which is what makes it affordable.  A staging is expensive to build and
# cheap to test against a table, so the loops go staging-major: one embed per
# (separator, settle), the bracket run extended one instruction at a time,
# and the endgame emitted once per (k, accumulator, read, orientation)
# whatever the table.  Measured, the whole three-input arity derives in 2.4s
# and two inputs in 0.15s; the table-major spelling of the same search costs
# minutes, because it rebuilds every staging once per table.  (Those two were
# 15s and 0.9s when this was written and are re-measured here rather than
# carried forward -- a timing in prose ages against every change under it.)
#
# What the three-input arity spends that on is 127 distinct stagings, spread
# over all five separators -- 34, 29, 37, 23 and 4 of them -- and both settle
# counts, 94 at zero and 33 at one.  The load is nowhere near even, and
# separator 4 carrying four stagings is the reason the list is not trimmed on
# a glance at how often each is named.
#
# Selection is on the accumulator's value **at the read**, not on the cell
# that holds the answer beforehand.  Those differ, because the walk out
# applies the running prefix-XOR: at ``acc = 22`` after separator 1, AND
# ``(0,0,0,1)`` arrives as the constant ``(1,1,1,1)``, and XOR ``(0,1,1,0)``
# arrives as ``b1``.  Choosing on the pre-walk column is what made an earlier
# version of this cover 10 of the 16 two-input tables rather than all of them.
# The enumeration sidesteps that trap by construction: it does not reason
# about which column *ought* to arrive, it emits the endgame and reads what
# the rows actually printed.
#
# A table and its complement share a staging, because the endgame tries both
# read polarities and both pool orientations and the printed digit is
# ``NOT(v XOR cell7)``, so the complement costs nothing to reach.  That is
# why the counts below are given in complement pairs.
_Staging = tuple[int, int, int | str, int]

# **Coverage, and the one table that must still be stored.**  The enumeration
# reaches 108 of the 109 non-degenerate three-input pairs and all 8 at two
# inputs.  The holdout is ``01101101`` / ``10010010``, and it is worth knowing
# why, because it was the hardest table here by some margin and the searches
# never built it at all -- both members raise after about 96 seconds.
#
# Its answer column is not scarce: 14375 of 804600 sparse suffixes leave it
# standing somewhere on the tape.  What is scarce is a staging that also
# *carries* it to the read, because the walk's prefix-XOR rewrites the very
# cell.  A pure bracket run never manages it -- which is exactly why the
# enumeration cannot reach it, every entry of :func:`_stagings` being a run --
# and the stored suffix interleaves two ``<`` into the run instead.
#
# The shape of that miss is worth recording so it is not re-run blind.  Unlike
# the tables the wider separator set closed, its answer *is* computed:
# ``01101101`` stands as a column at cell 24 under separator 2 at ``k == 15``.
# What fails is the carry -- no accumulator reads it intact, and from that
# staging it arrives as ``10011101`` or ``01100010``, neither the table nor
# its complement.  A sweep over 13 of the 15 (separator, settle) slices at
# ``k <= 40`` and every accumulator found no staging that delivers it; the two
# skipped slices scored worst on a cheap distance screen, and the five that
# scored best -- reaching Hamming distance 1 but never 0 -- were all covered
# and all missed.
#
# It is a gap in this family, not a wall: 180 of the 256 possible columns
# arrive across the family, and no affine invariant separates them from this
# one (all 255 parity masks checked), so nothing here forbids it.
#
# What closed the *other* gaps was not a better search but a wider separator
# set.  See the note on :data:`_SEPS`: the first two separators leave only 92
# distinct columns standing, and 112 of the 120 tables the searches could not
# reach did not stand as a column at all.  Three more separators carry 118 of
# those 120, every one of which builds, computes and emits in name order.
#
# The bracket axis is *exhausted*, not capped, and that is checkable rather
# than assumed.  Nothing in this language writes leftward -- ``[`` writes at
# ``ptr + 1`` and, on the cascade, ``ptr + 2``, and the pointer only ever
# advances -- so once every row's pointer has passed the accumulator window,
# no further bracket can change a staged column.  Measured, the columns stop
# changing between ``k == 25`` and ``k == 38`` depending on separator and
# settle count, so the sweep ran to 40 and anything past it is provably
# redundant.  The deepest first hit the enumeration actually needs is
# ``k == 26`` at three inputs and ``k == 6`` at two, which is where
# :data:`_MAX_BRACKETS` comes from; stopping at 30 would have been a cap
# rather than a bound.
#
# The other two axes were *sampled* rather than exhausted and came back
# empty -- settle counts 3 to 5 and accumulators 36 to 47 reached nothing the
# shipped stagings did not.  That is evidence they are barren, not proof.
#
# **A simpler form was looked for and does not exist.**  This is what the
# enumeration replaced a stored table with, and not what it could have been:
# the wish was a *uniform* rule -- one staging, or at least one field fewer --
# even at the cost of longer programs.  Every version of that was measured and
# fails, which is why all four fields are still enumerated:
#
# * **One fixed staging: impossible**, and by counting rather than by search.
#   A staging offers one column per accumulator and orientation -- 52 slots
#   over the ranges used here -- but those collapse badly, because the walk's
#   prefix-XOR is many-to-one and different accumulators keep arriving at the
#   same column.  Measured over every staging in the family, **the best
#   single one delivers 13 pairs and the mean is 5.8**, against 109 to place.
#   So this is short by a factor of eight, not marginally.
#
#   Nor can the enumeration be *indexed* instead of swept -- the map from
#   staging to table behaves like a hash.  Measured on the full many-to-many
#   relation (not on the first-hit assignment, which is contaminated by
#   separator 0 claiming everything it reaches first): at four inputs no
#   tested invariant yields a necessary condition, every one of the ten
#   (separator, settle) slices contributes tables reachable nowhere else,
#   and 72% of tables are served by exactly one slice.  Hamming weight does
#   predict a *rate* -- 78.4% reachable at weight 2 and 14 against 18.8% at
#   weight 8 -- but no weight class is empty, so nothing licenses declining
#   early.  See ``docs/walls.md``.
# * **Two separators: 99 of 109**, and *not* for want of room -- re-running
#   with bracket counts to 70 and accumulators to 60 reaches the same 99.
#   The ten stragglers need a different separator, not a longer program.
#   This is why :func:`_stagings` walks all five.
# * **Dropping the settle field: 99 of 109.**  Ten pairs are reachable only
#   at ``settle == 1``, so the staging cannot shrink to three fields.
#
# Separator 0 is the one curiosity: no *three-input* table needs it, since
# separators 1 to 4 reach 108 of the 109 between them.  It is enumerated
# first anyway because it carries every two-input table on its own, and
# :data:`_SEP` and :data:`_SCAN_SEPS` use it.
#
# Two more things look removable and are not.  ``_SETTLE`` is unused by the
# enumeration but parameterises the parked search, which still serves
# ``n >= 4``; and the searches themselves are unreachable at ``n <= 3`` yet
# are what a wider table falls through to.  Neither is dead.
#
# **What happens at four inputs.**  Four-input AND and NAND build in 0.2s and
# a table depending on one input in 2.4s -- all before the staging, by the
# degenerate and projection routes.  What the searches could not build was
# four-input XOR, and the diagnosis at the time was that the pool was fine
# and the search depth was the wall: XOR's failed attempt made 1016 pool
# lookups, 508 of them successful, the same one-in-two rate the three-input
# arity shows.
#
# That reading was right about the pool and incomplete about the wall.  XOR
# now builds from a staging, and the thing that had to change was neither the
# search nor the pool but the *suffix*: with ``'[' * k`` the only spelling
# available, the enumeration could not reach it.  See :data:`_STAGED_ARITIES`
# and :func:`_insert_suffixes`.  The searches remain what the other 76% of
# the arity falls through to, and the depth is still their limit.
#
# Which code answers does shift with arity, which is worth knowing before
# trimming the list on three-input evidence.  On the four-input tables measured
# here, sixteen-row joints were served by the third and fifth codes, and the
# fifth answers almost nothing below four inputs -- so an ablation at
# ``n <= 3`` under-reports what it is for.  The split is table-dependent and
# the sample is small: the sites from a four-input AND were answered by the
# fifth code alone, while the failing XOR's were answered by both.  Take this
# as "arity changes which code answers", not as a census.

# The arities the enumeration covers.  Two and three are *total*; four and
# five are partial, and are here because partial beats the fall-through each
# replaces.  Beyond five the gate stays explicit rather than implied by a
# miss: it is not that the enumeration is known to fail there, but that it
# has not been shown to succeed, and this list is the place that claim is
# made.
#
# Five was gated shut on exactly that wording until the family was harvested
# at that arity, which is the measurement that opened it: 24582
# fully-essential 32-bit columns, complement-closed, five-input XOR among
# them.  It is a 0.00057% slice rather than four inputs' quarter, and it
# ships on the same argument -- a miss falls through, so admitting the arity
# cannot cost coverage.  The one thing that had to change to make it runnable
# at all is that :func:`_derived_plans` is asked for the tables it wants
# rather than for the whole arity.
#
# Four inputs is gated on measurement rather than hope: the insert family
# below reaches 15404 of the 64594 fully-essential four-input tables (23.9%),
# four-input XOR among them -- the table the searches are recorded as failing
# on.  A table the derivation misses still falls through to the searches, so
# admitting the arity cannot cost *coverage*.
#
# What it costs is time, and the shape of that cost is worth stating plainly
# because it is unlike the other arities.  At two and three inputs the
# derivation stops early: every table is placed, so ``remaining`` reaches
# zero partway through.  At four it never can -- 76% of the arity is
# unreachable -- so the enumeration always runs to its caps, measured at
# about 76 seconds.  That is paid by the first fully-essential four-input
# table in a process whether it hits or misses, and :func:`_derived_plans` is
# cached, so it is paid once.  Constants, projections and any table with an
# ignored input are answered by the degenerate and projection routes in
# :func:`minifuck` before the staging is consulted at all, and never pay it.
#
# The caps are not slack that could shorten this.  Coverage climbs to both of
# them -- suffixes to ``k == 28`` and accumulators to 34 -- with 12256 tables
# at ``k <= 24`` against 15404 at 28, so a trim to buy time is a trim to
# coverage.  ``_stagings`` takes ``n`` for arity-dependent caps; measurement
# says this arity wants the full ones.
_STAGED_ARITIES = (2, 3, 4, 5)

# How far the enumeration runs.  Both caps are the measured maximum over
# every table plus a margin, not guesses: sweeping to a bracket count of 30
# and an accumulator of 40, the deepest first hit at two inputs is
# ``(k=6, acc=20)`` and at three ``(k=26, acc=31)``.  Nothing is reached past
# those, so the sweep stops a little beyond them.
_MAX_BRACKETS = 28
_MAX_ACC = 34

# How much of the enumeration a caller is willing to spend, counted in
# **stagings visited** rather than in seconds.
#
# The unit is the point.  A wall-clock budget would make the generator
# non-deterministic across machines: the same table would build on a fast
# host and raise on a slow one, and the template a table gets would depend
# on how loaded the box was.  A staging is one ``(separator, settle,
# suffix, accumulator)`` tuple in :func:`_stagings` order, so counting them
# is identical everywhere -- a budget picks out the *same* set of tables on
# a Raspberry Pi and on an M3, and the emitted programs stay byte-identical.
# The count also tracks real work, since :func:`_printed_column` memoises
# what a staging derives, making a visited staging roughly a constant unit.
#
# **A budget costs program length, not coverage.**  A table the budget stops
# short of falls through to :func:`_mux`, which is total at four inputs at
# about 11ms -- so lowering this cannot make a table unbuildable.  What it
# trades is the staged route's much shorter template (measured at four
# inputs: 205 characters against the sculpted route's 952) for the tables it
# gives up.  That is why a slow host can lower it safely.
#
# ``None`` means no budget, which is what ships at four inputs and below:
# the default must reproduce the enumeration exactly there, or every
# recorded template changes.
_STAGING_BUDGET: int | None = None

# Five inputs is budgeted by default, and that is a different decision from
# the one above.  At four inputs a budget is an option a slow host may take;
# here it ships on, because the arity is *only* reached by tables the
# cheaper routes could not place and the enumeration cannot stop early on a
# miss.  Measured on a table the span screen admits: 54.7s unbudgeted, 12.6s
# at 30000 stagings, 3.5s at 8000 -- against 1.4s for five-input XOR, which
# still builds at 30000.  The value below keeps the flagship hits and takes
# the miss from a minute to seconds.
#
# What it gives up is tables that sit late in the enumeration, and they are
# given up to a *raise* rather than to a slower route, since nothing below
# this arity's staged family reaches them.  That is the trade being made
# deliberately: at five inputs the generator refuses quickly instead of
# building slowly, and the refused tables are unreached rather than
# unbuildable -- see ``docs/walls.md``.
_STAGING_BUDGET_N5 = 30000


def _budget(n: int) -> int | None:
    """Return the staging budget for this arity, in stagings visited."""
    if n >= 5 and _STAGING_BUDGET is None:
        return _STAGING_BUDGET_N5
    return _STAGING_BUDGET


# The ``(separator, settle)`` slices in descending measured yield at four
# inputs, which is what makes a budget worth having.  Every slice costs the
# same 12064 stagings, and what they return is not close to even -- 2874
# tables for the best against 424 for the worst -- so spending a budget in
# this order buys 77% of the hits for half the work, and 91% for 70% of it.
# Enumerating in the plain ``(sep, settle)`` order instead makes a budget a
# flat trade, since hits are spread uniformly through the enumeration.
#
# Measured at ``n == 4`` and **not** assumed to hold elsewhere: at another
# arity the ranking is unmeasured, so the full enumeration order is used
# unless a budget is actually set.  Ordering only matters when something is
# going to be given up.
_SLICE_YIELD_ORDER = (
    (3, 0),
    (2, 0),
    (3, 1),
    (2, 1),
    (4, 0),
    (4, 1),
    (0, 0),
    (0, 1),
    (1, 1),
    (1, 0),
)


def _slices(n: int) -> tuple[tuple[int, int], ...]:
    """Return the ``(separator, settle)`` slices, in the order to spend them.

    Plain enumeration order when there is no budget, so the shipped
    behaviour is exactly what it was.  Under a budget at the arity the
    ranking was measured at, yield order instead -- what is given up should
    be the slices that place the fewest tables.
    """
    plain = tuple(
        (sep_index, settle) for sep_index in range(len(_SEPS)) for settle in (0, 1)
    )
    if _budget(n) is None or n != 4:
        return plain
    return _SLICE_YIELD_ORDER


# The arities whose enumeration includes the insert family below.  It is not
# offered at two or three inputs because the pure runs already close those
# arities completely, and enumerating a family that can only be reached after
# every pure run has missed would cost those arities time for nothing.
_INSERT_ARITIES = (4, 5)


def _insert_suffixes() -> Iterator[str]:
    """Enumerate bracket runs with one ``<`` inside, shortest first.

    The pure runs the enumeration spells as ``'[' * k`` are one string per
    length; putting a single ``<`` at each interior position gives ``k + 1``
    per length instead, which is where the four-input coverage comes from.

    This is not a free search over the alphabet -- that is what cost 29
    minutes to find the three-input suffix this family generalises, back when
    it was stored rather than derived.  It is the smallest generalisation of
    the pure run that that suffix proves necessary: it interleaves ``<`` into
    its bracket run, so a family no wider than "the same run with a ``<`` in
    it" was already known to reach columns no ``'[' * k`` reaches.  A second
    A second ``<`` reaches further still; that family was removed once the
    sculpted route covered the one pair it served.
    What was not known, and what
    the measurement settled, is how *many*: at four inputs the pure runs
    reach 1650 fully-essential columns and this family reaches 15404.

    The order is by length and then by the ``<``'s position from the left, so
    it is as deterministic as the bracket count it generalises.
    """
    for k in range(_MAX_BRACKETS + 1):
        for cut in range(k + 1):
            yield "[" * cut + "<" + "[" * (k - cut)


def _stagings(n: int) -> Iterator[_Staging]:
    """Enumerate ``(separator, settle, suffix, accumulator)`` in order.

    The order is what makes the derivation deterministic, and it is chosen so
    the cheap stagings come first: separator, then settle, then the bracket
    run, then the accumulator.  A table is built by the *first* of these that
    prints it, so this order -- not a stored table -- is what fixes which
    program each truth table gets.

    At an arity in :data:`_INSERT_ARITIES` the pure runs are followed by
    :func:`_insert_suffixes`, in a second pass over the same separators and
    settles.  It is a second pass rather than an inner loop deliberately:
    every pure run is tried before any insert, so an arity the pure runs
    already close is assigned exactly the stagings it was assigned before the
    family existed.  Two and three inputs are unchanged, table for table.

    :func:`_derived_plans` does not call this: it interleaves the same loops
    with the machines it is advancing, so that a bracket count costs one
    instruction rather than a rebuild.  This states the order those loops
    implement, and the test suite checks the two agree.
    """
    for sep_index in range(len(_SEPS)):
        for settle in (0, 1):
            for brackets in range(_MAX_BRACKETS + 1):
                for acc in range(9, _MAX_ACC + 1):
                    yield sep_index, settle, brackets, acc
    if n not in _INSERT_ARITIES:
        return
    for sep_index in range(len(_SEPS)):
        for settle in (0, 1):
            for suffix in _insert_suffixes():
                for acc in range(9, _MAX_ACC + 1):
                    yield sep_index, settle, suffix, acc


def _replay(truth_table: str, n: int, plan: _Staging) -> str | None:
    """Build one staging and return its template, or None if it does not print.

    The suffix is a bracket *count* for the pure runs -- a plain run, which
    the ``<`` terminates so the pointer lands where the endgame expects --
    and a literal string for the insert families, which carry their own
    terminator.
    """
    sep_index, settle, suffix, acc = plan
    j = _embed(n, settle=settle, sep=_SEPS[sep_index])
    _clamp(j)
    _walk_to(j, _BASE - 1)
    j.emit("[" * suffix + "<" if isinstance(suffix, int) else suffix)
    _clamp(j)
    hit = _try_print(j, truth_table, acc)
    return hit.template() if hit is not None else None


@cache
def _derived_plans(n: int, targets: tuple[str, ...]) -> dict[str, _Staging]:
    """Derive a staging for the wanted tables, in one pass of the enumeration.

    A staging is expensive to *build* and cheap to *test against a table*: the
    embed, the bracket run and the endgame do not depend on which table is
    wanted, and only the comparison at the very end does.  So the loops run
    staging-major -- one embed per ``(separator, settle)``, the bracket run
    extended one ``[`` at a time rather than rebuilt, and the endgame emitted
    once per ``(k, accumulator, read, orientation)`` -- and each printed column
    is looked up among the tables still wanting one.

    ``targets`` narrows *what is being looked for* without changing the
    enumeration: the same loops, the same order, the same first-hit rule.  A
    table is assigned the first staging in :func:`_stagings` order that prints
    it, whatever else was asked for alongside it.

    This used to offer a whole-arity spelling as well, which pre-built
    ``wanted`` over all ``2 ** (2 ** n)`` tables so that one pass answered the
    entire arity.  That could not run at five inputs -- ``2**32`` entries --
    and it is no longer worth its place below five either: what made it faster
    was deriving each column once, and :func:`_printed_column` now memoises
    exactly that, so asking per table costs what asking for the arity did.
    Measured across the whole suite, the two spellings finish within a second
    of each other (105.1s against 104.2s), so the narrower one is the only one
    kept.

    Returns a mapping from truth table to staging.  A table that no staging
    reaches is simply absent, so the caller falls through to the searches.
    """
    if n not in _STAGED_ARITIES:
        return {}

    # What each printed column would answer.  A table and its complement
    # share a staging, so both spellings map to their own table and whichever
    # is reached first assigns both.
    wanted: dict[tuple[int, ...], list[str]] = {}
    for table in targets:
        wanted.setdefault(tuple(int(c) for c in table), []).append(table)
    remaining = sum(len(tables) for tables in wanted.values())

    found: dict[str, _Staging] = {}

    def claim(staged: _Joint, suffix: int | str, head: tuple[int, int]) -> bool:
        """Record what every accumulator prints, deriving it rather than printing.

        Returns whether every table has been placed, which is what stops the
        enumeration early.  Both passes below share this: the suffix is
        already emitted by the time it runs, so a bracket count and an insert
        string reach it the same way.

        What an accumulator prints is not searched for.  :func:`_printed_column`
        derives it in closed form from the tape the walk leaves behind, so an
        accumulator that answers no wanted table costs one walk and a dict
        lookup instead of a full endgame.  The two reads are not enumerated at
        all: they print complementary columns, so both are read off the one
        derivation.  Only an accumulator that *does* answer a wanted table
        pays for an endgame, and then only to confirm it -- see
        :func:`_confirm`.
        """
        nonlocal remaining
        for acc in range(9, _MAX_ACC + 1):
            for cell7 in (0, 1):
                derived = _printed_column(staged, acc, cell7)
                if derived is None:
                    continue
                for read in _READS:
                    column = derived if read == _READS[1] else _complement(derived)
                    for table in wanted.get(column, ()):
                        if table in found:
                            continue
                        if not _confirm(staged, acc, read, cell7, column):
                            continue
                        found[table] = (*head, suffix, acc)
                        remaining -= 1
            if not remaining:
                return True
        return False

    # Stagings visited, against :data:`_STAGING_BUDGET`.  Counted per
    # accumulator sweep rather than per emitted suffix, because a staging is
    # a ``(separator, settle, suffix, accumulator)`` tuple and ``claim``
    # walks the accumulators for one suffix in a single call.
    spent = 0
    budget = _budget(n)
    accs = _MAX_ACC - 8

    def exhausted() -> bool:
        return budget is not None and spent >= budget

    slices = _slices(n)

    for sep_index, settle in slices:
        if exhausted():
            return found
        base = _embed(n, settle=settle, sep=_SEPS[sep_index])
        _clamp(base)
        _walk_to(base, _BASE - 1)
        run = base.fork()
        for brackets in range(_MAX_BRACKETS + 1):
            staged = run.fork()
            staged.emit("<")
            _clamp(staged)
            if claim(staged, brackets, (sep_index, settle)):
                return found
            spent += accs
            if exhausted():
                return found
            # Extending the run is what makes this cheap: the next
            # bracket count is one instruction on from this one, not a
            # rebuild from the embed.
            run.emit("[")

    # The insert family, in a second pass so that every pure run is tried
    # first and the arities the pure runs close keep the stagings they had.
    # This pass cannot share the incremental trick above -- moving the ``<``
    # one place right is not one instruction on from the last suffix -- so
    # each string is emitted onto a fork of the embed.
    if n not in _INSERT_ARITIES:
        return found
    for sep_index, settle in slices:
        if exhausted():
            return found
        base = _embed(n, settle=settle, sep=_SEPS[sep_index])
        _clamp(base)
        _walk_to(base, _BASE - 1)
        for suffix in _insert_suffixes():
            staged = base.fork()
            staged.emit(suffix + "<")
            _clamp(staged)
            if claim(staged, suffix, (sep_index, settle)):
                return found
            spent += accs
            if exhausted():
                return found
    return found


def _clear_derived_plans(
    _wrapped: Callable[[], None] = _derived_plans.cache_clear,
) -> None:
    """Clear the plan cache and the derived columns it shares work with."""
    _wrapped()
    _PRINTED_COLUMNS.clear()


_derived_plans.cache_clear = _clear_derived_plans  # type: ignore[method-assign]


# The arities whose enumeration is worth screening before it is run.  Only
# five: the screen below is *vacuous* at four inputs and cheaper to skip than
# to evaluate.  See :func:`_span_admits` for why the arity is what decides it.
_SCREENED_ARITIES = (5,)


def _span_basis(vectors: list[int]) -> list[int]:
    """Row-reduce ``vectors`` to a GF(2) basis, greatest leading bit first.

    Columns are packed one bit per row, so a table and a tape column are the
    same kind of object and XOR is their addition.
    """
    basis: list[int] = []
    for v in vectors:
        cur = v
        for b in basis:
            cur = min(cur, cur ^ b)
        if cur:
            basis.append(cur)
            basis.sort(reverse=True)
    return basis


def _in_span(v: int, basis: list[int]) -> bool:
    """Whether ``v`` is a GF(2) combination of ``basis``."""
    cur = v
    for b in basis:
        cur = min(cur, cur ^ b)
    return cur == 0


@cache
def _staging_spans(n: int) -> tuple[tuple[int, ...], ...]:
    """Return one basis per staging, spanning its standing columns.

    Built once per arity and cached, because it does not depend on the table
    being asked for: it is a property of the enumeration, not of the target.
    """
    out: list[tuple[int, ...]] = []
    window = range(1, _BASE + n * _SPAN + 12)

    def pack(j: _Joint) -> list[int]:
        cols = []
        for cell in window:
            v = 0
            for bit in j.col(cell):
                v = (v << 1) | bit
            cols.append(v)
        return cols

    for sep_index in range(len(_SEPS)):
        for settle in (0, 1):
            base = _embed(n, settle=settle, sep=_SEPS[sep_index])
            _clamp(base)
            _walk_to(base, _BASE - 1)
            run = base.fork()
            for _k in range(_MAX_BRACKETS + 1):
                staged = run.fork()
                staged.emit("<")
                _clamp(staged)
                out.append(tuple(_span_basis(pack(staged))))
                run.emit("[")
            if n not in _INSERT_ARITIES:
                continue
            for suffix in _insert_suffixes():
                staged = base.fork()
                staged.emit(suffix + "<")
                _clamp(staged)
                out.append(tuple(_span_basis(pack(staged))))
    return tuple(out)


def _span_admits(truth_table: str, n: int) -> bool:
    """Whether any staging *could* print this table, on a linear-algebra test.

    A **necessary** condition, and the asymmetry is the point: False means no
    staging prints the table and the enumeration can be skipped outright,
    while True means only that the enumeration has to run.  A miss at five
    inputs costs a measured 143 seconds and this answers in about 3.6
    milliseconds, so what it saves is the sweep that was going to fail.

    Everything the endgame emits after the suffix is GF(2)-affine in the
    columns standing at that point, so a printed column lies in their span.
    Measured over the whole family rather than argued: 241280 of 241280
    (staging, printed column) incidences are contained at five inputs, and no
    reachable table is declined -- 0 false negatives over all 24582.  The
    check that matters most is the one against the *generator* rather than
    against that harvest: sampled declined tables were handed to the real
    derivation and it agreed, taking about 143 seconds each to find nothing.

    **Only five inputs.**  At four the test is vacuous -- ambient dimension
    16 against bases whose rank reaches 16, so every table is admitted at
    exactly the base rate -- and evaluating it would cost more than it saves.
    At five the ambient dimension is 32 against a median rank of 16, which is
    what makes it bite: it declines 53.4% of unreachable tables.

    Scope is the shipped caps, separators and setter.  Change any of them and
    the spans change with them; ``test_span_screen_declines_no_reachable_table``
    is what fails if this is ever no longer true.
    """
    if n not in _SCREENED_ARITIES:
        return True
    packed = 0
    for bit in truth_table:
        packed = (packed << 1) | int(bit)
    return any(_in_span(packed, list(b)) for b in _staging_spans(n))


def _derive_staging(truth_table: str, n: int) -> _Staging | None:
    """Return the staging that builds ``truth_table``, or None if none does.

    Every staging is accepted on the evidence of its own output -- the
    endgame is emitted and the rows are compared against the table -- so this
    needs no table of answers.  The enumeration order in :func:`_stagings` is
    the whole specification: it, and not a stored answer, decides which
    program a truth table gets.

    A table the enumeration misses gets one more pass at the arities in
    the two-insert family that used to sit here.  That pass was
    targeted at the one table rather than folded into the enumeration on
    purpose: run for the whole arity it would sweep 44950 suffixes to
    exhaustion in a measured 159 seconds, hunting columns for tables that
    already have stagings, while asking it for a single table stops at the
    first hit in about a quarter of a second.
    """
    if n not in _STAGED_ARITIES:
        return None
    complement = "".join(str(1 - int(c)) for c in truth_table)
    # A linear-algebra screen before the enumeration, where one is worth
    # running.  It only ever declines -- see :func:`_span_admits` -- so the
    # result is the same and a table it rejects skips a sweep that was going
    # to fail.
    if not _span_admits(truth_table, n):
        return None
    # Ask for this table and its complement only.  Both are passed because
    # they share a staging and whichever the enumeration reaches first
    # assigns it.
    return _derived_plans(n, (truth_table, complement)).get(truth_table)


# **The flipped-embed pass was here, and it is gone.**  It complemented some
# inputs as they landed, which took four inputs from 23.9% to 94.35% -- a real
# gain at the time, and dead weight now.  Every table it placed is a table the
# plain enumeration missed, and :func:`_mux` builds all 49190 of those (swept
# exhaustively, not sampled), so nothing reached it that the sculpted route
# does not reach.  Nor was it a fallback for another arity: it was gated to
# four inputs alone, which :data:`_MUX_ARITIES` also covers.
#
# What it cost was the whole-arity sweep behind it -- over 300 seconds, paid
# by the first four-input table to miss the stagings, against about 11ms for
# the same table through :func:`_mux`.  Deleting it takes that miss from
# minutes to the sculpted route's own derivation.
#
# The trade is program length: the flipped pass emitted shorter templates for
# the tables it placed, and those tables now get the sculpted route's longer
# ones.  Taken deliberately -- a shorter program is not worth minutes to
# compute -- and paid only by tables the plain enumeration already missed.
#
# ``docs/walls.md`` keeps the mechanism and the 94.35% measurement, which are
# still true and still the reason the residue was worth attacking.


def _staged(truth_table: str, n: int) -> str | None:
    """Build from a derived staging without searching, or None if there is none.

    None rather than an exception on a miss, so the caller falls through to
    the searches and coverage cannot regress.

    A miss falls through to :func:`_mux`, which closes four inputs.  The
    flipped-embed pass that used to sit here was removed once that route was
    shown to build every table it placed; see the note above
    :data:`_MUX_BASE`.
    """
    plan = _derive_staging(truth_table, n)
    if plan is not None:
        return _replay(truth_table, n, plan)
    return _mux(truth_table, n)


# ---------------------------------------------------------------------------
# The sculpted route: separate every row into its own pointer position, then
# fix the printed column one row at a time, from the highest position down.
#
# This is the construction that closes the four-input residue, and it embeds
# each input **exactly once** -- the repo-wide rule every parameterized
# generator holds to (see ``docs/limitations.md``) is kept, not carved out.
# The observation it stands on is that the embed already put the whole row
# identity on the tape: ``_embed``'s walk transform is affine and invertible,
# so after the embed no two rows are in the same state, and converting that
# state difference into a *pointer* difference needs reads of what is already
# there, never another copy of an input.
#
# **Separation** is that conversion, and it is *constructed* -- closed form in
# ``n``, no search anywhere.  Weight each input as it lands, so the pointer
# ends holding the row's binary expansion:
#
#     for i in range(n):
#         setter(i); weight(2**(n-1-i)); pad
#
# :func:`_mux_weight` is what makes a bit worth more than one step.  A
# restoring read ``[x<[<`` displaces by the bit and puts the cell back, so it
# can be read again; ``k`` of them with a one-cell rewind between compound to
# exactly ``-k`` times the bit -- measured linear for ``k`` of 1 to 8.  The
# pointer therefore lands at ``c0 - sum(2**(n-1-i) * x_i)``, which is affine
# in the inputs and injective by binary expansion: all ``2**n`` rows are
# separated by construction, and nothing has to be searched for or checked
# row by row.
#
# Two conditions make the weights compose, and both were found by measuring
# rather than by argument:
#
# * the bit must be **fresh**.  One ``[x`` between the setter and the gadget
#   folds the bit into the running prefix-XOR, and every weight collapses
#   to 1 -- which is exactly what an earlier per-setter attempt measured and
#   read as a wall.  Once the displacement is banked in the pointer, though,
#   arbitrary rightward padding preserves it (measured pad 0 to 10).
# * gadgets must not reach into each other.  Weight ``k`` writes at most
#   ``k - 3`` cells left of its setter, so :func:`_mux_pad` puts that much
#   clear air plus the room the deepest rewind needs above cell 0.  The
#   threshold ``2**(n-2) - 1`` is sharp -- below it the weights are still
#   exactly right and the misses are rows clamping at the tape floor.
#
# This replaces four searches (a pointer-census BFS, a greedy pass over aimed
# reads, a beam over aimed-read sequences, and a two-machine BFS on one
# colliding pair).  They cost 2.8s at three inputs and 15.0s at four, and
# failed outright at five after 191 seconds; the construction is 0.0007s at
# four and 0.004s at five.
#
# It also corrects what this comment used to claim.  "Reading a bit as it
# lands does not help and cannot" was measured over a *stale* bit -- the
# setter-read unit is shift-invariant over the uniform wake only once a walk
# has crossed the bit.  Read while fresh and sandboxed, it is the whole
# construction.  ``docs/walls.md`` keeps the superseded reasoning.
#
# **Sculpting** then edits the separated rows individually.  Fix a target
# cell ``C`` below every row.  One round ``'<' * K + '[x' * K`` with
# ``K = b - C + 1`` has three provable effects:
#
# * the row at position ``b`` rewinds to ``C - 1`` and its first landing is
#   ``C`` -- an *unconditional* flip, nothing crossed before it, so the flip
#   is clean whatever that row's tape holds;
# * a row above ``b`` starts its walk right of ``C`` and writes nothing below
#   its own rewind point, so its cells at and left of ``C`` -- and therefore
#   the value the endgame will read for it -- are untouched;
# * rows below ``b`` cross ``C`` on the way back and pick up value-dependent
#   cascade debris from crossing ``C - 1``: scrambled, not controlled.
#
# So repeatedly fixing the *highest* disagreeing row strictly lowers the
# frontier, and the loop lands in at most ``2**n`` rounds.  The one
# non-structural residue is the pool code: the probe re-derives it each
# round, and a state-driven switch could in principle disturb a fixed row
# through the walkout, which is why the loop carries a small allowance and
# falls through rather than looping.  The trailing ``x`` on every round is
# the ``_FLIP`` lesson again: a walk whose last ``[`` cascades leaves the
# skip flag set, and the next instruction must be one the program can afford
# to lose.
#
# **Coverage and cost, measured.**  All 3652 four-input tables the staged
# families miss build through this route and print all 16 rows correctly on
# the shipped interpreter, at one program width per table and with the slots
# in name order -- which closes the arity: 64594 of 64594.  A build costs
# about 7ms, and the arity's separation, which used to be a 15-17s search, is
# now 0.0007s of construction.
#
# **Five inputs is no longer gated.**  This section used to say five was
# absent because no derivation had separated 32 rows -- the searches ran 191
# seconds and failed, always stalling on pairs differing in the first input.
# The constructed separation above does it in 0.004s, and the rest of the
# route was never arity-specific, so :data:`_MUX_ARITIES` now carries five.
# Sampled end to end: 200 of 200 fully-essential five-input tables build and
# print all 32 rows correctly on the shipped interpreter, five-input XOR
# among them, at about 0.14s each.  The arity is not *closed* -- 200 tables
# is a sample of 4294642034 -- but nothing in the construction is aware of
# ``n``, and no sampled table has failed.
#
# The route sits *after* the staged families in
# :func:`_solve`, so every table they already build keeps its template byte
# for byte, and *before* the searches, which now serve only as the net should
# a pool code refuse every ``(C, orientation, read)`` this tries.

# Where the sculpted route embeds, and how much of the tape to its left the
# separation searches must not write.  The pool codes were designed against
# the uniform wake ``_walk_to`` leaves and their marks reach to about cell
# fourteen, so a separation that scribbles there strands every probe --
# measured, 0 usable pool probes against 14 with the region intact.  Eight
# cells between the guard and the embed are deliberately left writable:
# scratch there is what lets the searches finish, and sealing it turns the
# four-input separation from a 15-second derivation into a failure.
_MUX_BASE = _BASE + 16
_MUX_GUARD = _MUX_BASE - 8

# The arities the route is offered.  Two and three never reach it (the
# stagings are total there); four is the arity it closes, and five it reaches
# on every table sampled.  The construction has no arity-specific step, so
# the tuple is a statement about what has been *verified*, not about what the
# route can express.
_MUX_ARITIES = (2, 3, 4, 5)

# One derived separation per arity, handed out as forks.  A plain dict
# rather than ``lru_cache`` because the value is a mutable ``_Joint``.
_MUX_SEPARATED: dict[int, _Joint] = {}


def _mux_embed(n: int) -> _Joint:
    """Emit the standard embed shape, laid down at ``_MUX_BASE``."""
    j = _Joint(n)
    _walk_to(j, _MUX_BASE - 1)
    for i in range(n):
        j.emit_setter(i)
        j.emit("[x")
        if i + 1 < n:
            j.emit(_SEP)
    return j


def _mux_reference(n: int) -> _Joint:
    """Return a joint walked to the embed's start with nothing embedded yet.

    What :func:`_mux_separate`'s guard check compares against: the walk-in is
    common to every row, so this is the tape the construction must leave
    untouched left of :data:`_MUX_GUARD`.
    """
    j = _Joint(n)
    _walk_to(j, _mux_start(n) - 1)
    return j


def _mux_intact(before: _Joint, after: _Joint) -> bool:
    """Whether every cell left of the guard survived, on every row."""
    return all(
        m.tape[:_MUX_GUARD] == m0.tape[:_MUX_GUARD]
        for m, m0 in zip(after.ms, before.ms, strict=True)
    )


def _mux_weight(k: int) -> str:
    """Return the gadget displacing a **fresh** setter bit by exactly ``-k``.

    A single restoring read ``[x<[<`` moves the pointer by the bit's value and
    puts the cell back, so the bit can be read again; rewinding one cell
    between such reads compounds them, and ``k`` of them displace by ``k``
    times the bit.  Measured linear for ``k`` of 1 to 8, with no row dying.

    *Fresh* is load-bearing and is the whole reason an earlier attempt at
    per-setter weighting read 1 for every weight: a single ``[x`` between the
    setter and this gadget folds the bit into the running prefix-XOR, and the
    reads then see the walk's wake rather than the bit.  Emit this directly
    after :meth:`_Joint.emit_setter`, never after a walk.

    The gadget writes at most ``max(0, k - 3)`` cells left of the setter
    (measured over the same range), which is what :func:`_mux_separate`'s pad
    is sized against.
    """
    return ("[x<[<" + "<") * (k - 1) + "[x<[<" if k > 0 else ""


def _mux_weights(n: int) -> tuple[int, ...]:
    """Return the per-input weights: ``2**(n-1-i)``, so the sum is the row."""
    return tuple(2 ** (n - 1 - i) for i in range(n))


def _mux_pad(n: int) -> int:
    """Return the slack each gadget gets beyond the previous one's weight.

    A gadget of weight ``k`` reaches ``k - 3`` cells left of its setter, so
    the pad has to clear that much *and* keep the deepest rewind above cell
    0.  ``2**(n-2) - 1`` is where the second condition binds and is sharp:
    at four inputs pads 1 and 2 separate 14 of 16 and pad 3 separates all 16;
    at five, pads 1 to 6 reach 21 to 30 of 32 and pad 7 closes it.  Below the
    threshold the weights are still exactly right -- the misses are rows
    whose leading bits clamp at the tape's floor, not a weighting error.

    The shift spells the power rather than ``2 **``, which mypy widens to
    ``Any`` because a negative exponent would make it a float; the arities
    here are always at least two, so the shift is the honest spelling.
    """
    return max((1 << (n - 2)) - 1, 1)


def _mux_start(n: int) -> int:
    """Return where to lay the embed so no gadget writes left of the guard.

    The leftmost write is the first gadget's, and it is the heaviest: weight
    ``2**(n-1)`` reaches ``2**(n-1) - 3`` cells left of its setter, which sits
    eight cells above the guard.  So the embed starts ``2**(n-1) - 9`` cells
    further right than :data:`_MUX_BASE`, which is nothing at two, three and
    four inputs -- they already clear the guard -- and 7 and 23 cells at five
    and six.  Measured: those are exactly the smallest starts that leave the
    guarded region untouched on every row.
    """
    return _MUX_BASE + max(0, (1 << (n - 1)) - 9)


def _mux_separate(n: int) -> _Joint | None:
    """Emit an embed leaving all ``2**n`` rows at distinct pointers.

    Constructed rather than searched.  Each input is weighted as it lands --
    setter, then :func:`_mux_weight` on the still-fresh bit, then a pad wide
    enough that the next gadget starts outside this one's damage -- so the
    pointer ends at ``c0 - sum(2**(n-1-i) * x_i)``.  That is affine in the
    inputs with the binary weights, hence injective, so the rows are
    separated by construction and there is nothing to search for.

    Table-independent, so it is built once per arity and cached; callers get
    a fork.  The return type keeps the ``None`` case the searches needed, so
    :func:`_mux` is unchanged, but the construction does not fail: the
    verification below is what the arity gate now rests on.
    """
    if n in _MUX_SEPARATED:
        return _MUX_SEPARATED[n].fork()
    weights = _mux_weights(n)
    pad = _mux_pad(n)
    j = _Joint(n)
    _walk_to(j, _mux_start(n) - 1)
    for i, k in enumerate(weights):
        j.emit_setter(i)
        j.emit(_mux_weight(k))
        if i + 1 < n:
            j.emit("[x" * (k + pad))
    # The construction is derived, but it is still *checked* before it is
    # cached: a separation that quietly lost a row would be found by the
    # sculpting loop as an unfixable table rather than as a bad separation.
    if any(m.dead for m in j.ms) or len(set(j.ptrs())) != 2**n:
        return None
    if not _mux_intact(_mux_reference(n), j):
        return None
    # Pad right so the sculpting rewinds fit: every round needs
    # ``b - C + 1 <= min(ptr) - 8`` with ``C`` below the lowest row.
    q = j.ptrs()
    floor = (max(q) - min(q)) + 24
    if min(q) < floor:
        j.emit("[x" * (floor - min(q)))
    _MUX_SEPARATED[n] = j.fork()
    return j


def _mux_column(j: _Joint, acc: int, cell7: int) -> tuple[int, ...] | None:
    """Return what the ``'[x<[<'`` read would print at ``acc``, uncached.

    The same derivation as :func:`_printed_column`, minus the memoisation:
    sculpting never revisits a state, so the module-level caches would grow
    one entry per probe and pay for lookups that can never hit.  The pool
    codes are tried directly instead.
    """
    probe = j.fork()
    probe.emit("x")  # absorb a pending skip so the clamp below is exact
    _clamp(probe)
    code = None
    for candidate in _POOL_CODES:
        if _pool_reaches(probe, candidate, cell7, acc - 1):
            code = candidate
            break
    if code is None:
        return None
    probe.emit(code)
    try:
        _walk_to(probe, acc - 1)
    except ValueError:
        return None
    return tuple(probe.col(probe.ms[0].ptr + 1))


def _mux(truth_table: str, n: int) -> str | None:
    """Build by separating the rows, then sculpting the column they print.

    Every ``(C, orientation, read)`` combination runs the same loop: derive
    the column the endgame would print, take the highest-positioned row that
    disagrees, flip its cell ``C`` with one clean round, repeat.  The
    frontier argument in the section comment bounds the loop; the cap is
    that bound plus a small allowance for a pool-code switch, and a stall
    falls through to the next combination rather than looping.  The
    finished joint is handed to :func:`_try_print`, so what is returned was
    seen to print the table.
    """
    if n not in _MUX_ARITIES:
        return None
    base = _mux_separate(n)
    if base is None:
        return None
    want = tuple(int(c) for c in truth_table)
    positions = base.ptrs()
    lowest, highest = min(positions), max(positions)
    for acc in range(highest - lowest + 9, lowest - 1):
        for cell7 in (0, 1):
            for direct in (True, False):
                j = base.fork()
                stalled = False
                for _ in range(2**n + 4):
                    column = _mux_column(j, acc, cell7)
                    if column is None:
                        stalled = True
                        break
                    got = column if direct else _complement(column)
                    disagree = [
                        p for p, g, w in zip(j.ptrs(), got, want, strict=True) if g != w
                    ]
                    if not disagree:
                        break
                    frontier = max(disagree)
                    rewind = frontier - acc + 1
                    if rewind > min(j.ptrs()) - 8:
                        stalled = True
                        break
                    j.emit("<" * rewind + "[x" * rewind + "x")
                else:
                    stalled = True
                if stalled:
                    continue
                j.emit("x")
                _clamp(j)
                hit = _try_print(j, truth_table, acc)
                if hit is not None:
                    return hit.template()
    return None


def _lift_leaves_name_order(essential: list[int], n: int) -> bool:
    """Whether lifting would emit the ``{Xi}`` out of ascending order.

    :func:`_lift` appends the ignored inputs after the solved template, so
    the result is still sorted when every ignored index is above every
    essential one -- ``{X0}{X1}`` then ``{X2}``.  It is only when an ignored
    index sits *below* an essential one that the append leaves sequence.
    """
    ignored = [i for i in range(n) if i not in essential]
    return bool(ignored and essential and min(ignored) < max(essential))


def _lift(template: str, essential: list[int], n: int) -> str:
    """Renumber a smaller table's placeholders back onto the wider arity.

    The inner solve used ``{X0}..{Xk-1}``, which correspond to the original
    inputs listed in ``essential``.  The renaming is done in a single pass, so
    a rename cannot collide with a placeholder it has not rewritten yet.

    Every input the function ignores still needs a placeholder, or the harness
    would have a bit with nowhere to put it.  Those go on the end: the fill is
    two characters whichever bit it is, so they cannot make the program's
    length depend on the inputs, and by then the digit has been printed -- the
    ``.`` has already run -- so whatever they do to the tape cannot matter.
    """
    rename = {f"X{slot}": f"X{i}" for slot, i in enumerate(essential)}
    lifted = re.sub(
        r"\{(X\d+)\}",
        lambda m: "{" + rename[m.group(1)] + "}",
        template,
    )
    ignored = "".join("{X" + str(i) + "}" for i in range(n) if i not in essential)
    return lifted + ignored


@cache
def _solve(truth_table: str) -> str:
    """Build a Minifuck template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Minifuck has no usable input command, so this is a parameterized
    generator: the template's ``{Xi}`` placeholders become ``[<`` for a one
    and ``xx`` for a zero -- equal width, so no instantiation leaks its
    inputs through its length -- and the harness instantiates one program per
    input combination.

    The emitted program embeds each input once, computes the table in cells
    past the pool, relays the answer into the *pointer* (values cannot travel
    left, but the pointer can), and prints one ASCII digit.  Every step is
    simulated against all ``2**n`` rows as it is emitted, and a
    :class:`ValueError` is raised rather than returning a program that has
    not been seen to print the table.

    Cached, because at four inputs and above the simulated search is what
    this module costs -- seconds to tens of seconds a table, against
    effectively zero to *run* the program it returns.  Below that nothing
    searches at all: two and three inputs are derived from the staging
    enumeration and the sculpted route, and all 276 tables up to three inputs
    build in about three and a half seconds together.  The build is
    deterministic in ``truth_table`` and the result is an immutable string,
    so repeat calls are free either way.
    """
    n = _validate_shape(truth_table)

    # A table that ignores some of its inputs is a *smaller* table wearing
    # extra ones, so solve it at the arity it actually uses and renumber the
    # placeholders back.  This is the part of the construction that composes:
    # what it costs depends on the essential inputs, not on ``n``, so a wide
    # table with a narrow core is as cheap as that core.
    essential = essential_inputs(truth_table, n)
    if len(essential) < n:
        # Projecting is much the cheaper route, but it emits the ignored
        # inputs after the ``.``, which leaves name order whenever an ignored
        # index sits below an essential one.  ``_embed`` already lays every
        # slot down in ascending order, so solving at the *full* arity is
        # in-order by construction -- try it first for exactly the tables the
        # lift would disorder, and only when it is the cheap closed-form
        # path.  A table with two or more essential inputs is not: measured
        # at n == 3, ``00000101`` runs the searches for 132 seconds and still
        # fails, against seconds to project.  Coverage comes first, so a miss
        # here falls through to the projection rather than raising.  The
        # attempt is capped at the fixed-cell lookup because that is where
        # every table it wins is won; letting it run the column search only
        # adds about five seconds to the tables it cannot build anyway.
        if _lift_leaves_name_order(essential, n):
            if len(essential) <= 1:
                in_order = _degenerate(truth_table, n, fixed_cells_only=True)
                if in_order is not None:
                    return in_order
            reconverged = _reconverged(truth_table, essential, n)
            if reconverged is not None:
                return reconverged
            # **The last ten out-of-order tables are sorted here.**
            #
            # Ten three-input tables used to emit ``{X0}{X2}{X1}``, all with
            # the same shape: the ignored input is the *middle* one.  The two
            # routes above cannot sort those -- emitting the ignored setter
            # first does not help when it already follows ``{X0}``, and
            # reconvergence drives every row to one state, so it cannot
            # collapse ``x1`` while preserving ``x0``.  Searched to depth 14,
            # no reset exists.  The comment that recorded this closed with
            # "sorting those needs the solver to assign names".
            #
            # It does not.  :func:`_mux` lays every slot down in ascending
            # order at the *full* arity and never projects, so it emits in
            # name order by construction -- and it does not care that the
            # table ignores an input, because it sculpts the printed column
            # row by row rather than reading a column the ignored bit would
            # have disturbed.  Measured: all ten come back ascending and
            # print every row correctly on the shipped interpreter.
            #
            # It goes *after* the two cheap routes because it is the more
            # expensive one and they already sort everything they reach; what
            # is left here is exactly the residue they cannot.
            sculpted = _mux(truth_table, n)
            if sculpted is not None:
                return sculpted
        inner = _solve(_project(truth_table, essential, n))
        return _lift(inner, essential, n)

    # At most one essential input means a constant or a (negated) projection,
    # and the embed already holds every one of those as a column -- so the
    # answer is a cell lookup rather than a search.
    if len(essential) <= 1:
        degenerate = _degenerate(truth_table, n)
        if degenerate is not None:
            return degenerate

    # A planned staging is the cheapest route by far, so it goes first.  Two
    # and three inputs are both complete -- the enumeration closes two, and
    # the enumeration plus the sculpted route closes three -- so nothing ever
    # runs below four inputs.  A miss at a wider arity falls through to the
    # searches below.
    derived = _staged(truth_table, n)
    if derived is not None:
        return derived

    # The sculpted route: it closes four inputs (all 3652 tables the staged
    # families miss, interpreter-verified) at milliseconds a table, so it
    # goes ahead of the searches -- which stay below purely as the safety
    # net for a pool code refusing every combination it tries.
    sculpted = _mux(truth_table, n)
    if sculpted is not None:
        return sculpted

    # **A miss raises here rather than searching, and that is a deliberate
    # trade of coverage for a bounded cost.**
    #
    # The column and parked searches used to sit at this point.  They were
    # measurably unreachable at ``n <= 4`` -- stubbed to raise, every table
    # at one, two and three inputs still built (4, 16 and 256 of each), and
    # so did a 370-table four-input sample that deliberately included 120
    # degenerate tables -- because the routes above close those arities
    # between them.
    #
    # At ``n >= 5`` they were reachable and *unbounded*.  A five-input table
    # the staged enumeration cannot place ran past a 240-second cap and was
    # still going, against 3.4 seconds for a table it can place (five-input
    # XOR) and about 55 seconds for the enumeration itself to give up.  So
    # the searches turned a fast failure into an indefinite one, which is
    # worse than refusing: a caller can handle a raise, and cannot handle a
    # build that never returns.
    #
    # What is kept is the fast half.  Five inputs still builds every table
    # the staged family reaches -- a measured 0.00057% slice, five-input XOR
    # among them, which no search here ever built anyway -- and a table
    # outside it now raises at once instead of hanging.  ``_span_admits``
    # declines most misses in milliseconds, so the common miss is fast too.
    #
    # This is a *cost* gate, not a claim about the language.  The tables it
    # refuses are unreached, not unbuildable, and lifting them needs the
    # 32-row separation :data:`_MUX_ARITIES` is waiting on -- see
    # ``docs/walls.md``.  Restore the searches and the old behaviour returns
    # unchanged; they are recorded in git history rather than carried as
    # code no arity can afford to run.
    raise ValueError(f"the Minifuck boolean generator could not build {truth_table!r}")


def minifuck(truth_table: str) -> str:
    """Build a Minifuck template for the given truth table.

    The construction is :func:`_solve`; this is the public entry, and the
    difference is the arity check.  ``_solve`` accepts a *nullary* table
    because it recurses into itself after projecting a table onto its
    essential inputs, and a constant table projects to a single entry --
    six such calls happen while building the 276 tables up to three inputs.
    A one-entry table is not a boolean function of any input, though, so it
    is refused at the API the way every other generator refuses it.
    """
    _validate_truth_table(truth_table)
    return _solve(truth_table)


# The construction's cache and its undecorated body live on ``_solve`` now,
# but tests and callers reach for them through the public name: keep
# ``cache_clear``/``cache_info`` and ``__wrapped__`` here so splitting the
# arity check off did not move the surface.
minifuck.cache_clear = _solve.cache_clear  # type: ignore[attr-defined]
minifuck.cache_info = _solve.cache_info  # type: ignore[attr-defined]
minifuck.__wrapped__ = _solve.__wrapped__  # type: ignore[attr-defined]
