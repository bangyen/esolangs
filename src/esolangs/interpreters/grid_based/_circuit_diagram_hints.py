"""Repair guidance for circuit diagram source errors."""

from enum import StrEnum

from esolangs.interpreters.source_hints import syntax_error


class Hint(StrEnum):
    """Accepted grammar at each rejected source boundary."""

    FUNCTION_HEADER = "put a function header before its terminator"
    FUNCTION_END = "close the function definition with its terminator"
    FUNCTION_NAME = "give each function a unique name"
    RESERVED_NAME = "choose a function name that is not a built-in gate or source"
    SUPPORTED_GATES = "use the supported Circuit Diagram gates and wires"
    SYMBOL = "use a gate symbol, wire glyph or defined function name at this coordinate"
    FUNCTION_OR_WIDTH = (
        "define the function, or put a valid width label on an adjacent wire"
    )
    WIRE_LABEL = "put the width label directly beside a wire"
    POSITIVE_WIDTH = "label the wire with a positive width"
    WIRE_WIDTH = "give all labels on the same wiring the same width"
    OUTPUT_WIRE = "put a horizontal - wire immediately left of :"
    INPUT_PORTS = "connect the required number of input ports on the left of the gate"
    OUTPUT_PORTS = (
        "connect the required number of output ports on the right of the gate"
    )
    GATE_WIDTH = "make the wire width label agree with the gate input and output widths"
    SETTLED_WIDTHS = "use consistent positive wire widths throughout the circuit"
    SYMBOLIC_WIDTH = "use the same width for each occurrence of a symbolic label"
    LABEL_WIDTH = "make the symbolic width agree with the numeric wire label"
    OUTPUT_SLICE = "keep at least one output wire after the % slice"
    FUNCTION_BODY = "define the called function before running it"
    FUNCTION_ARITY = "keep the function input count consistent with its definition"
    SINGLE_INPUT_WIRE = "connect a one-wire value to this function input"
    INPUT_WIDTH = "connect the declared number of wires to this function input"
    BOUND_WIDTH = "bind each symbolic input width consistently"
    INPUT_LABEL = (
        "use a positive numeric width or a single symbolic name for the function input"
    )
    SETTLED_FUNCTION = (
        "remove oscillating feedback from the function so it reaches a settled output"
    )
    RETURN_BITS = "connect a bit-valued return wire in the function body"

    def error(self, message: str) -> ValueError:
        """Attach this grammar hint to the rejected source diagnostic."""
        return syntax_error(message, self)
