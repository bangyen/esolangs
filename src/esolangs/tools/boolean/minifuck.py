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
The one exception is a single three-input table whose suffix no bracket run
spells; see :data:`_EXCEPTIONS`.

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
0.9s for two inputs and 15s for three, against minutes if each table sweeps
for itself.  So the first three-input table costs the arity and the other
255 are free; that is the trade deriving makes against storing.

Four inputs is *partial* and staged anyway: 15404 of the 64594 fully
essential four-input tables (23.9%), four-input XOR among them.  What buys
those is one widening of the suffix -- a single ``<`` inside the bracket run,
enumerated after every pure run -- and the family that widening generalises
is :data:`_EXCEPTIONS`' one stored suffix, which does the same thing by hand.
Partial coverage is worth gating on because a miss is not a failure: it falls
through to the searches below, which is why those remain -- a missing staging
degrades rather than raises.  What a four-input table does pay for is the
derivation, which at this arity cannot stop early; see
:data:`_STAGED_ARITIES`.
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


def _embed(n: int, settle: int = 0, sep: str = _SEP) -> _Joint:
    """Emit the embed: each ``{Xi}`` once, separated by :data:`_SEP`.

    The separator is not arbitrary.  A plain run of ``[x`` leaves the bits'
    prefix-XORs too correlated for the one-sided tests the endgame can make,
    and the XOR family becomes unreachable; ``[x<[x`` steps back over one
    cell so the parities stay distinguishable.  ``settle`` re-crosses the
    region that many times, which advances the affine state and offers the
    searches a different set of columns.
    """
    j = _Joint(n)
    _walk_to(j, _BASE - 1)
    for i in range(n):
        j.emit_setter(i)
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


@cache
def _find_pool_cached(
    site: tuple[tuple[object, ...], ...],
    cell7: int,
    walk_out: int,
    codes: tuple[str, ...],
) -> str | None:
    """:func:`_find_pool` keyed on the joint's state, memoised.

    The search is the build's hot spot -- it walks every pool code through
    every row of the joint, and at ``n == 3`` parity that is 56 million
    ``_Sim.exec`` calls, over half the build.  Almost all of it is repeated:
    the same joint state is reached from many plans, so 30167 calls resolve
    to 572 distinct sites, a 98% hit rate.

    Keyed without ``walk_out`` deliberately -- see :func:`_find_pool` for
    why the verdict does not depend on it.  It is still passed through to
    the probe so a cache miss runs exactly the search it always ran.

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
        if _pool_reaches(j, code, cell7, walk_out):
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
    key: two calls differing only in it are the same question.
    """
    return _find_pool_cached(
        tuple(m.key() for m in j.ms), cell7, walk_out, tuple(_POOL_CODES)
    )


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
# whatever the table.  Measured, the whole three-input arity derives in 15s
# and two inputs in 0.9s; the table-major spelling of the same search costs
# minutes, because it rebuilds every staging once per table.
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

# The arities the enumeration covers.  Two and three are *total*; four is
# partial, and is here because partial beats the fall-through it replaces.
# Beyond four it is not that the enumeration fails but that it has not been
# shown to succeed, so the gate stays explicit rather than implied by a miss.
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
# about six minutes.  That is paid by the first fully-essential four-input
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
_STAGED_ARITIES = (2, 3, 4)

# How far the enumeration runs.  Both caps are the measured maximum over
# every table plus a margin, not guesses: sweeping to a bracket count of 30
# and an accumulator of 40, the deepest first hit at two inputs is
# ``(k=6, acc=20)`` and at three ``(k=26, acc=31)``.  Nothing is reached past
# those, so the sweep stops a little beyond them.
_MAX_BRACKETS = 28
_MAX_ACC = 34

# The arities whose enumeration includes the insert family below.  It is not
# offered at two or three inputs because the pure runs already close those
# arities completely, and enumerating a family that can only be reached after
# every pure run has missed would cost those arities time for nothing.
_INSERT_ARITIES = (4,)


