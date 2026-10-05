"""Independent Packlang scanner and expression parser."""


def tokens(source):
    result = []
    at = 0
    while at < len(source):
        char = source[at]
        if char.isspace():
            at += 1
            continue
        if char == "%":
            if source[at : at + 2] == "%$":
                stop = source.find("%", at + 2)
                at = len(source) if stop < 0 else stop + 1
            else:
                stop = source.find("\n", at + 1)
                at = len(source) if stop < 0 else stop
            continue
        if char in "{}();:,^!":
            result.append(char)
            at += 1
            continue
        if char.isascii() and (char.isalpha() or char == "_"):
            stop = at + 1
            while (
                stop < len(source)
                and source[stop].isascii()
                and (source[stop].isalnum() or source[stop] == "_")
            ):
                stop += 1
            result.append(source[at:stop])
            at = stop
            continue
        if char in "0123456789":
            stop = at + 1
            while stop < len(source) and source[stop] in "0123456789":
                stop += 1
            result.append(source[at:stop])
            at = stop
            continue
        raise ValueError("invalid source character")
    return result


class Expression:
    def __init__(self, source):
        self.words = tokens(source)
        self.cursor = 0

    def take(self, word=None):
        if self.cursor == len(self.words):
            raise ValueError("incomplete expression")
        value = self.words[self.cursor]
        self.cursor += 1
        if word is not None and value != word:
            raise ValueError("unexpected token")
        return value

    def peek(self):
        return self.words[self.cursor] if self.cursor < len(self.words) else None

    def parse(self):
        node = self.chain()
        if self.peek() is not None:
            raise ValueError("trailing expression token")
        return node

    def chain(self):
        left = self.atom()
        while self.peek() == "^":
            self.take()
            left = ["xor", left, self.atom()]
        return left

    def atom(self):
        word = self.take()
        if word == "!":
            return ["invert", self.atom()]
        if word == "(":
            node = self.chain()
            self.take(")")
            return node
        if word[0] in "0123456789":
            return ["number", int(word)]
        if not (word[0].isalpha() or word[0] == "_"):
            raise ValueError("expected operand")
        if self.peek() != "(":
            return ["variable", word]
        self.take("(")
        if self.peek() == "length":
            self.take()
            self.take(")")
            return ["length", word]
        arguments = []
        if self.peek() != ")":
            arguments.append(self.chain())
            while self.peek() == ",":
                self.take()
                arguments.append(self.chain())
        self.take(")")
        return ["apply", word, arguments]


def native_tree(node):
    tag = node[0]
    if tag == "number":
        return ("lit", node[1])
    if tag == "variable":
        return ("var", node[1])
    if tag == "invert":
        return ("not", native_tree(node[1]))
    if tag == "xor":
        return ("xor", native_tree(node[1]), native_tree(node[2]))
    if tag == "length":
        return ("length", node[1])
    return ("apply", node[1], tuple(native_tree(arg) for arg in node[2]))
