"""Single source of truth for the languages the package supports.

Each :class:`Language` describes a language's generator (if any), its
interpreter (if any), and how a program is handed to that interpreter. The
public API, the tools, and the test suite all derive from this table, so
adding a language is a one-place change.

:func:`canonical_id` turns a language's display (wiki) name into its
canonical internal identifier, so the two are derived, not maintained in
parallel.
"""

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass

from esolangs.tools import text as _generate

# Display names whose canonical id cannot be produced by the slug rules
# (a name whose meaning is lost by stripping its symbols, like ``%^2^-1``).
_CANONICAL_OVERRIDES = {
    "%^2^-1": "pct_squared_minus_one",
}

_DIGIT_WORDS = {
    "0": "zero",
    "1": "one",
    "2": "two",
    "3": "three",
    "4": "four",
    "5": "five",
    "6": "six",
    "7": "seven",
    "8": "eight",
    "9": "nine",
}


def canonical_id(name: str) -> str:
    """Return the canonical internal identifier for a language's display name.

    The id is a valid-Python-identifier slug: lowercase, ASCII, non-ASCII
    letters transliterated (``þ`` -> ``th``), ``~`` spelled out as
    ``tilde``, ``*`` dropped, and digit-leading names expanded to words
    (``6-5`` -> ``six_five``).  A couple of names that no slug can capture
    are pinned in :data:`_CANONICAL_OVERRIDES`.
    """
    if name in _CANONICAL_OVERRIDES:
        return _CANONICAL_OVERRIDES[name]
    s = name.replace("~", "_tilde").replace("þ", "th").replace("*", "")
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    if s and s[0].isdigit():
        s = "".join("_" + _DIGIT_WORDS[c] + "_" if c.isdigit() else c for c in s)
        s = re.sub(r"_+", "_", s).strip("_")
    return s


@dataclass(frozen=True)
class Language:
    """Metadata for one language.

    ``id`` is the language's canonical internal identifier: the slug
    :func:`canonical_id` produces from the display name, used for the
    interpreter module, the generator function, and the test file, so every
    internal reference to a language uses the same token.  ``generator``
    produces a program that prints a text (None if the language has no
    generator).  ``interpreter`` is the dotted module under
    ``esolangs.interpreters`` that runs programs (None if the executable
    lives elsewhere, e.g. in extra/).  ``split`` passes the program split
    into lines to the interpreter, and ``kwargs`` holds any extra run()
    keyword arguments as (name, value) pairs.
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
        _generate.addsubjump,
        "register_based.addsubjump",
        id="addsubjump",
    ),
    "A Painter Ant": Language(
        "A Painter Ant",
        id="a_painter_ant",
        interpreter="grid_based.a_painter_ant",
    ),
    "123": Language(
        "123",
        _generate.one_two_three,
        "tape_based.one_two_three",
        id="one_two_three",
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
    "ArrowQueue": Language(
        "ArrowQueue",
        id="arrowqueue",
        interpreter="grid_based.arrowqueue",
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
        interpreter="stack_based.bf_pda",
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
        "register_based.between",
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
        "tape_based.bit_tilde",
        id="bit_tilde",
    ),
    "Bitdeque": Language(
        "Bitdeque",
        id="bitdeque",
        interpreter="queue_based.bitdeque",
    ),
    "BrainIf": Language(
        "BrainIf",
        _generate.brainif,
        "tape_based.brainif",
        id="brainif",
        split=True,
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
        "grid_based.clockwise",
        id="clockwise",
        split=True,
    ),
    "COD": Language(
        "COD",
        id="cod",
        interpreter="grid_based.cod",
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
        "grid_based.dig",
        id="dig",
        split=True,
    ),
    "Dimensional": Language(
        "Dimensional",
        _generate.dimensional,
        "tape_based.dimensional",
        id="dimensional",
    ),
    "Eval": Language(
        "Eval",
        _generate.eval,
        "stack_based.eval",
        id="eval",
    ),
    "Factor": Language(
        "Factor",
        _generate.factor,
        "tape_based.factor",
        id="factor",
    ),
    "Flowchart": Language(
        "Flowchart",
        id="flowchart",
        interpreter="grid_based.flowchart",
        split=True,
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
        interpreter="stack_based.grapheme",
    ),
    "Home Row": Language(
        "Home Row",
        _generate.home_row,
        "tape_based.home_row",
        id="home_row",
    ),
    "Jaune": Language(
        "Jaune",
        id="jaune",
        interpreter="tape_based.jaune",
    ),
    "Lamfunc": Language(
        "Lamfunc",
        id="lamfunc",
        interpreter="other.lamfunc",
    ),
    "LaserFuck": Language(
        "LaserFuck",
        _generate.laserfuck,
        "grid_based.laserfuck",
        id="laserfuck",
        split=True,
    ),
    "SLOW ACV MAMMALIAN": Language(
        "SLOW ACV MAMMALIAN",
        _generate.slow_acv_mammalian,
        "tape_based.slow_acv_mammalian",
        id="slow_acv_mammalian",
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
    "MyScript": Language(
        "MyScript",
        _generate.myscript,
        "register_based.myscript",
        id="myscript",
    ),
    "Nevermind": Language(
        "Nevermind",
        _generate.nevermind,
        "register_based.nevermind",
        id="nevermind",
        split=True,
    ),
    "NoComment": Language(
        "NoComment",
        _generate.nocomment,
        "tape_based.nocomment",
        id="nocomment",
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
    "Point Break": Language(
        "Point Break",
        id="point_break",
        interpreter="register_based.point_break",
        split=True,
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
        _generate.three_d_brainfuck,
        "tape_based.three_d_brainfuck",
        id="three_d_brainfuck",
    ),
    "Sophie": Language(
        "Sophie",
        _generate.sophie,
        "register_based.sophie",
        id="sophie",
    ),
    "Streetcode": Language(
        "Streetcode",
        id="streetcode",
        interpreter="grid_based.streetcode",
        split=True,
    ),
    "Suffolk": Language(
        "Suffolk",
        _generate.suffolk,
        "tape_based.suffolk",
        id="suffolk",
        kwargs=_kw(limit=1),
    ),
    "Suptiftam": Language(
        "Suptiftam",
        _generate.suptiftam,
        "other.suptiftam",
        id="suptiftam",
    ),
    "3x": Language(
        "3x",
        _generate.three_x,
        "stack_based.three_x",
        id="three_x",
    ),
    "Taglate": Language(
        "Taglate",
        _generate.taglate,
        "queue_based.taglate",
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
        "grid_based.wii2d",
        id="wii2d",
        split=True,
    ),
    "ZTOALC L": Language(
        "ZTOALC L",
        _generate.ztoalc_l,
        "other.ztoalc_l",
        id="ztoalc_l",
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
