r"""The committed boolean example programs, as data."""

from collections.abc import Callable
from dataclasses import dataclass, replace

from esolangs.registry import Generator, canonical_id
from esolangs.tools.boolean.a_painter_ant import _instantiate_apa
from esolangs.tools.boolean.helpers import instantiate
from esolangs.tools.boolean.parameterized import _instantiate_arrowqueue
from esolangs.tools.wrap import DEFAULT_WIDTH, takes_width, wrap_program

# The committed programs all.
# AND2 evaluated on 0,1.
# rows; keeping this corpus.
AND2 = "0001"


@dataclass(frozen=True)
class BooleanExample:
    r"""How one committed ``examples/boolean`` program is built and run."""

    generator: Generator
    table: str
    interpreter: str
    expected: str
    inputs: tuple[str, ...] = ()
    # : Whether ``expected`` is the.
    # : answer is the *halt* and.
    # : 123's constructed template.
    # : prints whatever that cell.
    # : no one should compare.
    # : "this program outputs.
    expected_compared: bool = True
    # : How the answer reaches the.
    # : program prints it.
    # : and loops forever for a 1,.
    # : program prints its whole.
    # : place in it, which ``note``.
    # : prose alone cannot be.
    # : dumps and forgot a third.
    answer_mode: str = "output"
    # : Where the answer sits in.
    # : it.
    # : for every language that.
    # : that dump state -- their.
    # : need saying: RAM0's answer.
    # : the end, and A Painter.
    answer_pattern: str = ""
    # : How this language spells a.
    # : mirror of ``alphabet`` for.
    # : cell ``o`` on black and.
    # :.
    # : For an ``answer_mode`` of.
    # : instead -- ``("halts",.
    # : goes was prose only, so a.
    # : hardcode halt-means-0 from.
    # : zero-per-language verifier.
    answer_values: tuple[str, str] = ("0", "1")
    # : How this language spells an.
    # : the digits, but not.
    # : than loud: Grapheme's.
    # : ``ord(line[0]) - 65`` and.
    # : ``A`` is a 1 and every.
    # : line and a ``"1"`` line.
    # : all-zeros row instead of.
    # : prose: ``ord('A') - 65`` is.
    # : the opposite of what the.
    # :.
    # : This said "every non-empty.
    # : as a 1", which is the.
    # : generator does with it.
    # : backwards, which is worse.
    # : the reason predicts.
    # : here so ``describe`` can.
    alphabet: tuple[str, str] = ("0", "1")
    # : How the bits are laid out.
    # : everywhere else;.
    # : seven bits per character.
    # : sends a single number whose.
    # : before the program starts.
    # : ``line_per_bit_padded`` is.
    # : majority, plus the leading.
    # : briefly called.
    # : Taglate "reads a character.
    # : false of the stdin it.
    # : whole lines.
    # : input-exhausted error; a.
    input_shape: str = "line_per_bit"
    # : Whether an odd input count.
    # : reads like any other digit.
    # : separator, so its n=3.
    # : input-exhausted error, and.
    # : MSB-set row wrongly.
    # : affine computation on the.
    ghost_digit: bool = False
    bits: tuple[int, ...] = ()
    fill: Callable[[str, list[int]], str] | None = None
    split: bool = False
    kwargs: tuple[tuple[str, int], ...] = ()
    note: str = ""
    stem: str = ""

    def build(self, width: int | None = DEFAULT_WIDTH) -> str:
        r"""Return the program text this example commits."""
        if width is not None and takes_width(self.generator):
            program = self.generator(self.table, width)
        else:
            program = self.generator(self.table)
        if self.fill is not None:
            program = self.fill(program, list(self.bits))
        return wrap_program(program, canonical_id(self.stem.replace("-", " ")), width)


def _kw(**kwargs: int) -> tuple[tuple[str, int], ...]:
    return tuple(kwargs.items())


def _reader(
    generator: Callable[[str], str],
    interpreter: str,
    *,
    table: str = AND2,
    inputs: tuple[str, ...] = ("0", "1"),
    expected: str = "0",
    split: bool = False,
    kwargs: tuple[tuple[str, int], ...] = (),
    note: str = "",
    alphabet: tuple[str, str] = ("0", "1"),
    input_shape: str = "line_per_bit",
    ghost_digit: bool = False,
    answer_mode: str = "output",
    answer_pattern: str = "",
    answer_values: tuple[str, str] = ("0", "1"),
) -> BooleanExample:
    r"""Build an input-reading example, whose bits are read from stdin."""
    return BooleanExample(
        answer_mode=answer_mode,
        answer_pattern=answer_pattern,
        answer_values=answer_values,
        generator=generator,
        table=table,
        interpreter=interpreter,
        expected=expected,
        inputs=inputs,
        alphabet=alphabet,
        input_shape=input_shape,
        ghost_digit=ghost_digit,
        split=split,
        kwargs=kwargs,
        note=note,
    )


