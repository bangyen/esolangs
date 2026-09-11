"""Single source of truth for the languages the package supports.

Each :class:`Language` describes a language's generators (if any), its
interpreter (if any), and how a program is handed to that interpreter. The
public API, the tools, and the test suite all derive from this table, so
adding a language is a one-place change.

:func:`canonical_id` turns a language's display (wiki) name into its
canonical internal identifier, so the two are derived, not maintained in
parallel.
"""

import difflib
import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache

from esolangs.exceptions import UnknownLanguageError
from esolangs.tools import boolean as _boolean

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


# A generator: ``generator(truth_table)`` returns a program computing it.
# Most take only the table; the few that lay their program out in two
# dimensions (LaserFuck, which folds its beam's track) also accept a
# ``width`` bounding the columns, since a shape cannot be reflowed after the
# fact the way a single long line can.  ``...`` keeps both arities callable
# with the table alone, which is how every width-less caller invokes them.
Generator = Callable[..., str]


@dataclass(frozen=True)
class Language:
    """Metadata for one language.

    ``id`` is the language's canonical internal identifier: the slug
    :func:`canonical_id` produces from the display name, used for the
    interpreter module, the generator function, and the test file, so every
    internal reference to a language uses the same token.

    ``boolean`` is the language's generator, which may be None: it produces
    a program computing a truth table.
    :data:`~esolangs.tools.boolean.BOOLEAN` is derived from it, so
    registering a generator here is the whole of adding one, with no second
    list to keep in step.

    ``interpreter`` is the dotted module under
    ``esolangs.interpreters`` that runs programs (None if the executable
    lives elsewhere, e.g. in extra/).  ``split`` passes the program split
    into lines to the interpreter.

    There is deliberately no field for extra ``run()`` arguments.  One
    existed -- ``kwargs``, carried through :data:`RUNNERS` and unpacked by
    ``esolangs.run`` -- and no language ever set it, so every call was
    ``run_fn(program, io)`` with an empty dict threaded through three
    functions to get there.  The eleven interpreters that take a further
    argument all default it, and the callers that pass one are the tests
    and the ``__main__`` blocks, which call the interpreter's ``run``
    directly and never come through here.  ``esolangs.tools.boolean.
    examples`` keeps its own ``kwargs`` because that one is used.

    """

    name: str
    interpreter: str | None = None
    split: bool = False
    id: str = ""
    boolean: Generator | None = None


