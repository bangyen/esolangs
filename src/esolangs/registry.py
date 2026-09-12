r"""Single source of truth for the languages the package supports."""

import difflib
import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from urllib.parse import quote

from esolangs.exceptions import UnknownLanguageError
from esolangs.tools import boolean as _boolean

# Display names whose canonical.
# (a name whose meaning is lost.
_CANONICAL_OVERRIDES = {
    "%^2^-1": "pct_squared_minus_one",
    # The parentheses are part of.
    # of the CV(N)(C) syllable --.
    # separators and yields.
    # pronounced as one word, so.
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


# : How close a miss has to be.
# :.
# : 0.6 offered ``Sophie`` for.
# : a wrong guess sends the.
# : Measured rather than picked.
# : names, 0.6 and 0.65 both.
# : suggests nothing for any of.
# : ``hello``, ``python``,.
# : costing real rescues.
# : measurement, re-run rather.
# : that trade and fails if.
# :.
# : Shared with the CLI's.
# : own copy of the number.
SUGGESTION_CUTOFF = 0.65


def canonical_id(name: str) -> str:
    r"""Return the canonical internal identifier for a language's display."""
    # Matched case-insensitively:.
    # so an exact-key lookup made.
    # could not match on case --.
    # and became ``cv_n_c``, which.
    # name (``BRAINFUCK``,.
    # Stripped before anything else.
    # non-alphanumerics and strip.
    # tolerated a stray surrounding.
    # exact one, and the two names.
    # exact two that did not.
    # through to ``cv_n_c``,.
    # CV(N)(C)?" -- an invisible.
    name = name.strip()
    folded = {key.casefold(): value for key, value in _CANONICAL_OVERRIDES.items()}
    if name.casefold() in folded:
        return folded[name.casefold()]
    # Lowercased *before* the.
    # lowercase characters, so.
    # through to the punctuation.
    # display name whose upper-case.
    s = name.lower().replace("~", "_tilde").replace("þ", "th").replace("*", "")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    if s and s[0].isdigit():
        s = "".join("_" + _DIGIT_WORDS[c] + "_" if c.isdigit() else c for c in s)
        s = re.sub(r"_+", "_", s).strip("_")
    return s


# A generator:.
# Most take only the table; the.
# dimensions (LaserFuck, which.
# ``width`` bounding the.
# fact the way a single long.
# with the table alone, which.
Generator = Callable[..., str]


@dataclass(frozen=True)
class Language:
    r"""Metadata for one language."""

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


# Generator function name ->.
# the name of its function (e.g.
# .
# This used to have a twin.
# written over that twin.
# than failing.
# sixteen boolean generators.
# Keying only by ``boolean``.
BY_BOOLEAN: dict[str, Language] = {
    lang.boolean.__name__: lang
    for lang in LANGUAGES.values()
    if lang.boolean is not None
}

# Display name -> (interpreter.
RUNNERS: dict[str, tuple[str, bool]] = {
    name: (lang.interpreter, lang.split)
    for name, lang in LANGUAGES.items()
    if lang.interpreter
}


@cache
def example_stems() -> dict[str, str]:
    r"""Return canonical id -> the ``examples/`` filename stem, per."""
    from esolangs.tools.boolean import examples as _examples

    return {
        canonical_id(stem.replace("-", " ")): stem
        for stem in set(_examples.BOOLEAN_EXAMPLES) | set(_examples.HAND_WRITTEN)
    }


@cache
def _fills() -> dict[str, Callable[[str, list[int]], str]]:
    r"""Return canonical id -> the substitution that instantiates a."""
    from esolangs.tools.boolean import examples as _examples

    return {
        canonical_id(stem.replace("-", " ")): example.fill
        for stem, example in _examples.BOOLEAN_EXAMPLES.items()
        if example.fill is not None
    }


def parameterized_ids() -> frozenset[str]:
    r"""Return the canonical ids whose boolean generator emits a template."""
    return frozenset(_fills())


# Canonical id -> display name,.
_BY_ID: dict[str, str] = {lang.id: name for name, lang in LANGUAGES.items()}


# : Characters a wiki slug may.
# :.
# : RFC 3986 lets a path.
# : so parentheses, ``*``,.
# : better link than.
# : here is the point: ``%`` is.
# : neither set, so ``%^2^-1``.
# :.
# : ``%^2`` is not a.
# : raw bytes is served by a.
_WIKI_SAFE = "_-.~()*!'+,;=:@&$"


def wiki_url(name: str) -> str:
    r"""Return the esolangs.org page for a language's display name."""
    slug = quote(name.replace(" ", "_"), safe=_WIKI_SAFE)
    return f"https://esolangs.org/wiki/{slug}"


def resolve(name: str) -> str:
    r"""Return the registered display name matching ``name``."""
    if not isinstance(name, str):
        # Checked before.
        # answer a ``None`` language.
        # attribute 'replace'`` -- the.
        # that escaped as an internal.
        raise UnknownLanguageError(
            f"expected a language name, got {type(name).__name__}"
        )
    if name in LANGUAGES:
        return name
    match = _BY_ID.get(canonical_id(name))
    if match is not None:
        return match
    close = difflib.get_close_matches(
        canonical_id(name), _BY_ID, n=2, cutoff=SUGGESTION_CUTOFF
    )
    raise UnknownLanguageError(name, tuple(_BY_ID[c] for c in close))
