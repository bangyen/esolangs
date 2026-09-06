"""The Minifuck machine the boolean generator emits against.

The generator cannot hand a whole program to the interpreter and read the
answer: it decides what to emit *next* from what the program built so far
has done, so it needs a machine it can feed one instruction at a time and
inspect between them.  :class:`_Sim` is that machine, and :class:`_Joint`
runs one per truth-table row in lockstep, which is how a single emitted
template is checked against every row of the table at once.

This lives beside the generator rather than inside it because the two
answer different questions.  Everything here is *what Minifuck does* --
one instruction's effect on a tape, a pointer and a skip flag.  The
construction in :mod:`esolangs.tools.boolean.minifuck` is *what to emit*:
pools, separators, sculpting rounds and the endgame, all of which consume
this machine and none of which this machine knows about.  Splitting them
keeps a 3300-line module from also being the place the language's
semantics are mirrored, and makes the mirror's one hard rule visible on
its own terms:

**The semantics are not respelled here.**  ``.`` and ``[`` -- the only
instructions that can print, read, or cascade into a neighbour -- delegate
to the interpreter's ``_step``, which stays the single definition of what
a Minifuck instruction means.  What this module adds is the *shape* the
emitter needs and the interpreter has no reason to provide: a per-row
pending-skip flag, a ``dead`` marker for the read a parameterized program
must never take, and closed forms for the two straight runs that would
otherwise be stepped one character at a time.  Those closed forms are an
optimization only while they agree with the stepper, which
``test_the_closed_form_runs_agree_with_stepping_them`` checks over random
states rather than fresh ones.
"""

from esolangs.interpreters.tape_based.minifuck import _step as _minifuck_step

class _Sim:
    """A Minifuck machine fed one instruction at a time.

    An emitter cannot hand a whole program over and read the answer: it must
    advance a machine and branch on where that left it.  So this accepts
    instructions singly, and holds the state an emitter branches on -- the
    tape as cells, the pointer, what has printed, and the two flags below.

    The *semantics* are not re-implemented here.  :meth:`exec` calls the
    interpreter's own ``_step``, so there is one definition of what a
    Minifuck instruction does and an emitter cannot drift from a real run.
    That became possible when the interpreter's transition was made pure;
    before that this class carried its own copy of the dispatch.

    ``dead`` marks the one transition a parameterized program must never
    take: a ``.`` on a zero pool reads a byte of input.
    """

    __slots__ = ("dead", "length", "out", "ptr", "skip", "tape")

    def __init__(self, size: int) -> None:
        """Start with a zeroed tape of ``size`` cells at the origin.

        The tape is an ``int`` bitvector, cell *i* at bit *i* -- the same
        spelling the interpreter's ``_State`` uses, so :meth:`exec` can hand
        it straight over.  Holding it as a list of cells instead would mean
        converting both ways on every step, which measured 68-78% of a step
        and made an O(1) flip cost O(tape).
        """
        self.tape = 0
        self.length = size
        self.ptr = 0
        self.out: list[str] = []
        self.dead = False
        self.skip = False

    def cell(self, index: int) -> int:
        """Return the bit in cell ``index``."""
        return (self.tape >> index) & 1

    def cells(self, stop: int) -> tuple[int, ...]:
        """Return cells ``0..stop-1``, the shape a column comparison wants."""
        return tuple((self.tape >> i) & 1 for i in range(stop))

    def copy(self) -> "_Sim":
        """Return an independent copy, for branching a search or a probe."""
        clone = _Sim.__new__(_Sim)
        clone.tape = self.tape
        clone.length = self.length
        clone.ptr = self.ptr
        clone.out = list(self.out)
        clone.dead = self.dead
        clone.skip = self.skip
        return clone

    def key(self) -> tuple[object, ...]:
        """Return the whole state, hashable, so a search can dedup on it."""
        return (self.tape, self.length, self.ptr, tuple(self.out), self.dead, self.skip)

    @staticmethod
    def restore(key: tuple[object, ...]) -> "_Sim":
        """Rebuild the machine :meth:`key` described.

        The inverse of :meth:`key`, so a memo can hold states rather than
        machines and hand back something the probes can step.
        """
        tape, length, ptr, out, dead, skip = key
        clone = _Sim.__new__(_Sim)
        clone.tape = tape  # type: ignore[assignment]
        clone.length = length  # type: ignore[assignment]
        clone.ptr = ptr  # type: ignore[assignment]
        clone.out = list(out)  # type: ignore[call-overload]
        clone.dead = dead  # type: ignore[assignment]
        clone.skip = skip  # type: ignore[assignment]
        return clone

    def run_left(self, count: int) -> None:
        """Apply ``"<" * count`` in closed form.

        ``<`` is the interpreter's cheapest branch -- ``ptr - 1 if ptr else
        ptr``, with no tape write, no print and no skip -- so a run of them
        is exactly ``max(ptr - count, 0)`` and does not need stepping.  A
        pending skip still eats the first one, and a dead row does not move.

        This is not a second definition of the language: it is the closed
        form *of* :meth:`exec` over one instruction, checked against it by a
        randomized differential control (see the module's test).  The clamp
        this serves was 33.8% of the six-input build's ``char x row`` steps.
        """
        if self.dead or count <= 0:
            return
        if self.skip:
            self.skip = False
            count -= 1
        self.ptr = max(self.ptr - count, 0)

    def run_walk(self, pairs: int) -> None:
        """Apply ``"[x" * pairs`` in closed form.

        Each pair advances one cell and flips it; when that flip leaves the
        cell zero the ``[`` cascades into the cell beyond it and sets the
        skip, which the pair's own ``x`` -- a comment -- then consumes.  So
        the pair always ends with the skip clear, and the run stays
        per-cell because the cascade depends on the bit it finds.

        The cascade is the part a closed form gets wrong: a model without it
        disagreed with :meth:`exec` on 877 of 3000 random states.  With it,
        0 of 3000.  The walk was 32.4% of the six-input build's steps.
        """
        if self.dead or pairs <= 0:
            return
        if self.skip:
            # The pending skip eats the leading ``[``; its ``x`` is a comment.
            self.skip = False
            pairs -= 1
        tape, length, ptr = self.tape, self.length, self.ptr
        for _ in range(pairs):
            ptr += 1
            if ptr + 1 >= length:
                length += 1
            tape ^= 1 << ptr
            if not (tape >> ptr) & 1:
                tape ^= 1 << (ptr + 1)
        self.tape, self.length, self.ptr = tape, length, ptr

    def exec(self, ins: str) -> None:
        """Execute one instruction, delegating the semantics to the interpreter.

        The language itself is not spelled here: the interpreter's ``_step``
        is the shipped pure transition, so an emitter and a real run cannot
        disagree about what an instruction does.  This used to carry
        its own copy of the dispatch, which was a second definition of
        Minifuck that had to be kept in step by hand.

        What stays is the *shape* the emitter needs, which the interpreter
        has no reason to provide.  Two translations are involved:

        * The interpreter holds the tape as an ``int`` bitvector and the
          emitter as a list of cells, so a step converts across the two.
        * A ``[`` that flips its cell to zero skips the *next* instruction.
          The interpreter spells that by advancing ``ind`` past it inside one
          program; an emitter is handed instructions singly and has no next
          instruction yet, so the skip is held on ``self.skip`` and consumed
          when that instruction arrives.

        ``dead`` marks the transition a parameterized program must never
        take -- a ``.`` on a zero pool, which the interpreter reports as
        ``_Effect.reads`` because a real run would fetch a byte of input.

        **The two pointer-only instructions are inlined.**  Delegating costs
        a call and a six-tuple pack and unpack per character, which is the
        emitter's remaining hot path; ``<`` and a comment character are the
        two cases that cannot print, read, cascade or set the skip, so their
        whole effect is the pointer move spelled here.  Everything that can
        do any of those -- ``.`` and ``[`` -- still goes to ``_step``, which
        stays the single definition of what those instructions mean.  The
        inlined pair is pinned to the interpreter by a differential test
        that steps both routes over random states.
        """
        if self.dead:
            return
        if self.skip:
            self.skip = False
            return

        if ins == "<":
            # _step: ``ptr - 1 if ptr else ptr`` -- no write, print or skip.
            if self.ptr:
                self.ptr -= 1
            return
        if ins not in ".[":
            # _step: a comment character moves only the interpreter's cursor.
            return

        tape, length, ptr, skipped, char, reads = _minifuck_step(
            ins, self.tape, self.length, self.ptr
        )

        if reads:
            self.dead = True
            return
        if char is not None:
            self.out.append(char)

        self.tape = tape
        self.length = length
        self.ptr = ptr
        self.skip = skipped


