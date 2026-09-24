"""Every registered language: its interpreter, source shape, and generator."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from esolangs import line as _line
from esolangs import piet as _piet
from esolangs import tools as _boolean
from esolangs.raster import Raster
from esolangs.registry._slug import canonical_id

# A generator: ``generator(truth_table)`` returns a program computing it.
# Most take only the table; the few that lay their program out in two
# dimensions (LaserFuck, which folds its beam's track) also accept a
# ``width`` bounding the columns, since a shape cannot be reflowed after the
# fact the way a single long line can.  ``...`` keeps both arities callable
# with the table alone, which is how every width-less caller invokes them.
Generator = Callable[..., str]
RasterGenerator = Callable[..., Raster]


class SourceKind(StrEnum):
    """The representation an interpreter consumes."""

    TEXT = "text"
    RASTER = "raster"


@dataclass(frozen=True)
class Language:
    """Language name, interpreter, source shape, id, and optional generator."""

    name: str
    interpreter: str | None = None
    split: bool = False
    id: str = ""
    boolean: Generator | None = None
    source_kind: SourceKind = SourceKind.TEXT
    raster_boolean: RasterGenerator | None = None


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
    "B-tapemark": Language(
        "B-tapemark",
        boolean=_boolean.b_tapemark,
        id="b_tapemark",
        interpreter="grid_based.b_tapemark",
    ),
    "BF-PDA": Language(
        "BF-PDA",
        boolean=_boolean.bfpda,
        id="bf_pda",
        interpreter="stack_based.bf_pda",
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
    "Crement": Language(
        "Crement",
        "other.crement",
        boolean=_boolean.crement,
        id="crement",
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
    "EGL": Language(
        "EGL",
        "grid_based.egl",
        boolean=_boolean.egl,
        id="egl",
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
    "Jaune": Language(
        "Jaune",
        boolean=_boolean.jaune,
        id="jaune",
        interpreter="tape_based.jaune",
    ),
    "LaserFuck": Language(
        "LaserFuck",
        "grid_based.laserfuck",
        boolean=_boolean.laserfuck,
        id="laserfuck",
        split=True,
    ),
    "Line": Language(
        "Line",
        id="line",
        source_kind=SourceKind.RASTER,
        raster_boolean=_line.generate,
    ),
    "Piet": Language(
        "Piet",
        id="piet",
        source_kind=SourceKind.RASTER,
        raster_boolean=_piet.generate,
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
    "Vandevelo": Language(
        "Vandevelo",
        "other.vandevelo",
        boolean=_boolean.vandevelo,
        id="vandevelo",
    ),
}

#: Widely known classics kept for coverage as much as construction.  All
#: three now carry a generator, but they sit outside the four admission axes:
#: they are here because a caller expects them, and each is an ordinary
#: machine in its own costume.  Malbolge's generator caps at thirteen inputs.
CLASSICS: dict[str, Language] = {
    "Befunge": Language(
        "Befunge",
        "grid_based.befunge",
        boolean=_boolean.befunge,
        id="befunge",
        split=True,
    ),
    "Malbolge": Language(
        "Malbolge",
        "other.malbolge",
        boolean=_boolean.malbolge,
        id="malbolge",
    ),
    "Whitespace": Language(
        "Whitespace",
        "stack_based.whitespace",
        boolean=_boolean.whitespace,
        id="whitespace",
    ),
}

LANGUAGES.update(CLASSICS)