def _embedded(
    generator: Callable[[str], str],
    interpreter: str,
    fill: Callable[[str, list[int]], str],
    *,
    table: str = AND2,
    bits: tuple[int, ...] = (0, 1),
    expected: str = "0",
    expected_compared: bool = True,
    split: bool = False,
    kwargs: tuple[tuple[str, int], ...] = (),
    note: str = "",
    answer_mode: str = "output",
    answer_pattern: str = "",
    answer_values: tuple[str, str] = ("0", "1"),
) -> BooleanExample:
    r"""Build a parameterized example, whose bits are embedded in the text."""
    return BooleanExample(
        answer_mode=answer_mode,
        answer_pattern=answer_pattern,
        answer_values=answer_values,
        generator=generator,
        table=table,
        interpreter=interpreter,
        expected=expected,
        expected_compared=expected_compared,
        bits=bits,
        fill=fill,
        split=split,
        kwargs=kwargs,
        note=note,
    )


# Each ``fill`` below is the.
# this bit", the counterpart of.
# performs.


def _fill_bio(template: str, bits: list[int]) -> str:
    r"""Pack each input into ``x`` by its binary weight, in a constant."""
    n = len(bits)
    return instantiate(
        template,
        bits,
        lambda i, b: ("0ox;" if b else "0oz;") * (2 ** (n - 1 - i)),
    )


def _fill_nocomment(template: str, bits: list[int]) -> str:
    return instantiate(
        template,
        bits,
        lambda _i, b: "c" if b == 0 else "i",
    )


def _fill_lamfunc(template: str, bits: list[int]) -> str:
    # each {Xi} fills a `vs v{i}`.
    return instantiate(
        template,
        bits,
        lambda _i, b: "0b" + str(b),
    )


def _fill_bitdeque(template: str, bits: list[int]) -> str:
    # The register flips after.
    # inputs in name order, so bit.
    # incoming register at i % 2.
    return instantiate(
        template,
        bits,
        lambda i, b: "PUSH INVERT" if b == i % 2 else "INVERT PUSH",
    )


def _fill_bfpda(template: str, bits: list[int]) -> str:
    r"""Push the bit, in a constant width."""
    return instantiate(
        template,
        bits,
        lambda _i, b: "<@@@" if b else "<[@]",
    )


def _fill_back(template: str, bits: list[int]) -> str:
    r"""Finish each input cell: ``+`` leaves the one, ``-`` flips it to."""
    return instantiate(
        template,
        bits,
        lambda _i, b: "+" if b else "-",
    )


def _fill_minsky_swap(template: str, bits: list[int]) -> str:
    r"""Set each input register by counting ``+`` against a ``*`` pad."""
    n = len(bits)
    size: int = 2**n

    def set_bit(i: int, bit: int) -> str:
        if i == n - 1:  # LSB: length-4 block, no "~".
            return "+*+*" if bit else "****"
        weight: int = 2 ** (n - 1 - i)
        if bit:
            return "+" * weight + "*" * (size - weight)
        return "*" * size

    return instantiate(template, bits, set_bit)


def _fill_ram0(template: str, bits: list[int]) -> str:
    r"""Set each input cell with ``Z A`` for a one and ``Z Z`` for a zero."""
    return instantiate(
        template,
        bits,
        lambda _i, b: "Z A" if b else "Z Z",
    )


def _fill_home_row(template: str, bits: list[int]) -> str:
    r"""Set the bit cell, in a constant width."""
    return instantiate(
        template,
        bits,
        lambda _i, b: "aj" if b else "as",
    )


def _fill_cod(template: str, bits: list[int]) -> str:
    r"""Set the cod's value to the bit at that input's ``+`` fork."""
    return instantiate(
        template,
        bits,
        lambda _i, b: ")" if b else " ",
    )


def _fill_eval(template: str, bits: list[int]) -> str:
    r"""Stage the bit on the tree stack, then move it to the input stack."""
    return instantiate(
        template,
        bits,
        lambda _i, b: "`=" if b else "0=",
    )


def _fill_wii2d(template: str, bits: list[int]) -> str:
    r"""Set each junction: ``v`` takes the 1-branch, ``>`` continues east."""
    return instantiate(
        template,
        bits,
        lambda _i, b: "v" if b else ">",
    )


