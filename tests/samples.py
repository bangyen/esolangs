r"""One tiny program per registry language, and the stdin it needs."""

# The corrected Inject truth.
# tests: the mutation bundle.
# importing the program from.
# mutant ran.
from tests.interpreters.test_inject import INJECT_TRUTH_MACHINE

# The wiki's street shape: a.
# southern lane, walled all.
# the CPth cell, ``O`` prints.
STREETCODE = "+-----+\n|     |\n|C^^O;|\n+-----+"

# The same street, writing.
# CP right without touching the.
STREETCODE_GAP = "+------+\n|      |\n|C^==^;|\n+------+"

# The wiki's truth machine:.
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

# The wiki's cat: the upper.
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

# The wiki's prime tester,.
# gates whose output bit is set.
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
    r"""Return ``value`` as four input lines, most significant bit first."""
    return "\n".join(format(value, "04b")) + "\n"


# Languages whose ``run``.
# Their interpreters end.
# one more ``machine.step()``.
# the halt writes what run.
# no-op step is the second one.
# .
# This is a fact about the.
# to learn it: each of the.
# ``dumps_on_the_post_halt_step.
# :attr:`esolangs.vm.VM.dumps_on.
# mechanism.
# .
# **Do not derive this set from.
# and reading the attribute.
# reason not to:.
# compares the declaration.
# its halt and stepping once.
# flag in both directions.
# flag to itself, so a language.
# keep a trait nobody rechecked.
# .
# Parsing the interpreters for.
# dump sites are uniform (all.
# the *timing* is not visible.
# guarded ``step`` and is.
# is external and its.
# this answer without building.
# any more cheaply than the.
DUMPS_ON_THE_POST_HALT_STEP = frozenset(
    {
        "Minsky Swap",
        "RAM0",
        "Bitdeque",
        "LaserFuck",
        "ArrowQueue",
        "Point Break",
        "Back",
    }
)

# Languages with no self-halt.
# outside and a VM stepped on.
# protocol is wrong here --.
# to, so these are carried for.
# .
# Each of the two declares.
# :attr:`esolangs.vm.VM.self_hal.
# obvious ``while not.
# How each one is stopped from.
# is where the machine that.
# reasons the one above does,.
# ``test_the_halting_convention_.
# against the traits in both.
NEVER_SELF_HALTS = frozenset({"A Painter Ant", "Suffolk"})

# Languages whose ``step()``.
# machine, rather than.
# .
# This set is kept, empty,.
# once held nine languages --.
# Modulous, Point Break, Qoibl,.
# indexed off the end of its.
# fifteen hand-written copies.
# happened to cover none of.
# because the check was written.
# .
# All nine now carry the ``if.
# interpreters already had.
# _recorded`` compares this set.
# directions, so a language.
# rejoining a list nobody.
RAISES_ON_THE_POST_HALT_STEP: frozenset[str] = frozenset()

# LaserFuck's ``run`` draws the.
# is not pinned, so its output.
# cannot be compared against a.
# ``test_dump_output_matches_int.
# sides with the same heading;.
NONDETERMINISTIC_AGAINST_RUN = frozenset({"LaserFuck"})

# language -> (program, stdin).
SAMPLES: dict[str, tuple[str, str]] = {
    "123": ("3231", ""),
    "3D Brainfuck": ("+.", ""),
    "3x": ("3!", ""),
    "%^2^-1": ("ie", ""),
    "6-5": ("55A", ""),
    "A Painter Ant": ("Pnn", ""),
    "Algebraic Programming Language": ("a + 1", "41\n"),
    "AddSubJump": ("-1 1 0 -7", ""),
    "Alight": ("begin;var c;set c 65;out c;end;", ""),
    "ArrowQueue": ("~*+", "0"),
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
    # Every Container program with.
    # VM test asserts exactly that.
    # is the one that reaches a.
    "Container": ("", ""),
    # The wiki's truth machine,.
    # branch loops forever, so the.
    "CV(N)(C)": ("soθɰ̊oθʋi", "0\n"),
    "Decleq": ("-2 5 9 9 9 65 0 0", ""),
    "Dig": (">$5:\n 2 ", ""),
    "Dimensional": ("+.+.+.", ""),
    "DINAC": ("OUT 'a", ""),
    "Eval": ("0+.", ""),
    "Factor": ("15", ""),
    "Fargo": ("$", "0\n"),
    "Flowchart": (FLOWCHART_TRUTH_MACHINE, "0\n"),
    "Forbin": ("main { x = 1; }", ""),
    "Forþ": ("65.", ""),
    "function x(y)": ("function f()\n[[~]]", "a\n"),
    "Grapheme": ("FAFY", ""),
    "Home Row": ("ak;", ""),
    # A corrected truth machine.
    # interpreter's module.
    # branch loops forever.
    "Inject": (INJECT_TRUTH_MACHINE, "0\n"),
    "Interprogck8": ("nNnN\ndiv", ""),
    "Jaune": ("++^", ""),
    "Lamfunc": ("p 5", ""),
    "LaserFuck": ("ÿ   x\n    +\n    o", ""),
    "Minifuck": (".", ""),
    "Minsky Swap": ("+", ""),
    "Modulous": ("[PSH INT 5][DUP][PRT INT]", ""),
    "MyScript": ("var a is 5\nsay a", ""),
    "Nevermind": ("make,x,5\nprint,$x", ""),
    "NoComment": ("ciio", ""),
    "Packlang": (
        "Package : IO {\n  Integer main {\n    charPut(65);\n    0;\n  }\n} p;",
        "",
    ),
    "Painfuck": ("pp", ""),
    "Point Break": ("LET zero:=0", "0"),
    "Polynomial": ("f(x) = x^2+4", ""),
    "Qoibl": ("we y we yyeeee we\ntt qe y qe tt", ""),
    "RAM0": ("ZA", ""),
    "ROTfuck": (".", ""),
    "S*bleq": ("-3 11 3", ""),
    "SLOW ACV MAMMALIAN": ("SEED SEED SEED CONSUME PRONOUNCE", ""),
    "Sophie": ("#$5.", ""),
    "Streetcode": (STREETCODE, ""),
    "Super SNUSP": ('"65.', ""),
    "Suffolk": ("!" * 66 + "<.", ""),
    "Suptiftam": ("x=7", ""),
    "Taglate": ("abc\ni", ""),
    "Unsquare": ("Io", ""),
    "WII2D": (">~.\n!", ""),
    "ZTOALC L": ("10\nprint 65", ""),
}
