"""Finite-input semantic pruning oracle for Brainfuck."""


def read_prune(code: str, visited: set[int]) -> str:
    """Delete unseen reads, then cancel universally sound adjacent pairs."""
    stack: list[str] = []
    for position, char in enumerate(code):
        if char == "," and position not in visited:
            continue
        if stack and stack[-1] + char in {"+-", "-+", "><"}:
            stack.pop()
        else:
            stack.append(char)
    return "".join(stack)