def _fill_minifuck(template: str, bits: list[int]) -> str:
    r"""Write each bit at ``ptr+1``: ``[<`` for a one, ``xx`` for a zero."""
    return instantiate(
        template,
        bits,
        lambda _i, b: "[<" if b else "xx",
    )


def _fill_one_two_three(template: str, bits: list[int]) -> str:
    r"""Embed each bit as the generator's own ``ONE``/``ZERO`` command."""
    from esolangs.tools.boolean.one_two_three import ONE, ZERO

    return instantiate(template, bits, lambda _i, b: ONE if b else ZERO)


def _fill_pct_squared_minus_one(template: str, bits: list[int]) -> str:
    r"""Substitute each bit's setter, named by the template's own header."""
    from esolangs.tools.boolean.pct_squared_minus_one import fill

    return fill(template, bits)


def _fill_arrowqueue(template: str, bits: list[int]) -> str:
    # ArrowQueue rebuilds its whole.
    return _instantiate_arrowqueue(template, bits)


# Example file stem -> how that.
# language's display name.
BOOLEAN_EXAMPLES: dict[str, BooleanExample] = {}


def _register() -> None:
    from esolangs.tools import boolean as b

    reading = {
        "addsubjump": _reader(b.addsubjump, "register_based.addsubjump"),
        # An executed line prints its.
        # answer arrives with the.
        "algebraic-programming-language": _reader(
            b.algebraic_programming_language,
            "other.algebraic_programming_language",
            expected="0\n",
            note="an executed line prints its result, so the answer ends in a newline",
        ),
        "alight": _reader(b.alight, "grid_based.alight", split=True),
        "basicfuck": _reader(b.basicfuck, "tape_based.basicfuck"),
        "between": _reader(b.between, "register_based.between", split=True),
        "bfstack": _reader(b.bfstack, "stack_based.bfstack"),
        "bit~": _reader(b.bit_tilde, "tape_based.bit_tilde"),
        "brainfuck": _reader(b.brainfuck, "tape_based.brainfuck"),
        "brainif": _reader(b.brainif, "tape_based.brainif", split=True),
        "circlefuck": _reader(b.circlefuck, "tape_based.circlefuck"),
        "collatz-multiverse": _reader(
            b.collatz_multiverse, "register_based.collatz_multiverse"
        ),
        "container": _reader(
            b.container,
            "other.container",
            split=True,
            note="Container prints the answer like any other reader; it "
            "also ends by calling sys.exit(0) rather than returning, which "
            "matters to a harness driving it but not to reading the result",
        ),
        # ``send`` terminates every.
        # with a newline after it --.
        "inject": _reader(
            b.inject,
            "other.inject",
            expected="0\n",
            note="send terminates each line, so the answer ends in a newline",
        ),
        "interprogck8": _reader(
            b.interprogck8,
            "register_based.interprogck8",
            split=True,
        ),
        "circuit_diagram": _reader(
            b.circuit_diagram,
            "grid_based.circuit_diagram",
            split=True,
        ),
        "clockwise": _reader(
            b.clockwise,
            "grid_based.clockwise",
            inputs=("01",),
            input_shape="one_line",
            split=True,
            note="Clockwise reads all its input bits in one go, so they go "
            "on one line -- one character per bit, not a line per bit, and "
            "not seven bits packed into a character: that packing is real "
            "but is on the output side. A line per bit, or a packed one, "
            "is read as a different row and answered wrongly",
        ),
        "cvnc": _reader(b.cvnc, "other.cvnc"),
        "decleq": _reader(b.decleq, "register_based.decleq"),
        "dig": _reader(b.dig, "grid_based.dig", split=True),
        "dimensional": _reader(b.dimensional, "tape_based.dimensional"),
        "dinac": _reader(b.dinac, "other.dinac"),
        "factor": _reader(b.factor, "tape_based.factor"),
        # Fargo reads one *number*.
        # line, and ``@ k`` indexes.
        # convention is therefore to.
        # most-significant-first are.
        # two-input table is the single.
        "fargo": _reader(
            b.fargo,
            "other.fargo",
            inputs=("1",),
            input_shape="row_index",
            note="Fargo reads one number whose bits are the inputs, so the "
            "committed input is the row index rather than a bit per line",
        ),
        "flowchart": _reader(b.flowchart, "grid_based.flowchart", split=True),
        "forbin": _reader(b.forbin, "other.forbin"),
        "forþ": _reader(b.forth, "stack_based.forth"),
        "function-x(y)": _reader(b.function_x_y, "other.function_x_y"),
        "grapheme": _reader(
            b.grapheme,
            "stack_based.grapheme",
            inputs=("%", "A"),
            alphabet=("%", "A"),
            note=(
                "Grapheme's generator normalizes each input line with "
                "ord(line[0]) - 65 and then maps zero to 1, so its input "
                "bits are spelled % and A: 'A' is a 1 and every other "
                "first character is a 0, which means a 0/1 line reads as 0 "
                "and the program answers the all-zeros row. The second "
                "step is not optional prose -- ord('A') - 65 is 0, so the "
                "subtraction alone says the opposite"
            ),
        ),
        "jaune": _reader(b.jaune, "tape_based.jaune"),
        "laserfuck": _reader(
            b.laserfuck,
            "grid_based.laserfuck",
            answer_mode="dump",
            split=True,
            expected="0",
            kwargs=_kw(seed=0),
            note=(
                "the initial heading is random by spec, so the example pins "
                "the source it is drawn from: seed 0 draws heading 3"
            ),
        ),
        "modulous": _reader(b.modulous, "stack_based.modulous"),
        "myscript": _reader(b.myscript, "register_based.myscript"),
        "nevermind": _reader(
            b.nevermind,
            "register_based.nevermind",
            split=True,
        ),
        "packlang": _reader(b.packlang, "other.packlang"),
        "painfuck": _reader(b.painfuck, "tape_based.painfuck"),
        "point-break": _reader(
            b.point_break,
            "register_based.point_break",
            answer_mode="termination",
            answer_values=("halts", "diverges"),
            expected="1 0 1 1 0 0 0 1",
            note=(
                "Point Break answers by termination -- it halts for a 0 "
                "result and loops forever for a 1, so only the halting "
                "branch is committed.  The numbers printed are its "
                "interpreter-only variable dump, which the verdict does not "
                "read: the answer is that the program halted at all"
            ),
        ),
        "polynomial": _reader(b.polynomial, "register_based.polynomial"),
        "qoibl": _reader(b.qoibl, "register_based.qoibl", split=True),
        "rotfuck": _reader(b.rotfuck, "tape_based.rotfuck"),
        "s*bleq": _reader(b.sbleq, "tape_based.sbleq"),
        "slow-acv-mammalian": _reader(
            b.slow_acv_mammalian, "tape_based.slow_acv_mammalian"
        ),
        "sophie": _reader(b.sophie, "register_based.sophie"),
        "streetcode": _reader(b.streetcode, "grid_based.streetcode", split=True),
        "super-snusp": _reader(b.super_snusp, "grid_based.super_snusp", split=True),
        "suffolk": _reader(b.suffolk, "tape_based.suffolk"),
        "suptiftam": _reader(b.suptiftam, "other.suptiftam"),
        "taglate": _reader(
            b.taglate,
            "queue_based.taglate",
            split=True,
            input_shape="line_per_bit_padded",
            ghost_digit=True,
            note="Taglate takes a line per bit like most languages, but an "
            "odd input count above 1 is padded with a leading zero it reads "
            "like any other digit: an n=3 program wants four lines. Feeding "
            "three exhausts its input; padding at the end instead answers "
            "every row whose top bit is set wrongly",
        ),
        "unsquare": _reader(b.unsquare, "stack_based.unsquare"),
        "ztoalc-l": _reader(b.ztoalc_l, "other.ztoalc_l", split=True),
        "3d-brainfuck": _reader(b.three_d_brainfuck, "tape_based.three_d_brainfuck"),
        "3x": _reader(b.three_x, "stack_based.three_x"),
        "6-5": _reader(b.six_five, "tape_based.six_five"),
    }

    embedded = {
        "a-painter-ant": _embedded(
            b.a_painter_ant,
            "grid_based.a_painter_ant",
            _instantiate_apa,
            answer_mode="dump",
            answer_pattern=r"(?m)^[.#o@]*([o@])[.#o@]*$",
            answer_values=("o", "@"),
            expected=(
                "..#......\n.........\n.........\n.........\n.........\n"
                ".........\n..#...#..\n.###.###.\n##o###.##\n.###.###.\n"
                "..#...#.."
            ),
            note=(
                "A Painter Ant has no output: it paints a grid and the answer "
                "is which of the two leaf rings the ant rests in, shown by "
                "'o' (on black, a zero) or '@' (on white, a one)"
            ),
        ),
        "back": _embedded(
            b.back,
            "tape_based.back",
            _fill_back,
            answer_mode="dump",
            split=True,
            expected="1 0 0",
            note=(
                "Back has no output instruction and dumps its tape at halt; "
                "the answer is cell n, past the n input cells -- which the "
                "reorder may hold in either order, so only cell n is pinned"
            ),
        ),
        "bf-pda": _embedded(b.bfpda, "stack_based.bf_pda", _fill_bfpda),
        "bio": _embedded(b.bio, "register_based.bio", _fill_bio),
        "bitdeque": _embedded(
            b.bitdeque,
            "queue_based.bitdeque",
            _fill_bitdeque,
            answer_mode="dump",
            note=(
                "Bitdeque has no output instruction and dumps its deque at "
                "halt; the generator leaves exactly one bit on it, so the "
                "whole dump is the answer and there is no position to name"
            ),
        ),
        "cod": _embedded(
            b.cod,
            "grid_based.cod",
            _fill_cod,
            note="COD has no runtime input and no I/O but a printed number",
        ),
        "eval": _embedded(b.eval, "stack_based.eval", _fill_eval),
        "home-row": _embedded(b.home_row, "tape_based.home_row", _fill_home_row),
        "lamfunc": _embedded(b.lamfunc, "other.lamfunc", _fill_lamfunc),
        "minifuck": _embedded(b.minifuck, "tape_based.minifuck", _fill_minifuck),
        "minsky-swap": _embedded(
            b.minsky_swap,
            "register_based.minsky_swap",
            _fill_minsky_swap,
            answer_mode="dump",
            expected="0 0",
            note=(
                "Minsky Swap has no output instruction and dumps its "
                "registers at halt; the answer is the second one"
            ),
        ),
        "nocomment": _embedded(b.nocomment, "tape_based.nocomment", _fill_nocomment),
        "ram0": _embedded(
            b.ram0,
            "register_based.ram0",
            _fill_ram0,
            answer_mode="dump",
            answer_pattern=r"z: (\d+)",
            expected="z: 0\nn: 1\nram: {\n    0: 0,\n    1: 1\n}",
            note=(
                "RAM0 has no output instruction and dumps its whole state "
                "at halt; the answer is the 'z' register"
            ),
        ),
        "wii2d": _embedded(
            b.wii2d,
            "grid_based.wii2d",
            _fill_wii2d,
            split=True,
        ),
        "pct-squared-minus-one": _embedded(
            b.pct_squared_minus_one,
            "register_based.pct_squared_minus_one",
            _fill_pct_squared_minus_one,
        ),
        # 123 answers with the.
        # only the halting (0) branch.
        # pops through location -2.
        # every row;.
        # them, so ``expected`` is.
        "123": _embedded(
            b.one_two_three,
            "tape_based.one_two_three",
            _fill_one_two_three,
            answer_mode="termination",
            answer_values=("halts", "diverges"),
            expected="",
            expected_compared=False,
            note=(
                "123 answers by terminating: it halts for a 0 result and loops "
                "forever for a 1, so only the halting branch is committed. Its "
                "output is not the answer and is not compared -- the merge pops "
                "through location -2 and prints whatever that cell holds, which "
                "for this program is the two bytes 'VO with a diaeresis'"
            ),
        ),
        "arrowqueue": _embedded(
            b.arrowqueue,
            "grid_based.arrowqueue",
            _fill_arrowqueue,
            answer_mode="termination",
            answer_values=("halts", "diverges"),
            expected="1 0 1 2 3",
            split=True,
            note=(
                "ArrowQueue answers by termination -- it halts for a 0 result "
                "and loops forever for a 1, so only the halting branch is "
                "committed.  The headings printed are its interpreter-only "
                "queue dump, which the verdict does not read: the answer is "
                "that the program halted at all"
            ),
        ),
    }

    # Stamp each example with its.
    # language it is and can pick.
    # the caller having to supply.
    for stem, example in {**reading, **embedded}.items():
        BOOLEAN_EXAMPLES[stem] = replace(example, stem=stem)


_register()

# Committed programs that no.
# behaviour tests but exempt.
# .
# Empty since Minifuck's entry.
# hand-written one: it read its.
# removed generator used, and.
# reading model.
# its inputs, so.
# every other file and the.
# ``docs/generators/minifuck_gen.
# .
# The mechanism is kept rather.
# what a future.
HAND_WRITTEN: dict[str, tuple[str, tuple[str, ...], str, bool]] = {}

__all__ = ["AND2", "BOOLEAN_EXAMPLES", "HAND_WRITTEN", "BooleanExample"]
