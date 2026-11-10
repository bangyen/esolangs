"""The execution and inspection interface, without adapters or registry imports."""

from typing import Protocol, runtime_checkable

from esolangs.runtime._capabilities import IpShape


@runtime_checkable
class VM(Protocol):
    """A step-capable interpreter wrapper.

    ``ip``/``memory``/``stack`` are language-shaped.
    """

    def step(self) -> None:
        """Execute one command, advancing the machine."""

    @property
    def halted(self) -> bool:
        """Whether the machine has finished executing."""

    @property
    def output(self) -> str:
        """Everything the machine has written so far."""

    @property
    def ip(self) -> int | tuple[int, ...] | None:
        """The current code/instruction position, language-shaped.

        An index, a coordinate tuple, or ``None`` once the agent is
        consumed.  Tuple arity is unstable within a run (a language may
        change shape to ``None`` or ``()``, or grow and shrink), so size
        nothing to the initial arity;
        :meth:`~esolangs.debugger.Debugger.break_at` checks kind, not arity.
        For grid languages the leading components are row then column, never
        x then y; others report a tuple without being grids, and
        ``describe(...)["state_model"]`` separates them.
        """

    @property
    def memory(self) -> list[int]:
        """The addressable cells, or ``[]`` where there is no such store."""

    @property
    def ptr(self) -> int | None:
        """The tape pointer, where the machine has one.

        ``None`` where there is no such thing to point with: a stack, a
        grid, a register file.  Not every tape machine spells it the same
        way (a property here, a plain attribute there), so the adapter
        reads it by ``getattr`` and the protocol only promises the read.
        """

    @property
    def stack(self) -> list[object]:
        """The stack, or ``[]`` where the language has none."""

    @property
    def ip_shape(self) -> IpShape:
        """How to read :attr:`ip` as a place in the source, if at all.

        ``"offset"`` (default) counts characters; ``"grid"`` is row, column,
        then heading; ``"line"`` starts with a line number; ``"opaque"`` is
        a real position that is not a place in the source.  Every tuple
        ``ip`` declares one of the last three
        (``test_a_positional_ip_says_what_it_counts``): a frame stack or
        a depth and cursor all look like ``(row, col)``.
        """

    @property
    def views(self) -> tuple[tuple[str, str], ...]:
        """The machine's own named state, as ``(name, text)`` pairs.

        Derived from its public property descriptors, so it cannot drift.
        """

    @property
    def self_halts(self) -> bool:
        """Whether the program can reach a halt of its own.

        ``False`` where the *language* has no halt: bound the run.  It
        does not promise a program runs forever -- a read can run out of
        input and end the program, and another language runs forever.
        No tally of carriers here; ``[n for n in
        list_languages() if describe(n)["self_halts"]]`` cannot drift.
        """

    @property
    def dumps_on_the_post_halt_step(self) -> bool:
        """Whether the output arrives on the step *after* the halt.

        A caller stopping at ``halted`` holds ``""``; one more ``step()``
        writes what ``run`` writes.
        """

    @property
    def eof_is_a_value(self) -> bool:
        """Whether a read past the end of the input yields a value here.

        The norm raises :class:`~esolangs.exceptions.InputExhaustedError`;
        ``True`` marks the languages that take a value instead, so an
        underfed program answers a different row.  Some are neither: a
        flag may be ``True`` yet the run halts on the read; another may be
        ``False`` yet the read *ends* the program.  A cyclic reader
        (``input_shape`` ``char_stream_cyclic``, Clockwise) never reaches an
        end to underfeed.  Every other language reading stdin, swept one line
        short, matches its flag.
        """

    @property
    def steppable_to_answer(self) -> bool:
        """Whether stepping this language ever reaches the answer.

        ``False`` where ``describe(n)["steppable_to_answer"]`` is false:
        the answer is the render after the walk is proven periodic (three
        million steps leave ``output`` empty).  Distinct from
        ``self_halts``, which a language carries while still writing its
        answer.  Use :func:`esolangs.run`.
        """
