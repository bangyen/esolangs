"""One tiny program per registry language, and the stdin it needs.

The per-language test files each grew their own copy of the same protocol
checks -- a snapshot can be hashed, a step past the halt is a no-op,
stepping to completion matches ``run``, and a halting program is proven to
halt.  Those checks say nothing about the language; they say that the
language's adapter honours the VM protocol.  Written once per file they
are sixty-odd near-identical bodies differing only in which ``_Machine``
to import and which program to hand it, which is the shape a table plus a
sweep replaces.

:data:`SAMPLES` is that table: for every name in
:data:`~esolangs.registry.RUNNERS`, the smallest program that reaches the
language's halt, and the stdin it reads on the way (``""`` for the ones
that read nothing).  The programs are *tiny* deliberately -- a hello-world
is the wrong input here, since the sweep runs each entry to completion and
some languages spell a greeting in tens of thousands of steps.

``TestSamplesCoverEveryLanguage`` locks the table against the registry, so
a language added without an entry fails there rather than being silently
skipped.
"""

# The corrected Inject truth machine lives beside the interpreter's own
# tests: the mutation bundle does not inline this module, so a test file
# importing the program from here would fail collection there before any
# mutant ran.  Defined there, imported here.
from tests.interpreters.test_inject import INJECT_TRUTH_MACHINE

# The wiki's street shape: a two-wide road with the instructions in the
# southern lane, walled all round.  ``C`` starts the car, ``^`` increments
# the CPth cell, ``O`` prints it, ``;`` halts.
STREETCODE = "+-----+\n|     |\n|C^^O;|\n+-----+"

# The same street, writing cells 0 and 2 and stepping over cell 1: "=" moves
# CP right without touching the cell it leaves.
STREETCODE_GAP = "+------+\n|      |\n|C^==^;|\n+------+"

# The wiki's truth machine: read a bit, and on 0 print it once and halt.
FLOWCHART_TRUTH_MACHINE = "\n".join(
    [
        "       ( )──┐        ",
        "           / /       ",
        "            │        ",
        "(( ))─\\ \\──< >┬─\\ \\─┐",
        "              │     │",
        "              └─────┘",
    ]
)

# The wiki's cat: the upper loop reads bits onto a deque, the lower pops
# them back off and prints them.
FLOWCHART_CAT = "\n".join(
    [
        "( )──┐   ",
        "  ┌─/ /─┐",
        "  │  │  │",
        "  │\\[ ]/│",
        "  │  │  │",
        "  └─< >─┘",
        "     │   ",
        "  ┌/{ }\\┐",
        "  │  │  │",
        "  │ \\ \\ │",
        "  │  │  │",
        "  └─< >─┘",
        "     │   ",
        "   (( )) ",
    ]
)

# The wiki's prime tester, repaired: a four-bit input port drives a tree of
# gates whose output bit is set for exactly the primes below 16.
CIRCUIT_PRIME_TESTER = "\n".join(
    [
        "       .~..",
        "      /    ..         .-.",
        "     <.----=---------.   o.",
        "    / .~. /.   .---.    .  >.",
        "-4-<     =  >.=--.  o.-=--.  \\",
        "    \\ . . .. /    ..  /       .",
        "     < =    = .------=-----.   >.",
        "      = .~..-=--.~.-.       .-.  a.-:",
        "     / \\    / \\                 .",
        "    .   .===.  .               /",
        "     \\   o.  \\  o.------------.",
        "      .-.     ..",
    ]
)


def bits_of(value: int) -> str:
    """Return ``value`` as four input lines, most significant bit first."""
    return "\n".join(format(value, "04b")) + "\n"


# Languages whose ``run`` writes its output on the step *after* the halt.
# Their interpreters end ``while not machine.halted: machine.step()`` with
# one more ``machine.step()`` to dump the final registers, so "stepping to
# the halt writes what run writes" is false for them by design, and the
# no-op step is the second one past the halt, not the first.
DUMPS_ON_THE_POST_HALT_STEP = frozenset({"Minsky Swap", "RAM0"})

# Languages with no self-halt at all: ``esolangs.run`` stops them from
# outside, by the ``limit``/``cycles`` bound the registry passes it, and a
# VM stepped on its own runs forever.  Nothing about the VM protocol is
# wrong here -- there is simply no halt for a sweep to drive to, so these
# are carried for the checks that do not need one.
NEVER_SELF_HALTS = frozenset({"A Painter Ant", "Suffolk"})

# Languages whose ``step()`` raises when called on an already-halted
# machine, rather than returning without doing anything.
#
# This set is kept, empty, because it is what holds the fix in place.  It
# once held nine languages -- brainfuck, Eval, Factor, Dimensional,
# Modulous, Point Break, Qoibl, S*bleq and Grapheme -- each of which
# indexed off the end of its own program when stepped past its halt.  The
# fifteen hand-written copies of ``test_step_after_halt_is_a_noop``
# happened to cover none of them, so the inconsistency survived precisely
# because the check was written per file instead of swept.
#
# All nine now carry the ``if self.halted: return`` guard the other fifty
# interpreters already had.  ``test_the_post_halt_step_raises_only_where
# _recorded`` compares this set against what actually raises, in both
# directions, so a language that regressed would fail rather than quietly
# rejoining a list nobody rechecks.
RAISES_ON_THE_POST_HALT_STEP: frozenset[str] = frozenset()

