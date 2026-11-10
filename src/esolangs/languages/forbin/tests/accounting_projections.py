"""Independent Forbin code, lexical-entry and IO blueprints; source-only draft."""

from dataclasses import fields, is_dataclass

from .accounting_model import Closure


def code_blueprint(program):
    """Retain source and every independently parsed rule, including dead code."""

    def freeze(value):
        if value is None or type(value) in (str, int, bool):
            return value
        if type(value) is tuple:
            return tuple(freeze(item) for item in value)
        if is_dataclass(value):
            return (
                type(value).__name__,
                tuple(
                    (field.name, freeze(getattr(value, field.name)))
                    for field in fields(value)
                ),
            )
        raise TypeError(("unexpected independent code value", type(value)))

    return freeze(program)


def lexical_graph(machine, roots):
    """Root global first, then explicit ordered roots; close parents and closures."""
    pending, indices = [0], {0: 0}

    def reference(environment):
        if environment not in indices:
            indices[environment] = len(pending)
            pending.append(environment)
        return ("reference", (indices[environment],))

    def function(value):
        return ("global", ()) if value is None else ("function", (value.site,))

    def value(item):
        if type(item) is int:
            return item
        # Independent Closure is deliberately not confused with a native object.
        if type(item) is Closure:
            return ("closure", (function(item.function), reference(item.environment)))
        if item in ("in", "out"):
            return ("input" if item == "in" else "output", ())
        raise TypeError(("unexpected independent runtime value", type(item)))

    root_refs = tuple(reference(root) for root in roots)
    nodes = []
    cursor = 0
    while cursor < len(pending):
        scope = machine.state.environments[pending[cursor]]
        parent = None if scope.parent is None else reference(scope.parent)
        bindings = frozenset(
            (name, value(item)) for name, item in sorted(scope.values.items())
        )
        nodes.append(("environment", (function(scope.function), parent, bindings)))
        cursor += 1
    return root_refs, tuple(nodes)


def entry_blueprint(machine, index=-1):
    """An entry replays only with equal lexical graph AND unread-input state."""
    frame = machine.state.frames[index]
    roots, graph = lexical_graph(machine, (frame.environment,))
    return (
        ("function", (frame.function.site,)),
        (roots[0], graph),
        machine.port.position,
        machine.state.bits,
        machine.state.reads,
    )


def workspace_blueprint(machine):
    """Preserve all five independent parts; never replace entry with full stack."""
    # The existing engine already declares the complete ordered frame payload,
    # including closure-valued loop rows and the live global lexical graph.
    return machine.parts()


def cycle_blueprint(machine):
    """Logical full-state comparison, before native cycle-label validation."""
    return code_blueprint(machine.program), workspace_blueprint(machine)


def io_blueprint(port):
    """Replay actual independent IO effects into all ScriptedIO storage fields."""
    output, cursor, reads, past, character, newline = "", 0, 0, 0, False, False
    for event in port.events:
        kind = event[0]
        if kind == "read":
            byte = event[1]
            assert cursor < len(port.text)
            assert ord(port.text[cursor]) == byte
            cursor += 1
            reads += 1
            character = True
            newline = False
        elif kind == "eof":
            assert cursor == len(port.text)
            character = True
            past += 1
        elif kind == "write":
            char = event[1]
            assert type(char) is str
            assert len(char) == 1
            output += char
            newline = char != "\n"
        elif kind == "refuse_write":
            char, partial = event[1:]
            assert type(char) is str
            assert len(char) == 1
            assert type(partial) is bool
            if partial:
                output += char
            # Refusal is inside _write: outer print_char has not committed its flag.
        elif kind != "refuse_read":
            raise ValueError(("unknown independent IO event", event))
    assert (output, cursor, reads, past, newline) == (
        port.output,
        port.position,
        port.reads,
        port.past_end,
        port.newline,
    )
    return {
        "_supplied": port.text.count("\n")
        + int(bool(port.text) and not port.text.endswith("\n")),
        "_source": port.text,
        "_offset": cursor,
        "_line_reads": 0,
        "_character_reads": character,
        "_past_end": past,
        "_pending": "",
        "_reads": reads,
        "_consumed": cursor,
        "_newline": newline,
        "_buffer": (output, "\n", len(output), None),
    }


def observation_blueprint(machine, *, completion=None, steps=None):
    """Primitive result fields; envelopes/classification remain separate controls."""
    port = io_blueprint(machine.port)
    return (
        port["_buffer"][0],
        port["_offset"],
        port["_reads"],
        port["_past_end"],
        completion,
        steps,
    )


class AncestorHistory:
    """Consume independently modeled pushes; budget exhaustion is no verdict."""

    def __init__(self, limit=64):
        """Keep the existing positive push budget; zero is not admitted here."""
        assert type(limit) is int
        assert limit > 0
        self.limit = limit
        self.entries = []
        self.pushes = 0

    def boundary(self, machine, previous_depth):
        """Inspect one successful transition, with the prior stack depth saved."""
        if machine.halted:
            return True
        depth = len(machine.state.frames)
        if depth <= previous_depth:
            return None
        if self.pushes == self.limit:
            raise TimeoutError("independent pushed-frame budget exhausted")
        self.pushes += 1
        at = depth - 1
        self.entries = [(d, key) for d, key in self.entries if d < at]
        key = entry_blueprint(machine)
        if any(key == saved for _, saved in self.entries):
            return False
        self.entries.append((at, key))
        # Caller must stop after this boundary if this was the final admitted
        # push, matching the old walk's bounded undecided outcome.
        if self.pushes == self.limit:
            raise TimeoutError("independent pushed-frame budget exhausted")
        return None
