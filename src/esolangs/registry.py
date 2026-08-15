"""Single source of truth for the languages the package supports.

Each :class:`Language` describes a language's generator (if any), its
interpreter (if any), and how a program is handed to that interpreter. The
public API, the tools, and the test suite all derive from this table, so
adding a language is a one-place change.
"""

from collections.abc import Callable
from dataclasses import dataclass

from esolangs.tools import generate as _generate


@dataclass(frozen=True)
class Language:
    """Metadata for one language.

    ``id`` is the language's canonical internal identifier: a snake_case,
    valid-Python-identifier slug used for the interpreter module, the
    generator function, and the test file, so every internal reference to a
    language uses the same token.  ``generator`` produces a program that
    prints a text (None if the language has no generator).  ``interpreter``
    is the dotted module under ``esolangs.interpreters`` that runs programs
    (None if the executable lives elsewhere, e.g. in extra/).  ``split``
    passes the program split into lines to the interpreter, and ``kwargs``
    holds any extra run() keyword arguments as (name, value) pairs.
    """

    name: str
    generator: Callable[[str], str] | None = None
    interpreter: str | None = None
    split: bool = False
    kwargs: tuple[tuple[str, int], ...] = ()
    id: str = ""


def _kw(**kwargs: int) -> tuple[tuple[str, int], ...]:
    return tuple(kwargs.items())


