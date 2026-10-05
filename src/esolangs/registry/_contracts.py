"""Boolean I/O contracts, independent of example programs and documentation."""

from dataclasses import dataclass
from typing import Literal

type AnswerMode = Literal["output", "dump", "termination"]
type InputShape = Literal[
    "line_per_bit",
    "char_stream",
    "char_stream_padded",
    "char_stream_cyclic",
    "row_index",
]
type WidthEffect = Literal["layout", "wrap", "none"]


@dataclass(frozen=True, slots=True)
class BooleanContract:
    """Input encoding and answer extraction for a generated Boolean program."""

    parameterized: bool = False
    alphabet: tuple[str, str] = ("0", "1")
    input_shape: InputShape = "line_per_bit"
    ghost_digit: bool = False
    answer_mode: AnswerMode = "output"
    answer_pattern: str = ""
    answer_values: tuple[str, str] = ("0", "1")
    note: str = ""
    ignores_whitespace: bool = False


# Only departures from the default line-input, printed-bit contract.
CONTRACTS: dict[str, BooleanContract] = {
    "grid_based.a_painter_ant": BooleanContract(
        answer_mode="dump",
        answer_pattern=r"(?m)^[.#o@]*([o@])[.#o@]*$",
        answer_values=("o", "@"),
        note="A Painter Ant has no output: it paints a grid and the answer "
        "is the answer cell the ant rests on below its white corridor, "
        "shown by 'o' (on black, a zero) or '@' (on white, a one)",
        parameterized=True,
    ),
    "grid_based.alight": BooleanContract(
        input_shape="char_stream",
    ),
    "grid_based.arrowqueue": BooleanContract(
        answer_mode="termination",
        answer_values=("halts", "diverges"),
        note="ArrowQueue answers by termination -- it halts for a 0 result "
        "and loops forever for a 1, so only the halting branch is "
        "committed.  The headings printed are its interpreter-only "
        "queue dump, which the verdict does not read: the answer is "
        "that the program halted at all",
        parameterized=True,
    ),
    "grid_based.b_tapemark": BooleanContract(
        input_shape="char_stream",
    ),
    "grid_based.circuit_diagram": BooleanContract(
        input_shape="char_stream",
        ignores_whitespace=True,
    ),
    "grid_based.clockwise": BooleanContract(
        input_shape="char_stream_cyclic",
        note="Clockwise reads all its input bits in one go, so they go "
        "on one line -- one character per bit, not a line per bit, and "
        "not seven bits packed into a character: that packing is real "
        "but is on the output side. A line per bit, or a packed one, "
        "is read as a different row and answered wrongly",
    ),
    "grid_based.egl": BooleanContract(
        input_shape="char_stream",
    ),
    "grid_based.fish": BooleanContract(
        input_shape="char_stream",
    ),
    "grid_based.flowchart": BooleanContract(
        input_shape="char_stream",
        ignores_whitespace=True,
    ),
    "grid_based.laserfuck": BooleanContract(
        answer_mode="dump",
        note="the initial heading is random by spec, so the example pins "
        "the source it is drawn from: seed 0 draws heading 3",
        input_shape="char_stream",
    ),
    "grid_based.streetcode": BooleanContract(
        input_shape="char_stream",
    ),
    "grid_based.super_snusp": BooleanContract(
        input_shape="char_stream",
    ),
    "grid_based.thisthat": BooleanContract(
        input_shape="char_stream",
        ignores_whitespace=True,
    ),
    "other.algebraic_programming_language": BooleanContract(
        note="an executed line prints its result, so the answer ends in a newline",
    ),
    "other.container": BooleanContract(
        note="Container prints the answer like any other reader; it "
        "also ends by calling sys.exit(0) rather than returning, which "
        "matters to a harness driving it but not to reading the result",
        input_shape="char_stream",
    ),
    "other.crement": BooleanContract(
        answer_mode="termination",
        answer_values=("halts", "diverges"),
        note="Crement answers by termination: the tree's nodes patch a "
        "per-input tester's jump targets, and the row lands past the "
        "end (halts, 0) or on a self-jump (diverges, 1)",
        parameterized=True,
    ),
    "other.fargo": BooleanContract(
        input_shape="row_index",
        note="Fargo reads one number whose bits are the inputs, so the "
        "committed input is the row index rather than a bit per line",
    ),
    "other.forbin": BooleanContract(
        input_shape="char_stream",
    ),
    "other.fractran": BooleanContract(
        answer_mode="dump",
        answer_values=("1", "2"),
        note="FRACTRAN has neither input nor output: the inputs are the "
        "exponents of n primes in the starting value, and the answer "
        "is the value the run stops on -- 1 for a zero and 2 for a one",
        parameterized=True,
    ),
    "other.inject": BooleanContract(
        note="send terminates each line, so the answer ends in a newline",
    ),
    "other.intercal": BooleanContract(
        answer_pattern=r"(?s)^([I]?)\n$",
        answer_values=("", "I"),
        note="INTERCAL READ OUT prints blank for zero and I for one",
        parameterized=True,
    ),
    "other.malbolge": BooleanContract(
        note="the answer is one character and is printed with no newline",
        input_shape="char_stream",
    ),
    "other.packlang": BooleanContract(
        input_shape="char_stream",
    ),
    "other.slashes": BooleanContract(
        note="Inputs fill the binary row index before unary table selection.",
        parameterized=True,
    ),
    "other.thue": BooleanContract(
        note="Thue draws which rewrite to make, by spec, and the "
        "interpreter draws too; this program's rules are written so that "
        "every state it reaches has exactly one, leaving the draw nothing "
        "to change",
    ),
    "other.unlambda": BooleanContract(
        input_shape="char_stream",
    ),
    "other.vandevelo": BooleanContract(
        answer_mode="termination",
        answer_values=("halts", "diverges"),
        note="Vandevelo answers by terminating: nil halts and not nil loops",
    ),
    "queue_based.bitdeque": BooleanContract(
        answer_mode="dump",
        note="Bitdeque has no output instruction and dumps its deque at "
        "halt; the generator leaves exactly one bit on it, so the "
        "whole dump is the answer and there is no position to name",
        parameterized=True,
    ),
    "queue_based.bitwise_cyclic_tag": BooleanContract(
        note="Bitwise Cyclic Tag has no I/O vocabulary at all: the inputs "
        "are bits of the initial data-string, and the answer is the "
        "bit the last 0 deletes, which the interpreter prints alone -- "
        "so the output is the answer and there is no position to name",
        parameterized=True,
    ),
    "queue_based.cyclic_tag": BooleanContract(
        note="Inputs fill the initial queue; the final deleted bit is the answer.",
        parameterized=True,
    ),
    "queue_based.taglate": BooleanContract(
        input_shape="char_stream_padded",
        ghost_digit=True,
        note="Taglate reads adjacent characters, but an "
        "odd input count above 1 is padded with a leading zero it reads "
        "like any other digit: an n=3 program wants four characters. Feeding "
        "three exhausts its input; padding at the end instead answers "
        "every row whose top bit is set wrongly",
    ),
    "register_based.addsubjump": BooleanContract(
        input_shape="char_stream",
    ),
    "register_based.bio": BooleanContract(
        parameterized=True,
    ),
    "register_based.decleq": BooleanContract(
        input_shape="char_stream",
    ),
    "register_based.minsky_swap": BooleanContract(
        answer_mode="dump",
        note="Minsky Swap has no output instruction and dumps its "
        "registers at halt; the answer is the second one",
        parameterized=True,
    ),
    "register_based.polynomial": BooleanContract(
        input_shape="char_stream",
    ),
    "register_based.qoibl": BooleanContract(
        input_shape="char_stream",
    ),
    "register_based.ram0": BooleanContract(
        answer_mode="dump",
        answer_pattern=r"z: (\d+)",
        note="RAM0 has no output instruction and dumps its whole state "
        "at halt; the answer is the 'z' register",
        parameterized=True,
    ),
    "register_based.sophie": BooleanContract(
        input_shape="char_stream",
    ),
    "stack_based.bf_pda": BooleanContract(
        parameterized=True,
    ),
    "stack_based.bfstack": BooleanContract(
        input_shape="char_stream",
    ),
    "stack_based.eval": BooleanContract(
        parameterized=True,
    ),
    "stack_based.false": BooleanContract(
        input_shape="char_stream",
    ),
    "stack_based.grapheme": BooleanContract(
        alphabet=("%", "A"),
        note="Grapheme's generator normalizes each input line with "
        "ord(line[0]) - 65 and then maps zero to 1, so its input "
        "bits are spelled % and A: 'A' is a 1 and every other "
        "first character is a 0, which means a 0/1 line reads as 0 "
        "and the program answers the all-zeros row. The second "
        "step is not optional prose -- ord('A') - 65 is 0, so the "
        "subtraction alone says the opposite",
    ),
    "stack_based.underload": BooleanContract(
        parameterized=True,
    ),
    "stack_based.unsquare": BooleanContract(
        input_shape="char_stream",
    ),
    "tape_based.back": BooleanContract(
        answer_mode="dump",
        note="Back has no output instruction and dumps its tape at halt; "
        "the answer is cell n, past the n input cells",
        parameterized=True,
    ),
    "tape_based.bit_tilde": BooleanContract(
        input_shape="char_stream",
    ),
    "tape_based.boolfuck": BooleanContract(
        input_shape="char_stream",
    ),
    "tape_based.brainfuck": BooleanContract(
        input_shape="char_stream",
    ),
    "tape_based.brainif": BooleanContract(
        input_shape="char_stream",
    ),
    "tape_based.circlefuck": BooleanContract(
        input_shape="char_stream",
    ),
    "tape_based.factor": BooleanContract(
        input_shape="char_stream",
    ),
    "tape_based.home_row": BooleanContract(
        parameterized=True,
    ),
    "tape_based.minifuck": BooleanContract(
        parameterized=True,
    ),
    "tape_based.nocomment": BooleanContract(
        parameterized=True,
    ),
    "tape_based.one_two_three": BooleanContract(
        answer_mode="termination",
        answer_values=("halts", "diverges"),
        note="123 answers by terminating: it halts for a 0 result and loops "
        "forever for a 1, so only the halting branch is committed. Its "
        "output is not the answer and is not compared -- the merge pops "
        "through location -2 and prints whatever that cell holds, which "
        "for this program is the two bytes 'VO with a diaeresis'",
        parameterized=True,
    ),
    "tape_based.rotfuck": BooleanContract(
        input_shape="char_stream",
    ),
    "tape_based.sbleq": BooleanContract(
        input_shape="char_stream",
    ),
    "tape_based.six_five": BooleanContract(
        input_shape="char_stream",
    ),
    "tape_based.slow_acv_mammalian": BooleanContract(
        input_shape="char_stream",
    ),
    "tape_based.smallfuck": BooleanContract(
        note="Smallfuck defines no I/O; this implementation prints final cell 2",
        parameterized=True,
    ),
    "tape_based.subleq": BooleanContract(
        input_shape="char_stream",
    ),
    "tape_based.suffolk": BooleanContract(
        input_shape="char_stream",
    ),
    "tape_based.three_d_brainfuck": BooleanContract(
        input_shape="char_stream",
    ),
    "stack_based.piet": BooleanContract(
        note="80 pixels per codel, comparable in area to Line"
    ),
}
