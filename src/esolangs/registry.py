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

    ``generator`` produces a program that prints a text (None if the
    language has no generator).  ``interpreter`` is the dotted module under
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


def _kw(**kwargs: int) -> tuple[tuple[str, int], ...]:
    return tuple(kwargs.items())


LANGUAGES: dict[str, Language] = {
    "123": Language("123", _generate._123),  # noqa: SLF001 - "123" is a language name
    "2dFish": Language("2dFish", _generate.two_d_fish),
    "6-5": Language("6-5", _generate.six_five, "tape_based.6-5"),
    "%^2^-1": Language("%^2^-1", _generate.pct_squared_minus_one),
    "ASCII art": Language("ASCII art", _generate.ascii_art, "tape_based.ascii-art"),
    "Back": Language("Back", interpreter="tape_based.back", split=True),
    "Basicfuck": Language("Basicfuck", _generate.basicfuck),
    "BF": Language("BF", _generate.bf, "tape_based.bf"),
    "BFStack": Language("BFStack", _generate.bfstack, "stack_based.bfstack"),
    "BIO": Language("BIO", _generate.bio, "register_based.bio"),
    "bit~": Language("bit~", _generate.bit_tilde),
    "BitDeque": Language("BitDeque", interpreter="other.bitdeque"),
    "BrainIf": Language("BrainIf", _generate.brainif, "tape_based.brainif", split=True),
    "CircleFuck": Language("CircleFuck", _generate.circlefuck, "tape_based.circlefuck"),
    "Clockwise": Language(
        "Clockwise", _generate.clockwise, "other.clockwise", split=True
    ),
    "Container": Language(
        "Container", _generate.container, "other.container", split=True
    ),
    "Dig": Language("Dig", _generate.dig, "register_based.dig", split=True),
    "Dimensional": Language(
        "Dimensional", _generate.dimensional, "tape_based.dimensional"
    ),
    "Dotlang": Language(
        "Dotlang", _generate.dotlang, "register_based.dotlang", split=True
    ),
    "DSDLAI": Language("DSDLAI", interpreter="register_based.dsdlai", split=True),
    "Eval": Language("Eval", _generate.eval, "stack_based.eval"),
    "EXCON": Language("EXCON", _generate.excon, "tape_based.excon"),
    "Forþ": Language("Forþ", _generate.forth),
    "Home Row": Language("Home Row", _generate.home_row),
    "huf": Language("huf", _generate.huf, "register_based.huf"),
    "Keys": Language("Keys", interpreter="other.keys", split=True),
    "LaserFuck": Language("LaserFuck", _generate.laserfuck),
    "Lightlang": Language("Lightlang", interpreter="register_based.lightlang"),
    "MAMMALIAN": Language("MAMMALIAN", _generate.mammalian, "tape_based.mammalian"),
    "Minifuck": Language("Minifuck", _generate.minifuck, "tape_based.minifuck"),
    "Minsky Swap": Language("Minsky Swap", interpreter="register_based.minsky-swap"),
    "Modulous": Language("Modulous", _generate.modulous, "stack_based.modulous"),
    "Movesum": Language("Movesum", interpreter="register_based.movesum", split=True),
    "Nevermind": Language(
        "Nevermind", _generate.nevermind, "other.nevermind", split=True
    ),
    "NoComment": Language("NoComment", _generate.nocomment, "tape_based.nocomment"),
    "Painfuck": Language("Painfuck", _generate.painfuck),
    "Polynomial": Language(
        "Polynomial",
        _generate.polynomial,
        "register_based.polynomial",
    ),
    "Qoibl": Language("Qoibl", _generate.qoibl, "register_based.qoibl", split=True),
    "RAM0": Language("RAM0", interpreter="register_based.RAM0"),
    "S*bleq": Language("S*bleq", interpreter="tape_based.sbleq"),
    "Sophie": Language("Sophie", _generate.sophie, "register_based.sophie"),
    "Suffolk": Language(
        "Suffolk",
        _generate.suffolk,
        "tape_based.suffolk",
        kwargs=_kw(limit=1),
    ),
    "Temporary": Language("Temporary", _generate.temporary, "stack_based.temporary"),
    "3x": Language("3x", _generate.three_x),
    "Taglate": Language("Taglate", _generate.taglate, "other.taglate", split=True),
    "Unsquare": Language("Unsquare", _generate.unsquare),
    "WII2D": Language("WII2D", _generate.wii2d, "register_based.WII2D", split=True),
    "ZTOALC": Language("ZTOALC", _generate.ztoalc, "other.ztoalc", split=True),
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