LANGUAGES: dict[str, Language] = {
    "AddSubJump": Language(
        "AddSubJump",
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
    "Alight": Language(
        "Alight",
        "grid_based.alight",
        boolean=_boolean.alight,
        id=canonical_id("Alight"),
        split=True,
    ),
    "Algebraic Programming Language": Language(
        "Algebraic Programming Language",
        boolean=_boolean.algebraic_programming_language,
        id="algebraic_programming_language",
        interpreter="other.algebraic_programming_language",
    ),
    "123": Language(
        "123",
        "tape_based.one_two_three",
        boolean=_boolean.one_two_three,
        id="one_two_three",
    ),
    "6-5": Language(
        "6-5",
        "tape_based.six_five",
        boolean=_boolean.six_five,
        id="six_five",
    ),
    "%^2^-1": Language(
        "%^2^-1",
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
        "tape_based.basicfuck",
        boolean=_boolean.basicfuck,
        id="basicfuck",
    ),
    "Between": Language(
        "Between",
        "register_based.between",
        boolean=_boolean.between,
        id="between",
        split=True,
    ),
    "brainfuck": Language(
        "brainfuck",
        "tape_based.brainfuck",
        boolean=_boolean.brainfuck,
        id="brainfuck",
    ),
    "BFStack": Language(
        "BFStack",
        "stack_based.bfstack",
        boolean=_boolean.bfstack,
        id="bfstack",
    ),
    "BIO": Language(
        "BIO",
        "register_based.bio",
        boolean=_boolean.bio,
        id="bio",
    ),
    "bit~": Language(
        "bit~",
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
        "tape_based.brainif",
        boolean=_boolean.brainif,
        id="brainif",
        split=True,
    ),
    "Circlefuck": Language(
        "Circlefuck",
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
        "register_based.collatz_multiverse",
        boolean=_boolean.collatz_multiverse,
        id="collatz_multiverse",
    ),
    "CV(N)(C)": Language(
        "CV(N)(C)",
        "other.cvnc",
        boolean=_boolean.cvnc,
        id="cvnc",
    ),
    "Decleq": Language(
        "Decleq",
        "register_based.decleq",
        boolean=_boolean.decleq,
        id="decleq",
    ),
    "Container": Language(
        "Container",
        "other.container",
        boolean=_boolean.container,
        id="container",
        split=True,
    ),
    "Dig": Language(
        "Dig",
        "grid_based.dig",
        boolean=_boolean.dig,
        id="dig",
        split=True,
    ),
    "Dimensional": Language(
        "Dimensional",
        "tape_based.dimensional",
        boolean=_boolean.dimensional,
        id="dimensional",
    ),
    "DINAC": Language(
        "DINAC",
        "other.dinac",
        boolean=_boolean.dinac,
        id="dinac",
    ),
    "Eval": Language(
        "Eval",
        "stack_based.eval",
        boolean=_boolean.eval,
        id="eval",
    ),
    "Factor": Language(
        "Factor",
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
        "stack_based.forth",
        boolean=_boolean.forth,
        id="forth",
    ),
    "Forbin": Language(
        "Forbin",
        "other.forbin",
        boolean=_boolean.forbin,
        id="forbin",
    ),
    "function x(y)": Language(
        "function x(y)",
        "other.function_x_y",
        boolean=_boolean.function_x_y,
        id="function_x_y",
    ),
    "Grapheme": Language(
        "Grapheme",
        boolean=_boolean.grapheme,
        id="grapheme",
        interpreter="stack_based.grapheme",
    ),
    "Home Row": Language(
        "Home Row",
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
    "Interprogck8": Language(
        "Interprogck8",
        "register_based.interprogck8",
        boolean=_boolean.interprogck8,
        id=canonical_id("Interprogck8"),
        split=True,
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
        "grid_based.laserfuck",
        boolean=_boolean.laserfuck,
        id="laserfuck",
        split=True,
    ),
    "SLOW ACV MAMMALIAN": Language(
        "SLOW ACV MAMMALIAN",
        "tape_based.slow_acv_mammalian",
        id="slow_acv_mammalian",
        boolean=_boolean.slow_acv_mammalian,
    ),
    "Minifuck": Language(
        "Minifuck",
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
        "stack_based.modulous",
        boolean=_boolean.modulous,
        id="modulous",
    ),
    "MyScript": Language(
        "MyScript",
        "register_based.myscript",
        boolean=_boolean.myscript,
        id="myscript",
    ),
    "Nevermind": Language(
        "Nevermind",
        "register_based.nevermind",
        boolean=_boolean.nevermind,
        id="nevermind",
        split=True,
    ),
    "NoComment": Language(
        "NoComment",
        "tape_based.nocomment",
        boolean=_boolean.nocomment,
        id="nocomment",
    ),
    "Packlang": Language(
        "Packlang",
        "other.packlang",
        boolean=_boolean.packlang,
        id="packlang",
    ),
    "Painfuck": Language(
        "Painfuck",
        "tape_based.painfuck",
        boolean=_boolean.painfuck,
        id="painfuck",
    ),
    "Polynomial": Language(
        "Polynomial",
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
        "tape_based.rotfuck",
        boolean=_boolean.rotfuck,
        id="rotfuck",
    ),
    "S*bleq": Language(
        "S*bleq",
        "tape_based.sbleq",
        boolean=_boolean.sbleq,
        id="sbleq",
    ),
    "3D Brainfuck": Language(
        "3D Brainfuck",
        "tape_based.three_d_brainfuck",
        boolean=_boolean.three_d_brainfuck,
        id="three_d_brainfuck",
    ),
    "Sophie": Language(
        "Sophie",
        "register_based.sophie",
        boolean=_boolean.sophie,
        id="sophie",
    ),
    "Streetcode": Language(
        "Streetcode",
        "grid_based.streetcode",
        boolean=_boolean.streetcode,
        id="streetcode",
        split=True,
    ),
    "Super SNUSP": Language(
        "Super SNUSP",
        boolean=_boolean.super_snusp,
        id="super_snusp",
        interpreter="grid_based.super_snusp",
        split=True,
    ),
    "Suffolk": Language(
        "Suffolk",
        "tape_based.suffolk",
        boolean=_boolean.suffolk,
        id="suffolk",
    ),
    "Suptiftam": Language(
        "Suptiftam",
        "other.suptiftam",
        boolean=_boolean.suptiftam,
        id="suptiftam",
    ),
    "3x": Language(
        "3x",
        "stack_based.three_x",
        boolean=_boolean.three_x,
        id="three_x",
    ),
    "Taglate": Language(
        "Taglate",
        "queue_based.taglate",
        boolean=_boolean.taglate,
        id="taglate",
        split=True,
    ),
    "Unsquare": Language(
        "Unsquare",
        "stack_based.unsquare",
        boolean=_boolean.unsquare,
        id="unsquare",
    ),
    "WII2D": Language(
        "WII2D",
        "grid_based.wii2d",
        boolean=_boolean.wii2d,
        id="wii2d",
        split=True,
    ),
    "ZTOALC L": Language(
        "ZTOALC L",
        "other.ztoalc_l",
        boolean=_boolean.ztoalc_l,
        id="ztoalc_l",
        split=True,
    ),
}


# Generator function name -> Language, so tests can look a generator up by
# the name of its function (e.g. ``six_five`` for "6-5").
#
# This used to have a twin keyed by the *text* generator's name, and a sweep
# written over that twin silently skipped every boolean-only language rather
# than failing.  That is how Jaune's table-dependent input count survived:
# sixteen boolean generators were invisible to the read-count contract test.
# Keying only by ``boolean`` leaves nothing to pick the wrong map from.
BY_BOOLEAN: dict[str, Language] = {
    lang.boolean.__name__: lang
    for lang in LANGUAGES.values()
    if lang.boolean is not None
}

# Display name -> (interpreter module, split lines).
RUNNERS: dict[str, tuple[str, bool]] = {
    name: (lang.interpreter, lang.split)
    for name, lang in LANGUAGES.items()
    if lang.interpreter
}


@cache
def example_stems() -> dict[str, str]:
    """Return canonical id -> the ``examples/`` filename stem, per language.

    The stems are dash-separated display names (``a-painter-ant``), while
    every internal reference is the underscored :func:`canonical_id` slug
    (``a_painter_ant``), and a few match neither by hand (``6-5``,
    ``pct-squared-minus-one``).  Deriving the map from the example table the
    same way :meth:`~esolangs.tools.boolean.examples.BooleanExample.build`
    does keeps the two spellings from drifting: a stem with no language, or
    a language with no stem, shows up as a missing key rather than as a
    silently empty example list, which is how 19 of the 69 came to report
    none.

    The import is deferred because ``examples`` imports this module; the
    map is wanted only when someone asks for a description, so paying for
    it then costs nothing at import time.
    """
    from esolangs.tools.boolean import examples as _examples

    return {
        canonical_id(stem.replace("-", " ")): stem
        for stem in set(_examples.BOOLEAN_EXAMPLES) | set(_examples.HAND_WRITTEN)
    }


@cache
def _fills() -> dict[str, Callable[[str, list[int]], str]]:
    """Return canonical id -> the substitution that instantiates a template.

    A *parameterized* generator returns a program with ``{Xi}`` slots rather
    than one that reads its inputs, and the slots are filled with that
    language's own code for setting an input.  Each committed example
    already carries that substitution as its ``fill``, so this is the
    existing recipe exposed rather than a second list to keep in step.

    Membership here is the definition of "parameterized" used everywhere in
    the package, and it is derived rather than written down for a measured
    reason: the same set taken from ``parameterized.__all__`` omits Home
    Row, whose generator emits ``{X0}`` all the same, and the three
    hand-kept lists in the docs each named a different subset.  ``fill`` is
    the only spelling that matches what the generators actually emit -- 17
    languages, checked against a ``{Xi}`` search over all 69.
    """
    from esolangs.tools.boolean import examples as _examples

    return {
        canonical_id(stem.replace("-", " ")): example.fill
        for stem, example in _examples.BOOLEAN_EXAMPLES.items()
        if example.fill is not None
    }


def parameterized_ids() -> frozenset[str]:
    """Return the canonical ids whose boolean generator emits a template."""
    return frozenset(_fills())


# Canonical id -> display name, the index :func:`resolve` matches against.
_BY_ID: dict[str, str] = {lang.id: name for name, lang in LANGUAGES.items()}


def resolve(name: str) -> str:
    """Return the registered display name matching ``name``.

    An exact hit wins.  Otherwise the name is matched by its
    :func:`canonical_id`, which makes the lookup case- and
    punctuation-insensitive: ``Brainfuck``, ``brainfuck`` and ``BRAINFUCK``
    all reach the one registered ``brainfuck``.  That the display names mix
    conventions (``brainfuck``, ``Suffolk``, ``bit~``) is exactly why -- a
    caller cannot guess which one a given language follows, and being told
    "unknown language" for a name that is plainly in ``esolangs list`` is
    the wrong answer to a question of spelling.

    A name matching nothing raises :class:`UnknownLanguageError` naming the
    closest registered spellings.
    """
    if name in LANGUAGES:
        return name
    match = _BY_ID.get(canonical_id(name))
    if match is not None:
        return match
    close = difflib.get_close_matches(canonical_id(name), _BY_ID, n=2, cutoff=0.6)
    raise UnknownLanguageError(name, tuple(_BY_ID[c] for c in close))