LANGUAGES: dict[str, Language] = {
    "ABCDirection": Language(
        "ABCDirection",
        id="abcdirection",
        interpreter="tape_based.abcdirection",
    ),
    "AddSubJump": Language(
        "AddSubJump",
        _generate.add_sub_jump,
        "register_based.add_sub_jump",
        id="add_sub_jump",
    ),
    "A Painter Ant": Language(
        "A Painter Ant",
        id="a_painter_ant",
        interpreter="other.a_painter_ant",
    ),
    "123": Language(
        "123",
        _generate.one_two_three,
        "tape_based.one_two_three",
        id="one_two_three",
    ),
    "2 Bits, 1 Byte": Language(
        "2 Bits, 1 Byte",
        id="two_bits_one_byte",
        interpreter="other.two_bits_one_byte",
    ),
    "2dFish": Language(
        "2dFish",
        _generate.two_d_fish,
        "other.two_d_fish",
        id="two_d_fish",
    ),
    "6-5": Language(
        "6-5",
        _generate.six_five,
        "tape_based.six_five",
        id="six_five",
    ),
    "%^2^-1": Language(
        "%^2^-1",
        _generate.pct_squared_minus_one,
        "register_based.pct_squared_minus_one",
        id="pct_squared_minus_one",
    ),
    "Albabet": Language(
        "Albabet",
        _generate.albabet,
        "other.albabet",
        id="albabet",
    ),
    "ASCII art": Language(
        "ASCII art",
        _generate.ascii_art,
        "tape_based.ascii_art",
        id="ascii_art",
    ),
    "ArrowQueue": Language(
        "ArrowQueue",
        id="arrowqueue",
        interpreter="other.arrowqueue",
        split=True,
    ),
    "Back": Language(
        "Back",
        id="back",
        interpreter="tape_based.back",
        split=True,
    ),
    "BF-PDA": Language(
        "BF-PDA",
        id="bf_pda",
        interpreter="tape_based.bf_pda",
    ),
    "Basicfuck": Language(
        "Basicfuck",
        _generate.basicfuck,
        "tape_based.basicfuck",
        id="basicfuck",
    ),
    "Between": Language(
        "Between",
        _generate.between,
        "other.between",
        id="between",
        split=True,
    ),
    "brainfuck": Language(
        "brainfuck",
        _generate.brainfuck,
        "tape_based.brainfuck",
        id="brainfuck",
    ),
    "BFStack": Language(
        "BFStack",
        _generate.bfstack,
        "stack_based.bfstack",
        id="bfstack",
    ),
    "BIO": Language(
        "BIO",
        _generate.bio,
        "register_based.bio",
        id="bio",
    ),
    "bit~": Language(
        "bit~",
        _generate.bit_tilde,
        "other.bit_tilde",
        id="bit_tilde",
    ),
    "Bitdeque": Language(
        "Bitdeque",
        id="bitdeque",
        interpreter="other.bitdeque",
    ),
    "BrainIf": Language(
        "BrainIf",
        _generate.brainif,
        "tape_based.brainif",
        id="brainif",
        split=True,
    ),
    "Brainpocalypse": Language(
        "Brainpocalypse",
        id="brainpocalypse",
        interpreter="tape_based.brainpocalypse",
    ),
    "Circlefuck": Language(
        "Circlefuck",
        _generate.circlefuck,
        "tape_based.circlefuck",
        id="circlefuck",
    ),
    "Clockwise": Language(
        "Clockwise",
        _generate.clockwise,
        "other.clockwise",
        id="clockwise",
        split=True,
    ),
    "Collatz Multiverse": Language(
        "Collatz Multiverse",
        _generate.collatz_multiverse,
        "register_based.collatz_multiverse",
        id="collatz_multiverse",
    ),
    "Decleq": Language(
        "Decleq",
        _generate.decleq,
        "register_based.decleq",
        id="decleq",
    ),
    "Container": Language(
        "Container",
        _generate.container,
        "other.container",
        id="container",
        split=True,
    ),
    "Dig": Language(
        "Dig",
        _generate.dig,
        "register_based.dig",
        id="dig",
        split=True,
    ),
    "Dimensional": Language(
        "Dimensional",
        _generate.dimensional,
        "tape_based.dimensional",
        id="dimensional",
    ),
    "Dotlang": Language(
        "Dotlang",
        _generate.dotlang,
        "register_based.dotlang",
        id="dotlang",
        split=True,
    ),
    "DSDLAI": Language(
        "DSDLAI",
        id="dsdlai",
        interpreter="register_based.dsdlai",
        split=True,
    ),
    "Eval": Language(
        "Eval",
        _generate.eval,
        "stack_based.eval",
        id="eval",
    ),
    "EXCON": Language(
        "EXCON",
        _generate.excon,
        "tape_based.excon",
        id="excon",
    ),
    "Factor": Language(
        "Factor",
        _generate.factor,
        "tape_based.factor",
        id="factor",
    ),
    "Forþ": Language(
        "Forþ",
        _generate.forth,
        "stack_based.forth",
        id="forth",
    ),
    "Forbin": Language(
        "Forbin",
        _generate.forbin,
        "other.forbin",
        id="forbin",
    ),
    "Grapheme": Language(
        "Grapheme",
        id="grapheme",
        interpreter="other.grapheme",
    ),
    "Home Row": Language(
        "Home Row",
        _generate.home_row,
        "other.home_row",
        id="home_row",
    ),
    "huf": Language(
        "huf",
        _generate.huf,
        "register_based.huf",
        id="huf",
    ),
    "Kak": Language(
        "Kak",
        id="kak",
        interpreter="tape_based.kak",
    ),
    "Keys": Language(
        "Keys",
        id="keys",
        interpreter="other.keys",
        split=True,
    ),
    "LaserFuck": Language(
        "LaserFuck",
        _generate.laserfuck,
        "other.laserfuck",
        id="laserfuck",
        split=True,
    ),
    "Lightlang": Language(
        "Lightlang",
        id="lightlang",
        interpreter="register_based.lightlang",
    ),
    "SLOW ACV MAMMALIAN": Language(
        "SLOW ACV MAMMALIAN",
        _generate.mammalian,
        "tape_based.mammalian",
        id="mammalian",
    ),
    "Minifuck": Language(
        "Minifuck",
        _generate.minifuck,
        "tape_based.minifuck",
        id="minifuck",
    ),
    "Minsky Swap": Language(
        "Minsky Swap",
        id="minsky_swap",
        interpreter="register_based.minsky_swap",
    ),
    "Modulous": Language(
        "Modulous",
        _generate.modulous,
        "stack_based.modulous",
        id="modulous",
    ),
    "Movesum": Language(
        "Movesum",
        id="movesum",
        interpreter="register_based.movesum",
        split=True,
    ),
    "Nevermind": Language(
        "Nevermind",
        _generate.nevermind,
        "other.nevermind",
        id="nevermind",
        split=True,
    ),
    "NoComment": Language(
        "NoComment",
        _generate.nocomment,
        "tape_based.nocomment",
        id="nocomment",
    ),
    "Number Seventy-Four": Language(
        "Number Seventy-Four",
        id="seventy_four",
        interpreter="other.seventy_four",
    ),
    "Painfuck": Language(
        "Painfuck",
        _generate.painfuck,
        "tape_based.painfuck",
        id="painfuck",
    ),
    "Polynomial": Language(
        "Polynomial",
        _generate.polynomial,
        "register_based.polynomial",
        id="polynomial",
    ),
    "Qoibl": Language(
        "Qoibl",
        _generate.qoibl,
        "register_based.qoibl",
        id="qoibl",
        split=True,
    ),
    "RAM0": Language(
        "RAM0",
        id="ram0",
        interpreter="register_based.ram0",
    ),
    "ROTfuck": Language(
        "ROTfuck",
        _generate.rotfuck,
        "tape_based.rotfuck",
        id="rotfuck",
    ),
    "S*bleq": Language(
        "S*bleq",
        _generate.sbleq,
        "tape_based.sbleq",
        id="sbleq",
    ),
    "3D Brainfuck": Language(
        "3D Brainfuck",
        _generate.three_d_bf,
        "tape_based.three_d_bf",
        id="three_d_bf",
    ),
    "Sophie": Language(
        "Sophie",
        _generate.sophie,
        "register_based.sophie",
        id="sophie",
    ),
    "Suffolk": Language(
        "Suffolk",
        _generate.suffolk,
        "tape_based.suffolk",
        id="suffolk",
        kwargs=_kw(limit=1),
    ),
    "Stun Step": Language(
        "Stun Step",
        id="stun_step",
        interpreter="tape_based.stun_step",
    ),
    "The Temporary Stack": Language(
        "The Temporary Stack",
        _generate.temporary,
        "stack_based.temporary",
        id="temporary",
    ),
    "Trash": Language(
        "Trash",
        id="trash",
        interpreter="other.trash",
    ),
    "3x": Language(
        "3x",
        _generate.three_x,
        "other.three_x",
        id="three_x",
    ),
    "Taglate": Language(
        "Taglate",
        _generate.taglate,
        "other.taglate",
        id="taglate",
        split=True,
    ),
    "Unsquare": Language(
        "Unsquare",
        _generate.unsquare,
        "stack_based.unsquare",
        id="unsquare",
    ),
    "WII2D": Language(
        "WII2D",
        _generate.wii2d,
        "register_based.wii2d",
        id="wii2d",
        split=True,
    ),
    "ZTOALC L": Language(
        "ZTOALC L",
        _generate.ztoalc,
        "other.ztoalc",
        id="ztoalc",
        split=True,
    ),
}


# Display name -> generator function, for languages that have one.
GENERATORS: dict[str, Callable[[str], str]] = {
    name: lang.generator for name, lang in LANGUAGES.items() if lang.generator
}

# Generator function name -> Language, so tests can look a generator up by
# the name of its function (e.g. ``six_five`` for "6-5").
BY_FUNCTION: dict[str, Language] = {
    lang.generator.__name__: lang
    for lang in LANGUAGES.values()
    if lang.generator is not None
}

# Display name -> (interpreter module, split lines, run() keyword arguments).
RUNNERS: dict[str, tuple[str, bool, dict[str, int]]] = {
    name: (lang.interpreter, lang.split, dict(lang.kwargs))
    for name, lang in LANGUAGES.items()
    if lang.interpreter
}
