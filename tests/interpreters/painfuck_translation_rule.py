"""Successive suffix substitutions for Painfuck's declared alphabet."""

CYCLES = ("pevkjzwr", "yuctsobqihald")
NEXT = {
    cycle[index]: cycle[(index + 1) % len(cycle)]
    for cycle in CYCLES
    for index in range(len(cycle))
}
PREVIOUS = {after: before for before, after in NEXT.items()}


def translate(source):
    commands = [char for char in source if char in NEXT]
    for position in range(len(commands)):
        for later in range(position + 1, len(commands)):
            commands[later] = NEXT[commands[later]]
    return "".join(commands)


def encode(commands):
    if any(char not in NEXT for char in commands):
        raise ValueError("unknown command")
    result = list(commands)
    for position in range(len(result)):
        for later in range(position + 1, len(result)):
            result[later] = PREVIOUS[result[later]]
    return "".join(result)