# LaserFuck's ``run`` draws the laser's initial heading at random when it
# is not pinned, so its output is not a function of the program alone and
# cannot be compared against a separately-built VM.  ``test_vm.py``'s
# ``test_dump_output_matches_interpreter`` handles this by building both
# sides with the same heading; the sweep just leaves the comparison to it.
NONDETERMINISTIC_AGAINST_RUN = frozenset({"LaserFuck"})

# language -> (program, stdin)
SAMPLES: dict[str, tuple[str, str]] = {
    "123": ("3231", ""),
    "3D Brainfuck": ("+.", ""),
    "3x": ("3!", ""),
    "%^2^-1": ("ie", ""),
    "6-5": ("55A", ""),
    "A Painter Ant": ("Pnn", ""),
    "AddSubJump": ("-1 1 0 -7", ""),
    "ArrowQueue": ("~*+", ""),
    "BF-PDA": ("<@.", ""),
    "BFStack": (">+.", ""),
    "Back": ("-*", ""),
    "BIO": ("0ox;0ix{1ox;};1ix;", ""),
    "Basicfuck": (
        "#basicfuck t=1 r=0~255 o=nearest\n#allocate a\na += 65;\nwrite <- a ;",
        "",
    ),
    "Between": ("'a'v.\n[a]s|3|\n[a]p.\n.x.", ""),
    "bit~": ("~(", ""),
    "Bitdeque": ("PUSH INVERT", ""),
    "BrainIf": ("if 0 output", ""),
    "brainfuck": ("+++[>+++<-]>.", ""),
    "COD": ("~~~~~\n~>))---", ""),
    "Circlefuck": ("+.@", ""),
    "Circuit Diagram": (CIRCUIT_PRIME_TESTER, bits_of(7)),
    "Clockwise": ("+;S;S;S;S;S;+;R\nR             R", ""),
    "Collatz Multiverse": ("x = negativeOne x + negativeOne, DO PRINT.", ""),
    # Every Container program with a container in it runs forever (its own
    # VM test asserts exactly that of "A=0:\n+1 A>=0"); the empty program
    # is the one that reaches a halt.
    "Container": ("", ""),
    # The wiki's truth machine, which halts only on a zero: the "1"
    # branch loops forever, so the halting input is the one to sweep.
    "CV(N)(C)": ("soθɰ̊oθʋi", "0\n"),
    "Decleq": ("-2 5 9 9 9 65 0 0", ""),
    "Dig": (">$5:\n 2 ", ""),
    "Dimensional": ("+.+.+.", ""),
    "Eval": ("0+.", ""),
    "Factor": ("15", ""),
    "Fargo": ("$", "0\n"),
    "Flowchart": (FLOWCHART_TRUTH_MACHINE, "0\n"),
    "Forbin": ("main { x = 1; }", ""),
    "Forþ": ("65.", ""),
    "Grapheme": ("FAFY", ""),
    "Home Row": ("ak;", ""),
    # A corrected truth machine (the wiki's own is inverted -- see the
    # interpreter's module docstring), on the input that halts: the "1"
    # branch loops forever.
    "Inject": (INJECT_TRUTH_MACHINE, "0\n"),
    "Jaune": ("++^", ""),
    "Lamfunc": ("p 5", ""),
    "LaserFuck": ("ÿ   x\n    +\n    o", ""),
    "Minifuck": (".", ""),
    "Minsky Swap": ("+", ""),
    "Modulous": ("[PSH INT 5][DUP][PRT INT]", ""),
    "MyScript": ("var a is 5\nsay a", ""),
    "Nevermind": ("make,x,5\nprint,$x", ""),
    "NoComment": ("ciio", ""),
    "Painfuck": ("pp", ""),
    "Point Break": ("LET zero:=0", ""),
    "Polynomial": ("f(x) = x^2+4", ""),
    "Qoibl": ("we y we yyeeee we\ntt qe y qe tt", ""),
    "RAM0": ("ZA", ""),
    "ROTfuck": (".", ""),
    "S*bleq": ("-3 11 3", ""),
    "SLOW ACV MAMMALIAN": ("SEED SEED SEED CONSUME PRONOUNCE", ""),
    "Sophie": ("#$5.", ""),
    "Streetcode": (STREETCODE, ""),
    "Suffolk": ("!" * 66 + "<.", ""),
    "Suptiftam": ("x=7", ""),
    "Taglate": ("abc\ni", ""),
    "Unsquare": ("Io", ""),
    "WII2D": (">~.\n!", ""),
    "ZTOALC L": ("10\nprint 65", ""),
}
