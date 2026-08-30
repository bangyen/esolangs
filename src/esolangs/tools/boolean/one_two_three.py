r"""Boolean-function generator for 123, under the termination convention.

123 has no usable input command for a decision tree -- its ``,`` equivalent
(``2`` at location -3) reads real stdin -- so this is a *parameterized*
generator: the template's ``{Xi}`` placeholders become ``1`` for a one and
``2`` for a zero, and the harness instantiates one program per input
combination.  Both fills are one character, so no instantiation leaks its
inputs through ``len()``.

**The answer is the halting behaviour, not printed output.**  Halt means 0
and a proven loop means 1, the convention already used here for ArrowQueue
and Point Break; the verdict comes from
:func:`esolangs.vm.run_until_halt_or_cycle`, so a loop is proved by a state
revisit rather than assumed from a fuel cap.

Why that convention and not printing
------------------------------------

Flipping a bit is XOR, so a straight-line ``1``/``2`` program is affine by
construction: the printing route reaches exactly the eight affine tables at
``n == 2`` (the constants, the two projections, their negations, XOR and
XNOR) and cannot express AND.  Termination escapes that bound because the
verdict accumulates over passes instead of reading one cell.

``docs/walls.md`` recorded the termination route as capped in turn, at the
*monotone* tables, for a verified union of nine of the sixteen.  That
ceiling belongs to the displacement-neutral ``12``/``21`` setter it fixed,
not to the language.  Under that setter every instantiation stays in
position lockstep, so a set bit can only add a pass and never remove one,
and the computed table is monotone by construction.  The ±1 setter used here
is *not* neutral: ``1`` moves the pointer left and ``2`` moves it right, so
the two fills displace it oppositely, the pointer phase itself carries
information, and the looping set need not be upward-closed.  That is what
puts XOR (``0110``) and NAND (``1110``) in reach.  The neutral setter was
chosen there for the *printing* route, which needs the rows to print
together; termination does not need them to.

The mechanism
-------------

With the ±1 fill the pointer's displacement after the embeds is
``(#zeros - #ones)``, and the ``-4 -> 0`` wrap makes that a counter modulo
four.  A tail of ``1``s decodes it: ``{X0}{X1}`` followed by ``k`` ones
computes a function of the input *popcount* alone -- rows ``01`` and ``10``
always agree -- sweeping XNOR at ``k == 2`` and XOR at ``k == 4``.
Asymmetric tables need ``3``, which re-runs the segment before it while the
tested bit is TRUE and so makes the pass count input-dependent.

Coverage
--------

All four one-input and all sixteen two-input tables are covered by the plans
below, found by lockstep search over templates carrying each placeholder
once in name order.  A wider table raises :class:`ValueError`, the shape
``%^2^-1`` already uses for the arities it does not derive; see
``docs/limitations.md``.

Every plan loops by a *proven state revisit*, never by unbounded growth.
That is a hard requirement rather than an aesthetic one:
:func:`~esolangs.vm.run_until_halt_or_cycle` never returns on a program
whose pointer marches right forever, so a plan with such a row would hang
the harness instead of reporting a 1.  The suite checks this directly.
"""

from esolangs.tools.boolean.helpers import _validate_truth_table

__all__ = ["one_two_three"]

#: ``{Xi}`` fills.  One character each, so instantiations are equal length.
ONE, ZERO = "1", "2"

#: Verified one-input plans, indexed by truth table.
_ONE_INPUT_PLAN = {
    "00": "{X0}11",
    "01": "{X0}111",
    "10": "{X0}1",
    "11": "3{X0}",
}

#: Verified two-input plans, indexed by truth table.
#:
#: Every row of every entry is a proven halt or a proven state-revisit
#: cycle.  ``0110`` (XOR) and ``1110`` (NAND) are the two that the monotone
#: ceiling in ``docs/walls.md`` placed out of reach.
_TWO_INPUT_PLAN = {
    "0000": "{X0}{X1}111",
    "0001": "{X0}12{X1}111",
    "0010": "11{X0}1{X1}1",
    "0011": "13{X0}{X1}31",
    "0100": "{X0}1{X1}111",
    "0101": "3{X0}3{X1}111",
    "0110": "{X0}{X1}1111",
    "0111": "{X0}1113{X1}1",
    "1000": "33{X0}{X1}1",
    "1001": "{X0}{X1}11",
    "1010": "13{X0}{X1}",
    "1011": "{X0}1113{X1}",
    "1100": "{X0}13{X1}11",
    "1101": "{X0}13{X1}1",
    "1110": "{X0}13{X1}",
    "1111": "3{X0}{X1}",
}


def _essential_inputs(truth_table: str, n: int) -> list[int]:
    """Which inputs the table actually depends on."""
    return [
        i
        for i in range(n)
        if any(
            truth_table[row] != truth_table[row ^ (1 << (n - 1 - i))]
            for row in range(2**n)
        )
    ]


def _in_name_order(body: str, n: int) -> str:
    """Return ``body`` once its slots are known to be in ascending order.

    The repo-wide invariant is that a template emits ``{X0}`` before
    ``{X1}``; asserting it here keeps a mistyped plan from shipping.
    """
    positions = [body.index(f"{{X{i}}}") for i in range(n)]
    if positions != sorted(positions):
        raise ValueError(f"template {body!r} emits slots out of name order")
    return body


def one_two_three(truth_table: str) -> str:
    """Build a 123 template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    The template's ``{Xi}`` placeholders take ``1`` for a one and ``2`` for
    a zero.  The instantiated program's answer is its *halting* behaviour --
    it halts for a 0 and loops for a 1 -- so the harness decides it with
    :func:`esolangs.vm.run_until_halt_or_cycle` rather than reading output.

    One- and two-input tables are covered completely.  A wider table raises
    :class:`ValueError`: an ignored input still has to be embedded, every
    fill moves the pointer, and the pointer phase *is* the computed value
    here, so a trailing inert embed shifts the very quantity the plan
    decodes.  See ``docs/limitations.md``.
    """
    n = _validate_truth_table(truth_table)
    if n == 0:
        raise ValueError("123 needs at least one input")
    if n > 2:
        essential = len(_essential_inputs(truth_table, n))
        raise ValueError(
            "123's boolean generator derives one- and two-input tables; "
            f"{truth_table!r} has {n} inputs ({essential} essential). "
            "See docs/limitations.md",
        )
    plans = _ONE_INPUT_PLAN if n == 1 else _TWO_INPUT_PLAN
    return _in_name_order(plans[truth_table], n)
