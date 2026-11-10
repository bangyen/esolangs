"""Independent Fargo value/frame bridges; no interpreter imports."""

from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot, WorkspaceVariant

WORKSPACE = WorkspaceModel(
    "fargo-v1",
    ("instruction", "input_number", "output_number", "frames", "input_cursor"),
)


def callable_value(value):
    return hasattr(value, "arguments") and hasattr(value, "unevaluated")


def resource_value(value):
    """Encode arrays iteratively; empty array and zero are distinct types."""
    completed = {}
    pending = [(value, False)]
    while pending:
        item, ready = pending.pop()
        if id(item) in completed:
            continue
        if type(item) is int:
            completed[id(item)] = item
        elif callable_value(item):
            completed[id(item)] = WorkspaceVariant(
                "callable", (item.name, item.arguments, item.unevaluated)
            )
        elif ready:
            completed[id(item)] = WorkspaceVariant(
                "array", tuple(completed[id(child)] for child in item)
            )
        else:
            assert type(item) is tuple
            pending.append((item, True))
            pending.extend((child, False) for child in item)
    return completed[id(value)]


def snapshot(row):
    state = row.state
    assert state is not None
    frames = tuple(
        WorkspaceVariant(
            "frame",
            (
                frame.code,
                frame.offset,
                frame.label,
                resource_value(frame.last),
                tuple(
                    (resource_value(fn), tuple(resource_value(arg) for arg in args))
                    for fn, args in frame.waiting
                ),
                frozenset(
                    (key, resource_value(value)) for key, value in frame.bindings
                ),
            ),
        )
        for frame in state.continuations
    )
    return WorkspaceSnapshot(
        WORKSPACE,
        (state.line, state.number, state.output, frames, row.cursor),
    )


def decimal_text(value):
    """Spell integers using bounded chunks, independently of the host cap."""
    negative = value < 0
    value = abs(value)
    chunks = []
    while value:
        value, remainder = divmod(value, 1_000_000_000)
        chunks.append(remainder)
    if not chunks:
        return "0"
    return (
        ("-" if negative else "")
        + str(chunks[-1])
        + "".join(f"{chunk:09d}" for chunk in reversed(chunks[:-1]))
    )


def value_repr(value):
    if callable_value(value):
        return f"_Func({value.name!r}, {value.arguments}, {value.unevaluated!r})"
    if type(value) is int:
        return decimal_text(value)
    pieces = [value_repr(child) for child in value]
    return "(" + ", ".join(pieces) + ("," if len(pieces) == 1 else "") + ")"


def frame_repr(frame):
    waiting = tuple(
        (ReprValue(value_repr(fn)), tuple(ReprValue(value_repr(arg)) for arg in args))
        for fn, args in frame.waiting
    )
    bindings = tuple(
        (key, ReprValue(value_repr(value))) for key, value in frame.bindings
    )
    return (
        f"_Frame(tokens={frame.code!r}, pos={frame.offset}, pending={waiting!r}, "
        f"binds={bindings!r}, fn_name={frame.label!r}, result={value_repr(frame.last)})"
    )


class ReprValue:
    def __init__(self, text):
        self.text = text

    def __repr__(self):
        return self.text


def cycle(row):
    state = row.state
    assert state is not None
    return (
        state.line,
        state.number,
        state.output,
        tuple(
            (
                frame.code,
                frame.offset,
                frame.label,
                value_repr(frame.last),
                tuple(
                    (fn.name, tuple(value_repr(arg) for arg in args))
                    for fn, args in frame.waiting
                ),
                tuple(
                    sorted((key, value_repr(value)) for key, value in frame.bindings)
                ),
            )
            for frame in state.continuations
        ),
        row.cursor,
    )


def entry_key(frame, cursor):
    return (
        frame.label,
        tuple(sorted((key, value_repr(value)) for key, value in frame.bindings)),
        cursor,
    )


def shorten(text):
    return text if len(text) <= 60 else text[:57] + "..."


def debug(row):
    state = row.state
    frames = state.continuations
    shown = "[" + ", ".join(frame_repr(frame) for frame in frames[:8]) + "]"
    shown = shown + f" +{len(frames) - 8} more" if len(frames) > 8 else shorten(shown)
    return {
        "ip": state.line,
        "memory": (state.number, state.output),
        "pointer": None,
        "stack": frames,
        "views": (
            ("frames", shown),
            ("ind", shorten(repr(state.line))),
            ("number", shorten(decimal_text(state.number))),
        ),
    }
