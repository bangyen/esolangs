from functools import cache

_OPS = {
    4: "jump",
    5: "out",
    23: "in",
    39: "rotate",
    40: "seek",
    62: "mix",
    68: "pass",
    81: "stop",
}
_CIPHER = (
    "5z]&gqtyfr$(we4{WP)H-Zn,[%\\3dL+Q;>U!pJS72FhOA1C"
    "B6v^=I_0/8|jsb9m<.TVac`uY*MK'X~xDl}REokN:#?G\"i@"
)
_WORDS = 59049


@cache
def _mix(left, right):
    value = 0
    for place in range(10):
        left, x = divmod(left, 3)
        right, y = divmod(right, 3)
        value += int(("100", "102", "221")[y][x]) * 3**place
    return value


@cache
def _image(code):
    memory = [ord(c) for c in code if not c.isspace()]
    if any(
        (
            not 33 <= word <= 126 or (word + i) % 94 not in _OPS
            for i, word in enumerate(memory)
        )
    ):
        raise ValueError
    previous, last = [0, 0, *memory][-2:]
    for _ in range(len(memory), _WORDS):
        previous, last = (last, _mix(last, previous))
        memory.append(last)
    return tuple(memory)


class _PagedWords:
    """Pure reference store; only independently changed pages are rebuilt."""

    def __init__(self, words):
        self.words = list(words)
        self.pages = [tuple(words[start : start + 64]) for start in range(0, 59049, 64)]
        self.dirty = set()

    def __getitem__(self, address):
        return self.words[address]

    def __setitem__(self, address, value):
        self.words[address] = value
        self.dirty.add(address // 64)

    def capture(self):
        for page in self.dirty:
            start = page * 64
            self.pages[page] = tuple(self.words[start : min(start + 64, 59049)])
        self.dirty.clear()
        return tuple(self.pages)


def _full_projection(a, c, d, halted, memory):
    return (a, c, d, halted, memory.capture())


def _full_model(code, stdin):
    try:
        memory = _PagedWords(_image(code))
    except ValueError:
        return ("syntax", [(None, False, "", 0, 0)])
    a = c = d = cursor = 0
    output = ""
    halted = False
    trace = []
    for _ in range(129):
        trace.append(
            (_full_projection(a, c, d, halted, memory), halted, output, cursor, cursor)
        )
        if halted:
            return (None, trace + [trace[-1]] * 3)
        word = memory[c]
        operation = _OPS.get((word + c) % 94)
        if not 33 <= word <= 126 or operation == "stop":
            halted = True
            continue
        match operation:
            case "jump":
                c = memory[d]
            case "seek":
                d = memory[d]
            case "rotate":
                low = memory[d] % 3
                a = memory[d] = low * 19683 + memory[d] // 3
            case "mix":
                a = memory[d] = _mix(a, memory[d])
            case "in":
                a = ord(stdin[cursor]) if cursor < len(stdin) else 59048
                cursor += cursor < len(stdin)
            case "out":
                output += chr(a % 256)
        word = memory[c]
        if 33 <= word <= 126:
            memory[c] = ord(_CIPHER[word - 33])
        c, d = ((c + 1) % _WORDS, (d + 1) % _WORDS)
    return (None, trace)