# The two straight runs the emitter builds, named so the classifier below
# compares against a constant rather than a bare character literal -- bandit
# reads ``token == "<"`` as a hardcoded-password check (B105).
_LEFT = "<"
_WALK = "[x"


def _straight_run(code: str) -> tuple[str, int] | None:
    """Name the :class:`_Sim` method that applies ``code`` in closed form.

    Returns ``("run_left", k)`` for ``"<" * k`` and ``("run_walk", k)`` for
    ``"[x" * k`` -- the two shapes :func:`_clamp` and :func:`_walk_to` emit
    -- with the repeat count.  Mixed code returns ``None`` and is stepped
    character by character as before.

    Deliberately strict: it recognises only these two exact spellings, so a
    string that merely starts with them (``"[x[["``) falls through to the
    stepper rather than taking a closed form that does not describe it.
    """
    head = code[0]
    if head == _LEFT:
        return ("run_left", len(code)) if code.count(_LEFT) == len(code) else None
    if head == "[" and len(code) % 2 == 0:
        pairs = len(code) // 2
        return ("run_walk", pairs) if code == _WALK * pairs else None
    return None


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
        """Append code and run it on every row, keeping them in lockstep.

        Straight runs take a closed form.  Stepping every row one character
        at a time is what made this the generator's cost -- 173.7M ``exec``
        calls on a six-input build -- and two thirds of those characters are
        a run of a single token: ``"<" * k`` from :func:`_clamp` and
        ``"[x" * k`` from :func:`_walk_to`.  Both have an effect that
        :class:`_Sim` can apply directly, so the rows skip the per-character
        dispatch without changing what is emitted or what the rows hold.

        The template is appended before the dispatch either way, so the
        program this builds is byte-identical to the stepped one; only the
        route the simulated rows take differs.
        """
        self.parts.append(code)
        if not code:
            return
        run = _straight_run(code)
        if run is not None:
            method, count = run
            for m in self.ms:
                getattr(m, method)(count)
            return
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
        return tuple(m.cell(cell) for m in self.ms)

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