def _insert_suffixes() -> Iterator[str]:
    """Enumerate bracket runs with one ``<`` inside, shortest first.

    The pure runs the enumeration spells as ``'[' * k`` are one string per
    length; putting a single ``<`` at each interior position gives ``k + 1``
    per length instead, which is where the four-input coverage comes from.

    This is not a free search over the alphabet -- that is what cost 29
    minutes to find :data:`_EXCEPTIONS`' one stored suffix.  It is the
    smallest generalisation of the pure run that the stored exception proves
    necessary: that suffix interleaves ``<`` into its bracket run, so a
    family no wider than "the same run with a ``<`` in it" was already known
    to reach columns no ``'[' * k`` reaches.  What was not known, and what
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


# The one table the enumeration cannot reach.  Its suffix interleaves two
# ``<`` into the bracket run, which no ``'[' * k`` spells, so no entry of
# :func:`_stagings` expresses it.  This is not a staging the sweep merely
# missed: pure bracket runs were taken to exhaustion for this pair over every
# separator, settle count and accumulator -- 13 of the 15 slices at
# ``k <= 40`` -- and none carries its column to the read.  The search that
# did find it ran for 29 minutes, which is why it is stored rather than
# derived.  See the note on :data:`_SEPS` and commit 89bcc12.
_EXCEPTIONS: dict[int, dict[str, _Staging]] = {
    3: {"01101101": (2, 0, "[[<[<[[[[[[[[[", 22)},
}


def _replay(truth_table: str, n: int, plan: _Staging) -> str | None:
    """Build one staging and return its template, or None if it does not print.

    The suffix is a bracket *count* for everything the enumeration produces --
    a plain run, which the ``<`` terminates so the pointer lands where the
    endgame expects -- and a literal string for the one stored exception.
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
def _derived_plans(n: int) -> dict[str, _Staging]:
    """Derive a staging for every table at this arity, in one pass.

    The whole arity is done at once because a staging is expensive to *build*
    and cheap to *test against a table*: the embed, the bracket run and the
    endgame do not depend on which table is wanted, and only the comparison
    at the very end does.  So the loops run staging-major -- one embed per
    ``(separator, settle)``, the bracket run extended one ``[`` at a time
    rather than rebuilt, and the endgame emitted once per
    ``(k, accumulator, read, orientation)`` -- and each printed column is
    looked up among the tables still wanting one.

    Doing it table-major instead re-derives the same stagings once per table
    and costs minutes rather than seconds, which is what an earlier version
    of this did.  The result is identical either way: a table is assigned the
    first staging in :func:`_stagings` order that prints it.

    Returns a mapping from truth table to staging.  A table that no staging
    reaches is simply absent, so the caller falls through to the searches.
    """
    if n not in _STAGED_ARITIES:
        return {}

    # What each printed column would answer.  A table and its complement
    # share a staging, so both spellings map to their own table and whichever
    # is reached first assigns both.
    wanted: dict[tuple[int, ...], list[str]] = {}
    for r in range(2 ** (2**n)):
        table = format(r, f"0{2**n}b")
        wanted.setdefault(tuple(int(c) for c in table), []).append(table)
    remaining = 2 ** (2**n)

    found: dict[str, _Staging] = {}

    def claim(staged: _Joint, suffix: int | str, head: tuple[int, int]) -> bool:
        """Try every accumulator here, recording what each prints.

        Returns whether every table has been placed, which is what stops the
        enumeration early.  Both passes below share this: the suffix is
        already emitted by the time it runs, so a bracket count and an insert
        string reach it the same way.
        """
        nonlocal remaining
        for acc in range(9, _MAX_ACC + 1):
            for read in _READS:
                for cell7 in (0, 1):
                    probe = staged.fork()
                    try:
                        _endgame(probe, acc, read, cell7)
                    except ValueError:
                        continue
                    printed = probe.printed()
                    if any(len(digit) != 1 for digit in printed):
                        continue
                    column = tuple(int(digit) for digit in printed)
                    for table in wanted.get(column, ()):
                        if table not in found:
                            found[table] = (*head, suffix, acc)
                            remaining -= 1
            if not remaining:
                return True
        return False

    for sep_index in range(len(_SEPS)):
        for settle in (0, 1):
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
    for sep_index in range(len(_SEPS)):
        for settle in (0, 1):
            base = _embed(n, settle=settle, sep=_SEPS[sep_index])
            _clamp(base)
            _walk_to(base, _BASE - 1)
            for suffix in _insert_suffixes():
                staged = base.fork()
                staged.emit(suffix + "<")
                _clamp(staged)
                if claim(staged, suffix, (sep_index, settle)):
                    return found
    return found


