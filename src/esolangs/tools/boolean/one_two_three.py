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

All four one-input, all sixteen two-input and all 256 three-input tables
are covered by the plans below, over templates carrying each placeholder
once in name order.  A wider table raises :class:`ValueError`, the shape
``%^2^-1`` already uses for the arities it does not derive; see
``docs/limitations.md``.

Three inputs did not fall to the lockstep search that settled the first
two.  Shortest-first enumeration reaches only 148 of the 256 tables by ten
symbols, and each further symbol multiplies the space by about four, so the
remainder came from sampling the shape the short plans already take -- a
``3``-sparse skeleton whose slots are separated by short literal runs.

The last table to fall was ``01111110``, TRUE exactly when the inputs are
not all equal.  It is the one *popcount-only* signature the counter cannot
reach on its own: with uniform ±1 fills the displacement after three embeds
is ``3 - 2·popcount`` modulo four, which is 3 for an even popcount and 1 for
an odd one, so the bare counter carries only popcount **parity** at three
inputs.  ``0110`` -- TRUE at popcount 1 and 2 -- is not a parity function,
so it needs ``3``'s TRUE-backward re-run rather than a longer decode tail,
and it was found by mutating the plans for the neighbouring tables rather
than by sampling.

Every plan loops by a *proven state revisit*, never by unbounded growth.
That is a hard requirement rather than an aesthetic one:
:func:`~esolangs.vm.run_until_halt_or_cycle` never returns on a program
whose pointer marches right forever, so a plan with such a row would hang
the harness instead of reporting a 1.  The suite checks this directly.
"""

from esolangs.tools.boolean.helpers import _validate_truth_table, essential_inputs

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


#: Verified three-input plans, indexed by truth table.
#:
#: All 256 are covered.  A flat length-bounded sweep plateaus at 148 of
#: them by ten symbols and cannot afford eleven, so most of these were
#: found by sampling the *shape* the short plans take -- a ``3``-sparse
#: skeleton with short literal runs between the slots -- and the last
#: one by mutating the plans for neighbouring tables.
_THREE_INPUT_PLAN = {
    "00000000": "3{X0}{X1}{X2}31",
    "00000001": "{X0}3{X1}22{X2}311",
    "00000010": "{X0}{X1}{X2}1111",
    "00000011": "12{X0}{X1}3{X2}313",
    "00000100": "{X0}1{X1}1{X2}11",
    "00000101": "{X0}1{X1}1{X2}11313",
    "00000110": "{X0}3{X1}{X2}3111",
    "00000111": "{X0}312{X1}{X2}311",
    "00001000": "{X0}13{X1}313{X2}1",
    "00001001": "11{X0}1{X1}{X2}11",
    "00001010": "13{X0}3{X1}1{X2}31",
    "00001011": "{X0}{X1}{X2}1111313",
    "00001100": "13{X0}{X1}31{X2}11",
    "00001101": "12{X0}3{X1}{X2}1311",
    "00001110": "{X0}13{X1}11{X2}31",
    "00001111": "11{X0}13{X1}{X2}11",
    "00010000": "1{X0}{X1}331{X2}13",
    "00010001": "1{X0}{X1}31{X2}1311",
    "00010010": "1{X0}{X1}31{X2}3131",
    "00010011": "{X0}12{X1}1311311{X2}113",
    "00010100": "1{X0}{X1}13{X2}131",
    "00010101": "21{X0}{X1}21121121{X2}11",
    "00010110": "{X0}{X1}{X2}121111",
    "00010111": "11112{X0}1{X1}323{X2}111",
    "00011000": "13{X0}{X1}313{X2}1",
    "00011001": "11{X0}1{X1}2{X2}111",
    "00011010": "{X0}1113{X1}13{X2}1",
    "00011011": "{X0}33{X1}131{X2}12311",
    "00011100": "13{X0}{X1}31{X2}13",
    "00011101": "11{X0}1{X1}2113{X2}1",
    "00011110": "13{X0}{X1}31{X2}1",
    "00011111": "3223{X0}1113{X1}1{X2}111",
    "00100000": "1{X0}112{X1}3{X2}3113",
    "00100001": "1{X0}131{X1}1{X2}13",
    "00100010": "3{X0}311{X1}1{X2}1",
    "00100011": "11{X0}1{X1}3{X2}311",
    "00100100": "{X0}1{X1}111113{X2}311",
    "00100101": "11211{X0}13{X1}3131{X2}1",
    "00100110": "11{X0}1{X1}{X2}1111",
    "00100111": "113{X0}1{X1}{X2}11311",
    "00101000": "{X0}{X1}11{X2}1111",
    "00101001": "{X0}111{X1}1{X2}1",
    "00101010": "331122{X0}1{X1}131{X2}311",
    "00101011": "{X0}2132131131{X1}1{X2}31",
    "00101100": "{X0}1{X1}13{X2}311",
    "00101101": "13{X0}{X1}3111{X2}1",
    "00101110": "{X0}2{X1}1131{X2}13111",
    "00101111": "{X0}1113{X1}1{X2}1",
    "00110000": "1{X0}1111{X1}13231{X2}1",
    "00110001": "1{X0}131{X1}13{X2}1",
    "00110010": "11{X0}1{X1}3{X2}313",
    "00110011": "3{X0}311{X1}13{X2}1",
    "00110100": "3231{X0}{X1}111311{X2}11",
    "00110101": "{X0}1333311{X1}1{X2}1311",
    "00110110": "1{X0}21{X1}1113111{X2}1",
    "00110111": "{X0}3312{X1}1323121{X2}11",
    "00111000": "{X0}1{X1}13{X2}31",
    "00111001": "3311{X0}1{X1}113111{X2}1",
    "00111010": "1{X0}113{X1}13{X2}1",
    "00111011": "{X0}122111213{X1}{X2}31",
    "00111100": "{X0}{X1}113{X2}31",
    "00111101": "{X0}111{X1}13{X2}1",
    "00111110": "1122{X0}2{X1}113{X2}31111",
    "00111111": "{X0}2{X1}1213{X2}2311113",
    "01000000": "{X0}111{X1}1{X2}11",
    "01000001": "{X0}{X1}11{X2}111",
    "01000010": "{X0}1313113{X1}11{X2}13",
    "01000011": "1312{X0}221{X1}1{X2}31",
    "01000100": "3{X0}3{X1}1{X2}111",
    "01000101": "{X0}1{X1}1{X2}1131",
    "01000110": "11{X0}11{X1}11{X2}1",
    "01000111": "{X0}1211{X1}3131{X2}11",
    "01001000": "122331{X0}21{X1}1111{X2}1",
    "01001001": "11{X0}1{X1}{X2}1131",
    "01001010": "1321{X0}113{X1}113{X2}1",
    "01001011": "1{X0}21{X1}131311{X2}1",
    "01001100": "331321{X0}2{X1}13{X2}111",
    "01001101": "{X0}{X1}111313{X2}1",
    "01001110": "{X0}2133132{X1}1311{X2}1",
    "01001111": "{X0}1113{X1}1{X2}11",
    "01010000": "{X0}13{X1}13{X2}111",
    "01010001": "{X0}13{X1}313{X2}11",
    "01010010": "1{X0}3{X1}31{X2}3131",
    "01010011": "1331{X0}31{X1}232111{X2}1",
    "01010100": "2{X0}113{X1}13{X2}1131",
    "01010101": "3{X0}{X1}3{X2}111",
    "01010110": "{X0}111211{X1}112{X2}1131",
    "01010111": "1{X0}311{X1}231{X2}113",
    "01011000": "{X0}13{X1}3113{X2}1",
    "01011001": "12{X0}3{X1}131131{X2}121",
    "01011010": "33{X0}3{X1}23313{X2}1111",
    "01011011": "21211{X0}213{X1}3113{X2}1",
    "01011100": "{X0}131121{X1}3{X2}111",
    "01011101": "{X0}{X1}1133113{X2}1",
    "01011110": "33{X0}312{X1}13{X2}1111",
    "01011111": "11{X0}31{X1}2213{X2}111",
    "01100000": "{X0}11132{X1}{X2}31",
    "01100001": "{X0}{X1}11322111311{X2}13",
    "01100010": "{X0}12{X1}1{X2}1111",
    "01100011": "1312{X0}12121{X1}{X2}31",
    "01100100": "{X0}1211{X1}11{X2}1",
    "01100101": "{X0}1211{X1}11{X2}131",
    "01100110": "3{X0}3{X1}{X2}1111",
    "01100111": "{X0}1211{X1}131{X2}121",
    "01101000": "{X0}{X1}2{X2}111111",
    "01101001": "{X0}{X1}{X2}11111",
    "01101010": "{X0}{X1}211{X2}1111",
    "01101011": "{X0}{X1}{X2}111131",
    "01101100": "{X0}{X1}21{X2}131131111",
    "01101101": "{X0}{X1}{X2}1131311",
    "01101110": "1313311{X0}{X1}3{X2}11333311",
    "01101111": "11{X0}13{X1}11{X2}1",
    "01110000": "2{X0}1132131{X1}113{X2}13",
    "01110001": "{X0}{X1}111311111333{X2}1",
    "01110010": "12131{X0}12{X1}{X2}31331",
    "01110011": "11{X0}1{X1}32112311{X2}1",
    "01110100": "1{X0}211{X1}113{X2}1",
    "01110101": "1{X0}1331{X1}132{X2}21111",
    "01110110": "1312{X0}1211{X1}1313{X2}1",
    "01110111": "3{X0}3{X1}1113{X2}1",
    "01111000": "1{X0}13111212{X1}{X2}1311",
    "01111001": "1{X0}{X1}1313131{X2}1",
    "01111010": "31311{X0}13{X1}113{X2}1",
    "01111011": "133132{X0}121{X1}{X2}131311",
    "01111100": "{X0}111{X1}13{X2}11",
    "01111101": "{X0}{X1}11113{X2}1",
    "01111110": "1313311{X0}{X1}3{X2}131233311",
    "01111111": "{X0}{X1}{X2}121121111",
    "10000000": "33{X0}{X1}{X2}11",
    "10000001": "33{X0}{X1}2{X2}111",
    "10000010": "{X0}{X1}112{X2}11",
    "10000011": "{X0}111{X1}13{X2}31",
    "10000100": "{X0}{X1}1331{X2}13",
    "10000101": "212{X0}3131{X1}211{X2}131",
    "10000110": "{X0}33{X1}11{X2}1",
    "10000111": "13{X0}11112{X1}2{X2}1311",
    "10001000": "3{X0}3{X1}{X2}1",
    "10001001": "13{X0}2{X1}{X2}11",
    "10001010": "13{X0}323{X1}3{X2}1",
    "10001011": "1{X0}131{X1}1{X2}31",
    "10001100": "1131121{X0}{X1}213{X2}1",
    "10001101": "13{X0}2{X1}13{X2}1",
    "10001110": "113{X0}12{X1}{X2}1",
    "10001111": "13{X0}23{X1}{X2}1",
    "10010000": "{X0}12{X1}{X2}111",
    "10010001": "{X0}12{X1}12{X2}111",
    "10010010": "{X0}1{X1}1{X2}1",
    "10010011": "{X0}1{X1}1{X2}13113",
    "10010100": "{X0}{X1}{X2}111",
    "10010101": "{X0}{X1}2112{X2}111",
    "10010110": "{X0}{X1}11{X2}1",
    "10010111": "{X0}{X1}11{X2}13113",
    "10011000": "131{X0}1{X1}{X2}1",
    "10011001": "3{X0}3{X1}{X2}11",
    "10011010": "{X0}11132{X1}213{X2}131",
    "10011011": "11{X0}3313{X1}33333113{X2}13",
    "10011100": "11{X0}12{X1}113111{X2}1",
    "10011101": "{X0}{X1}{X2}1113113",
    "10011110": "{X0}{X1}113113{X2}1",
    "10011111": "11{X0}13{X1}{X2}1",
    "10100000": "1{X0}23{X1}31{X2}1",
    "10100001": "{X0}13{X1}13{X2}1",
    "10100010": "{X0}3{X1}1312{X2}11",
    "10100011": "{X0}3{X1}231{X2}1",
    "10100100": "{X0}13{X1}113{X2}1",
    "10100101": "{X0}23{X1}31{X2}11",
    "10100110": "{X0}3{X1}131{X2}1",
    "10100111": "12{X0}31{X1}131{X2}1",
    "10101000": "{X0}13112{X1}3{X2}1",
    "10101001": "{X0}{X1}131131{X2}1",
    "10101010": "13{X0}{X1}1{X2}",
    "10101011": "13{X0}22{X1}3{X2}",
    "10101100": "{X0}31{X1}31{X2}13",
    "10101101": "112{X0}3{X1}3{X2}1",
    "10101110": "113{X0}1{X1}{X2}",
    "10101111": "11{X0}13{X1}{X2}",
    "10110000": "{X0}1113{X1}11{X2}31331",
    "10110001": "1321{X0}332{X1}3211{X2}1",
    "10110010": "132{X0}1{X1}111311{X2}1",
    "10110011": "1{X0}1312{X1}231{X2}13",
    "10110100": "112{X0}{X1}2{X2}133111",
    "10110101": "{X0}{X1}3321133{X2}333131",
    "10110110": "{X0}{X1}11{X2}1133113331",
    "10110111": "31313{X0}21{X1}2311{X2}1",
    "10111000": "1321{X0}2{X1}3{X2}1",
    "10111001": "112{X0}122{X1}3131{X2}11",
    "10111010": "1{X0}131{X1}13{X2}",
    "10111011": "131{X0}1{X1}23{X2}",
    "10111100": "{X0}{X1}3231211{X2}31",
    "10111101": "1312{X0}{X1}3{X2}1",
    "10111110": "{X0}{X1}11113{X2}",
    "10111111": "{X0}1113{X1}12{X2}",
    "11000000": "33{X0}{X1}3{X2}131",
    "11000001": "{X0}133{X1}13{X2}13",
    "11000010": "33{X0}{X1}321{X2}31",
    "11000011": "{X0}{X1}113{X2}11",
    "11000100": "{X0}133{X1}13{X2}11",
    "11000101": "{X0}1113{X1}311{X2}1",
    "11000110": "11212{X0}2{X1}1131{X2}13",
    "11000111": "{X0}1{X1}13{X2}11",
    "11001000": "1311111{X0}1{X1}3{X2}13",
    "11001001": "1312{X0}3{X1}{X2}1",
    "11001010": "1{X0}1132{X1}3{X2}1",
    "11001011": "{X0}1{X1}13111{X2}1",
    "11001100": "3{X0}3{X1}23{X2}31",
    "11001101": "11222{X0}11121{X1}3{X2}1",
    "11001110": "33{X0}12{X1}3{X2}31",
    "11001111": "3123122{X0}2{X1}13{X2}311",
    "11010000": "{X0}1113221{X1}3331{X2}13",
    "11010001": "{X0}133{X1}13{X2}1",
    "11010010": "1121{X0}{X1}31{X2}1313",
    "11010011": "{X0}1{X1}13{X2}1",
    "11010100": "112{X0}{X1}131{X2}3131113",
    "11010101": "{X0}{X1}2111311121{X2}11",
    "11010110": "112{X0}{X1}131{X2}1",
    "11010111": "{X0}{X1}113{X2}1",
    "11011000": "13{X0}13312{X1}13{X2}1",
    "11011001": "2133113{X0}12{X1}33{X2}11",
    "11011010": "11{X0}13{X1}3{X2}1",
    "11011011": "112{X0}1{X1}313{X2}1",
    "11011100": "1313{X0}1{X1}3{X2}1",
    "11011101": "3{X0}3{X1}13{X2}1",
    "11011110": "112{X0}1{X1}31{X2}1",
    "11011111": "1{X0}131{X1}12311{X2}1",
    "11100000": "{X0}1113{X1}31{X2}1",
    "11100001": "1312{X0}111{X1}31{X2}1",
    "11100010": "{X0}133{X1}3121{X2}31",
    "11100011": "31113{X0}{X1}13111{X2}31",
    "11100100": "{X0}122{X1}1{X2}1131131",
    "11100101": "11{X0}13{X1}311{X2}1",
    "11100110": "13121{X0}3131{X1}2{X2}31",
    "11100111": "122{X0}1{X1}1131133{X2}1",
    "11101000": "13{X0}2{X1}{X2}1",
    "11101001": "132{X0}{X1}{X2}1",
    "11101010": "132{X0}{X1}{X2}",
    "11101011": "{X0}{X1}113{X2}",
    "11101100": "1{X0}211{X1}311{X2}1",
    "11101101": "1121{X0}11{X1}31{X2}1",
    "11101110": "13{X0}2{X1}{X2}",
    "11101111": "{X0}11132{X1}{X2}",
    "11110000": "{X0}13{X1}1{X2}13",
    "11110001": "{X0}13{X1}1{X2}111",
    "11110010": "{X0}13{X1}1{X2}1",
    "11110011": "{X0}3{X1}{X2}3121",
    "11110100": "{X0}13{X1}1{X2}11",
    "11110101": "13321{X0}3{X1}1{X2}21111",
    "11110110": "112{X0}3{X1}11{X2}1",
    "11110111": "{X0}132{X1}{X2}2112121111",
    "11111000": "{X0}132{X1}{X2}1",
    "11111001": "112{X0}3{X1}{X2}1",
    "11111010": "112{X0}3{X1}{X2}",
    "11111011": "{X0}13{X1}12{X2}",
    "11111100": "33{X0}32{X1}2{X2}31",
    "11111101": "{X0}{X1}{X2}111311",
    "11111110": "{X0}132{X1}{X2}",
    "11111111": "3{X0}{X1}{X2}",
}


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

    One-, two- and three-input tables are covered completely.  A wider
    table raises :class:`ValueError`: an ignored input still has to be
    embedded, every fill moves the pointer, and the pointer phase *is* the
    computed value here, so a trailing inert embed shifts the very quantity
    the plan decodes.  See ``docs/limitations.md``.
    """
    n = _validate_truth_table(truth_table)
    if n > 3:
        essential = len(essential_inputs(truth_table, n))
        raise ValueError(
            "123's boolean generator derives one-, two- and three-input "
            f"tables; {truth_table!r} has {n} inputs ({essential} essential). "
            "See docs/limitations.md",
        )
    plans = (_ONE_INPUT_PLAN, _TWO_INPUT_PLAN, _THREE_INPUT_PLAN)[n - 1]
    return _in_name_order(plans[truth_table], n)
