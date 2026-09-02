"""Single source of truth for the languages the package supports.

Each :class:`Language` describes a language's generators (if any), its
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

from esolangs.tools import boolean as _boolean
from esolangs.tools import text as _generate

# Display names whose canonical id cannot be produced by the slug rules
# (a name whose meaning is lost by stripping its symbols, like ``%^2^-1``).
_CANONICAL_OVERRIDES = {
    "%^2^-1": "pct_squared_minus_one",
    # The parentheses are part of the name -- they mark the optional slots
    # of the CV(N)(C) syllable -- so the slug rule turns them into
    # separators and yields "cv_n_c".  The language is written and
    # pronounced as one word, so the underscores are noise.
    "CV(N)(C)": "cvnc",
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


# A text generator: ``generator(text)`` returns a program printing it.
# Most take only the text; the few that lay their program out in two
# dimensions (Clockwise, which walks a rectangle's perimeter) also accept a
# ``width`` bounding the columns, since a shape cannot be reflowed after the
# fact the way a single long line can.  ``...`` keeps both arities callable
# with the text alone, which is how every width-less caller invokes them.
Generator = Callable[..., str]


@dataclass(frozen=True)
class Language:
    """Metadata for one language.

    ``id`` is the language's canonical internal identifier: the slug
    :func:`canonical_id` produces from the display name, used for the
    interpreter module, the generator function, and the test file, so every
    internal reference to a language uses the same token.

    ``text`` and ``boolean`` are the language's two generators, either of
    which may be None: ``text`` produces a program that prints a text, and
    ``boolean`` one computing a truth table.  Both
    :data:`GENERATORS` and :data:`~esolangs.tools.boolean.BOOLEAN` are
    derived from them, so registering a generator here is the whole of
    adding one, with no second list to keep in step.

    ``interpreter`` is the dotted module under
    ``esolangs.interpreters`` that runs programs (None if the executable
    lives elsewhere, e.g. in extra/).  ``split`` passes the program split
    into lines to the interpreter, and ``kwargs`` holds any extra run()
    keyword arguments as (name, value) pairs.
    """

    name: str
    text: Generator | None = None
    interpreter: str | None = None
    split: bool = False
    kwargs: tuple[tuple[str, int], ...] = ()
    id: str = ""
    boolean: Callable[[str], str] | None = None


LANGUAGES: dict[str, Language] = {
    "AddSubJump": Language(
        "AddSubJump",
        _generate.addsubjump,
        "register_based.addsubjump",
        boolean=_boolean.addsubjump,
        id="addsubjump",
    ),
    "A Painter Ant": Language(
        "A Painter Ant",
        boolean=_boolean.a_painter_ant,
        id="a_painter_ant",
        interpreter="grid_based.a_painter_ant",
    ),
    "Algebraic Programming Language": Language(
        "Algebraic Programming Language",
        boolean=_boolean.algebraic_programming_language,
        id="algebraic_programming_language",
        interpreter="other.algebraic_programming_language",
    ),
    "123": Language(
        "123",
        _generate.one_two_three,
        "tape_based.one_two_three",
        boolean=_boolean.one_two_three,
        id="one_two_three",
    ),
    "6-5": Language(
        "6-5",
        _generate.six_five,
        "tape_based.six_five",
        boolean=_boolean.six_five,
        id="six_five",
    ),
    "%^2^-1": Language(
        "%^2^-1",
        _generate.pct_squared_minus_one,
        "register_based.pct_squared_minus_one",
        boolean=_boolean.pct_squared_minus_one,
        id="pct_squared_minus_one",
    ),
    "ArrowQueue": Language(
        "ArrowQueue",
        boolean=_boolean.arrowqueue,
        id="arrowqueue",
        interpreter="grid_based.arrowqueue",
        split=True,
    ),
    "Back": Language(
        "Back",
        boolean=_boolean.back,
        id="back",
        interpreter="tape_based.back",
        split=True,
    ),
    "BF-PDA": Language(
        "BF-PDA",
        boolean=_boolean.bfpda,
        id="bf_pda",
        interpreter="stack_based.bf_pda",
    ),
    "Basicfuck": Language(
        "Basicfuck",
        _generate.basicfuck,
        "tape_based.basicfuck",
        boolean=_boolean.basicfuck,
        id="basicfuck",
    ),
    "Between": Language(
        "Between",
        _generate.between,
        "register_based.between",
        boolean=_boolean.between,
        id="between",
        split=True,
    ),
    "brainfuck": Language(
        "brainfuck",
        _generate.brainfuck,
        "tape_based.brainfuck",
        boolean=_boolean.brainfuck,
        id="brainfuck",
    ),
    "BFStack": Language(
        "BFStack",
        _generate.bfstack,
        "stack_based.bfstack",
        boolean=_boolean.bfstack,
        id="bfstack",
    ),
    "BIO": Language(
        "BIO",
        _generate.bio,
        "register_based.bio",
        boolean=_boolean.bio,
        id="bio",
    ),
    "bit~": Language(
        "bit~",
        _generate.bit_tilde,
        "tape_based.bit_tilde",
        boolean=_boolean.bit_tilde,
        id="bit_tilde",
    ),
    "Bitdeque": Language(
        "Bitdeque",
        boolean=_boolean.bitdeque,
        id="bitdeque",
        interpreter="queue_based.bitdeque",
    ),
    "BrainIf": Language(
        "BrainIf",
        _generate.brainif,
        "tape_based.brainif",
        boolean=_boolean.brainif,
        id="brainif",
        split=True,
    ),
    "Circlefuck": Language(
        "Circlefuck",
        _generate.circlefuck,
        "tape_based.circlefuck",
        boolean=_boolean.circlefuck,
        id="circlefuck",
    ),
    "Circuit Diagram": Language(
        "Circuit Diagram",
        boolean=_boolean.circuit_diagram,
        id="circuit_diagram",
        interpreter="grid_based.circuit_diagram",
        split=True,
    ),
    "Clockwise": Language(
        "Clockwise",
        _generate.clockwise,
        "grid_based.clockwise",
        boolean=_boolean.clockwise,
        id="clockwise",
        split=True,
    ),
    "COD": Language(
        "COD",
        boolean=_boolean.cod,
        id="cod",
        interpreter="grid_based.cod",
    ),
    "Collatz Multiverse": Language(
        "Collatz Multiverse",
        _generate.collatz_multiverse,
        "register_based.collatz_multiverse",
        boolean=_boolean.collatz_multiverse,
        id="collatz_multiverse",
    ),
    "CV(N)(C)": Language(
        "CV(N)(C)",
        _generate.cvnc,
        "other.cvnc",
        boolean=_boolean.cvnc,
        id="cvnc",
    ),
    "Decleq": Language(
        "Decleq",
        _generate.decleq,
        "register_based.decleq",
        boolean=_boolean.decleq,
        id="decleq",
    ),
    "Container": Language(
        "Container",
        _generate.container,
        "other.container",
        boolean=_boolean.container,
        id="container",
        split=True,
    ),
    "Dig": Language(
        "Dig",
        _generate.dig,
        "grid_based.dig",
        boolean=_boolean.dig,
        id="dig",
        split=True,
    ),
    "Dimensional": Language(
        "Dimensional",
        _generate.dimensional,
        "tape_based.dimensional",
        boolean=_boolean.dimensional,
        id="dimensional",
    ),
    "Eval": Language(
        "Eval",
        _generate.eval,
        "stack_based.eval",
        boolean=_boolean.eval,
        id="eval",
    ),
    "Factor": Language(
        "Factor",
        _generate.factor,
        "tape_based.factor",
        boolean=_boolean.factor,
        id="factor",
    ),
    "Fargo": Language(
        "Fargo",
        boolean=_boolean.fargo,
        id="fargo",
        interpreter="other.fargo",
    ),
    "Flowchart": Language(
        "Flowchart",
        boolean=_boolean.flowchart,
        id="flowchart",
        interpreter="grid_based.flowchart",
        split=True,
    ),
    "Forþ": Language(
        "Forþ",
        _generate.forth,
        "stack_based.forth",
        boolean=_boolean.forth,
        id="forth",
    ),
    "Forbin": Language(
        "Forbin",
        _generate.forbin,
        "other.forbin",
        boolean=_boolean.forbin_boolean,
        id="forbin",
    ),
    "Grapheme": Language(
        "Grapheme",
        boolean=_boolean.grapheme,
        id="grapheme",
        interpreter="stack_based.grapheme",
    ),
    "Home Row": Language(
        "Home Row",
        _generate.home_row,
        "tape_based.home_row",
        boolean=_boolean.home_row,
        id="home_row",
    ),
    "Inject": Language(
        "Inject",
        boolean=_boolean.inject,
        id="inject",
        interpreter="other.inject",
    ),
    "Jaune": Language(
        "Jaune",
        boolean=_boolean.jaune,
        id="jaune",
        interpreter="tape_based.jaune",
    ),
    "Lamfunc": Language(
        "Lamfunc",
        boolean=_boolean.lamfunc,
        id="lamfunc",
        interpreter="other.lamfunc",
    ),
    "LaserFuck": Language(
        "LaserFuck",
        _generate.laserfuck,
        "grid_based.laserfuck",
        boolean=_boolean.laserfuck,
        id="laserfuck",
        split=True,
    ),
    "SLOW ACV MAMMALIAN": Language(
        "SLOW ACV MAMMALIAN",
        _generate.slow_acv_mammalian,
        "tape_based.slow_acv_mammalian",
        id="slow_acv_mammalian",
        boolean=_boolean.slow_acv_mammalian_boolean,
    ),
    "Minifuck": Language(
        "Minifuck",
        _generate.minifuck,
        "tape_based.minifuck",
        boolean=_boolean.minifuck,
        id="minifuck",
    ),
    "Minsky Swap": Language(
        "Minsky Swap",
        boolean=_boolean.minsky_swap,
        id="minsky_swap",
        interpreter="register_based.minsky_swap",
    ),
    "Modulous": Language(
        "Modulous",
        _generate.modulous,
        "stack_based.modulous",
        boolean=_boolean.modulous,
        id="modulous",
    ),
    "MyScript": Language(
        "MyScript",
        _generate.myscript,
        "register_based.myscript",
        boolean=_boolean.myscript,
        id="myscript",
    ),
    "Nevermind": Language(
        "Nevermind",
        _generate.nevermind,
        "register_based.nevermind",
        boolean=_boolean.nevermind,
        id="nevermind",
        split=True,
    ),
    "NoComment": Language(
        "NoComment",
        _generate.nocomment,
        "tape_based.nocomment",
        boolean=_boolean.nocomment,
        id="nocomment",
    ),
    "Painfuck": Language(
        "Painfuck",
        _generate.painfuck,
        "tape_based.painfuck",
        boolean=_boolean.painfuck,
        id="painfuck",
    ),
    "Polynomial": Language(
        "Polynomial",
        _generate.polynomial,
        "register_based.polynomial",
        boolean=_boolean.polynomial,
        id="polynomial",
    ),
    "Point Break": Language(
        "Point Break",
        boolean=_boolean.point_break,
        id="point_break",
        interpreter="register_based.point_break",
        split=True,
    ),
    "Qoibl": Language(
        "Qoibl",
        _generate.qoibl,
        "register_based.qoibl",
        boolean=_boolean.qoibl,
        id="qoibl",
        split=True,
    ),
    "RAM0": Language(
        "RAM0",
        boolean=_boolean.ram0,
        id="ram0",
        interpreter="register_based.ram0",
    ),
    "ROTfuck": Language(
        "ROTfuck",
        _generate.rotfuck,
        "tape_based.rotfuck",
        boolean=_boolean.rotfuck,
        id="rotfuck",
    ),
    "S*bleq": Language(
        "S*bleq",
        _generate.sbleq,
        "tape_based.sbleq",
        boolean=_boolean.sbleq,
        id="sbleq",
    ),
    "3D Brainfuck": Language(
        "3D Brainfuck",
        _generate.three_d_brainfuck,
        "tape_based.three_d_brainfuck",
        boolean=_boolean.three_d_brainfuck,
        id="three_d_brainfuck",
    ),
    "Sophie": Language(
        "Sophie",
        _generate.sophie,
        "register_based.sophie",
        boolean=_boolean.sophie,
        id="sophie",
    ),
    "Streetcode": Language(
        "Streetcode",
        _generate.streetcode,
        "grid_based.streetcode",
        boolean=_boolean.streetcode,
        id="streetcode",
        split=True,
    ),
    "Suffolk": Language(
        "Suffolk",
        _generate.suffolk,
        "tape_based.suffolk",
        boolean=_boolean.suffolk,
        id="suffolk",
    ),
    "Suptiftam": Language(
        "Suptiftam",
        _generate.suptiftam,
        "other.suptiftam",
        boolean=_boolean.suptiftam,
        id="suptiftam",
    ),
    "3x": Language(
        "3x",
        _generate.three_x,
        "stack_based.three_x",
        boolean=_boolean.three_x,
        id="three_x",
    ),
    "Taglate": Language(
        "Taglate",
        _generate.taglate,
        "queue_based.taglate",
        boolean=_boolean.taglate,
        id="taglate",
        split=True,
    ),
    "Unsquare": Language(
        "Unsquare",
        _generate.unsquare,
        "stack_based.unsquare",
        boolean=_boolean.unsquare,
        id="unsquare",
    ),
    "WII2D": Language(
        "WII2D",
        _generate.wii2d,
        "grid_based.wii2d",
        boolean=_boolean.wii2d,
        id="wii2d",
        split=True,
    ),
    "ZTOALC L": Language(
        "ZTOALC L",
        _generate.ztoalc_l,
        "other.ztoalc_l",
        boolean=_boolean.ztoalc_l_boolean,
        id="ztoalc_l",
        split=True,
    ),
}


# Display name -> generator function, for languages that have one.
GENERATORS: dict[str, Generator] = {
    name: lang.text for name, lang in LANGUAGES.items() if lang.text
}

# Generator function name -> Language, so tests can look a generator up by
# the name of its function (e.g. ``six_five`` for "6-5").
BY_FUNCTION: dict[str, Language] = {
    lang.text.__name__: lang for lang in LANGUAGES.values() if lang.text is not None
}

# The same, for the *boolean* generators.  ``BY_FUNCTION`` is keyed by the
# text generator's name, so a language with a boolean generator and no text
# one is absent from it entirely -- and a sweep written over ``BY_FUNCTION``
# silently skips those languages rather than failing.  That is how Jaune's
# table-dependent input count survived: it is a boolean-only language, so
# the read-count contract test never saw it.  Sixteen boolean generators
# were invisible this way (Bitdeque, RAM0, Lamfunc, Flowchart, Jaune and
# the rest of the boolean-only set).
BY_BOOLEAN: dict[str, Language] = {
    lang.boolean.__name__: lang
    for lang in LANGUAGES.values()
    if lang.boolean is not None
}

# Display name -> (interpreter module, split lines, run() keyword arguments).
RUNNERS: dict[str, tuple[str, bool, dict[str, int]]] = {
    name: (lang.interpreter, lang.split, dict(lang.kwargs))
    for name, lang in LANGUAGES.items()
    if lang.interpreter
}