def _derive_staging(truth_table: str, n: int) -> _Staging | None:
    """Return the staging that builds ``truth_table``, or None if none does.

    Every staging is accepted on the evidence of its own output -- the
    endgame is emitted and the rows are compared against the table -- so this
    needs no table of answers.  The enumeration order in :func:`_stagings` is
    the whole specification: it, and not a stored answer, decides which
    program a truth table gets.

    The stored exception is keyed by the lexicographically smaller of the
    table and its complement, since that pair shares a staging: the endgame
    tries both read polarities and prints ``NOT(v XOR cell7)``.
    """
    if n not in _STAGED_ARITIES:
        return None
    complement = "".join(str(1 - int(c)) for c in truth_table)
    exception = _EXCEPTIONS.get(n, {}).get(min(truth_table, complement))
    if exception is not None:
        return exception
    return _derived_plans(n).get(truth_table)


def _staged(truth_table: str, n: int) -> str | None:
    """Build from a derived staging without searching, or None if there is none.

    None rather than an exception on a miss, so the caller falls through to
    the searches and coverage cannot regress.
    """
    plan = _derive_staging(truth_table, n)
    return None if plan is None else _replay(truth_table, n, plan)


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
def minifuck(truth_table: str) -> str:
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

    Cached, because at three inputs the simulated search is what this module
    costs -- seconds to tens of seconds a table, against effectively zero to
    *run* the program it returns.  Two inputs no longer pay that: they are
    derived from the staging enumeration, and all sixteen build in well under
    a second together.  The build is deterministic in ``truth_table`` and the
    result is an immutable string, so repeat calls are free either way.
    """
    n = _validate_truth_table(truth_table)
    want = tuple(int(c) for c in truth_table)

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
        inner = minifuck(_project(truth_table, essential, n))
        return _lift(inner, essential, n)

    # At most one essential input means a constant or a (negated) projection,
    # and the embed already holds every one of those as a column -- so the
    # answer is a cell lookup rather than a search.
    if len(essential) <= 1:
        degenerate = _degenerate(truth_table, n)
        if degenerate is not None:
            return degenerate

    # A planned staging is the cheapest route by far, so it goes first.  At
    # two inputs the plan is complete and no search ever runs; at three it
    # covers all 109 complement pairs, and a miss at another arity falls through to the
    # searches below.
    derived = _staged(truth_table, n)
    if derived is not None:
        return derived

    frontier = _BASE + n * _SPAN + 6

    # The scans first, across *both* separators, because they are by far the
    # cheapest route and a good share of tables land in one of them: the
    # embed's carry chain computes AND, NOR and XOR as a byproduct, so the
    # answer is often already sitting in a cell.  Interleaving them with the
    # searches (one separator fully, then the next) made tables that only the
    # second separator's scan reaches pay for three failed searches first --
    # measured at 69-82s each, against about 35s for the searches that do hit.
    for sep in _SCAN_SEPS:
        base = _embed(n, sep=sep)
        _clamp(base)
        for acc in range(9, frontier):
            hit = _try_print(base, truth_table, acc)
            if hit is not None:
                return hit.template()

    for sep in _SCAN_SEPS:
        # Otherwise search for the answer column outright.  The search has to
        # launch from the frontier, with the pointer already in the data: a
        # depth-``d`` walk from the origin never reaches cell ``_BASE``, so
        # every state it could see is input-independent.
        for park in range(_BASE - 2, _BASE + 2 * n + 4):
            probe = _embed(n, sep=sep)
            _clamp(probe)
            try:
                _walk_to(probe, park)
            except ValueError:
                continue
            found = _find_column(probe, want, frontier + 8, _COLUMN_DEPTH)
            if found is None:
                continue
            code, _cell = found
            probe.emit(code)
            _clamp(probe)
            for acc in range(9, frontier + 8):
                hit = _try_print(probe, truth_table, acc)
                if hit is not None:
                    return hit.template()

    # Last, and only if everything cheaper failed: park the pointer on the
    # answer as part of what is searched for, so no walk intervenes between
    # producing the column and reading it -- a walk back would re-cross, and
    # so change, that very cell.  This is the most expensive route, and it
    # earns its place at n == 2 (it is the only one reaching the XOR family)
    # while contributing no hits at all in an n == 3 sample, so it goes last.
    for sep in _SCAN_SEPS:
        for code, _cell in _find_parked(
            _embed(n, settle=_SETTLE, sep=sep),
            want,
            frontier + 8,
            _PARKED_DEPTH,
            _PARKED_LIMIT,
        ):
            probe = _embed(n, settle=_SETTLE, sep=sep)
            probe.emit(code)
            _clamp(probe)
            for acc in range(9, frontier + 8):
                hit = _try_print(probe, truth_table, acc)
                if hit is not None:
                    return hit.template()

    raise ValueError(f"the Minifuck boolean generator could not build {truth_table!r}")
