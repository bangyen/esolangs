"""Mutable independent Packlang frames, expressions, stores and ports."""

import copy

from tests.interpreters.packlang_program_reference import Program


class InvalidOperationError(Exception):
    pass


def instructions(body):
    code = []

    def visit(statements):
        for statement in statements:
            if statement[0] in ("if", "while"):
                start = len(code)
                code.append(["guard", statement[1], None])
                visit(statement[2])
                if statement[0] == "while":
                    code.append(["jump", start])
                code[start][2] = len(code)
            else:
                code.append(statement)

    visit(body)
    return code


class Reference:
    def __init__(self, source, stdin=""):
        self.program = Program(source)
        self.stdin = stdin
        self.offset = 0
        self.reads = 0
        self.past_end = 0
        self.output = ""
        mains = [
            key
            for key, function in self.program.functions.items()
            if key[1] == "main" and not function["params"]
        ]
        if len(mains) > 1:
            raise ValueError("multiple main functions")
        entry = mains[0] if mains else None
        if entry is None:
            for package in reversed(self.program.order):
                eligible = [
                    key
                    for key, function in self.program.functions.items()
                    if key[0] == package and not function["params"]
                ]
                if len(eligible) == 1:
                    entry = eligible[0]
                    break
        if entry is None:
            raise ValueError("missing entry")
        self.code = {
            key: instructions(function["body"])
            for key, function in self.program.functions.items()
        }
        self.frames = [self.frame(entry, [])]

    def frame(self, key, values):
        function = self.program.functions[key]
        if len(values) != len(function["params"]):
            raise InvalidOperationError("call arity")
        types = {
            slot: kind
            for (package, slot), kind in self.program.globals.items()
            if package == key[0]
        }
        types.update(function["locals"])
        store = {
            slot: kind[0] if kind[4] is None else [kind[0]] * kind[4]
            for slot, kind in types.items()
        }
        store.update(zip(function["params"], values, strict=False))
        return {
            "key": key,
            "pc": 0,
            "store": store,
            "types": types,
            "result": 0,
            "pending": None,
            "returned": None,
        }

    def value(self, node, frame):
        kind = node[0]
        store = frame["store"]
        if kind in ("number", "resolved"):
            return node[1]
        if kind == "invert":
            return int(self.value(node[1], frame) == 0)
        if kind == "xor":
            return self.value(node[1], frame) ^ self.value(node[2], frame)
        name = node[1]
        if name not in store:
            raise InvalidOperationError("undefined variable")
        value = store[name]
        if kind == "variable":
            if isinstance(value, list):
                raise InvalidOperationError("array scalar")
            return value
        if not isinstance(value, list):
            raise InvalidOperationError("scalar indexing")
        if kind == "length":
            return len(value)
        if len(node[2]) != 1:
            raise InvalidOperationError("index arity")
        index = self.value(node[2][0], frame)
        if not 0 <= index < len(value):
            raise InvalidOperationError("index bounds")
        return value[index]

    def call(self, node, frame):
        kind = node[0]
        children = (
            node[1:2]
            if kind == "invert"
            else node[1:3]
            if kind == "xor"
            else node[2]
            if kind == "apply"
            else []
        )
        for child in children:
            found = self.call(child, frame)
            if found is not None:
                return found
        return node if kind == "apply" and node[1] not in frame["store"] else None

    def function(self, name, package):
        if (package, name) in self.program.functions:
            return (package, name)
        reachable = set()
        todo = [package]
        while todo:
            selected = todo.pop()
            if selected in reachable:
                continue
            reachable.add(selected)
            todo.extend(self.program.dependencies.get(selected, set()))
        eligible = [
            key
            for key in self.program.functions
            if key[0] in reachable and key[1] == name
        ]
        if len(eligible) != 1:
            raise InvalidOperationError("missing or ambiguous function")
        return eligible[0]

    def step(self):
        if not self.frames:
            return
        frame = self.frames[-1]
        code = self.code[frame["key"]]
        if frame["pc"] == len(code):
            self.frames.pop()
            if self.frames:
                self.frames[-1]["returned"] = frame["result"]
            return
        statement = code[frame["pc"]]
        opcode = statement[0]
        expression = (
            statement[1]
            if opcode in ("print", "val", "guard")
            else statement[2]
            if opcode in ("read", "init", "incr", "decr")
            else None
        )
        if expression is not None:
            if frame["pending"] is None:
                frame["pending"] = copy.deepcopy(expression)
            expression = frame["pending"]
            if frame["returned"] is not None:
                call = self.call(expression, frame)
                if call is None:
                    raise InvalidOperationError("return without call")
                call[:] = ["resolved", frame["returned"]]
                frame["returned"] = None
            call = self.call(expression, frame)
            if call is not None:
                key = self.function(call[1], frame["key"][0])
                values = [self.value(arg, frame) for arg in call[2]]
                self.frames.append(self.frame(key, values))
                return
        pc = frame["pc"] + 1
        if opcode == "print":
            self.output += chr(self.value(expression, frame) % 256)
        elif opcode == "val":
            frame["result"] = self.value(expression, frame)
        elif opcode == "guard":
            if not self.value(expression, frame):
                pc = statement[2]
        elif opcode == "jump":
            pc = statement[1]
        else:
            name = statement[1]
            store = frame["store"]
            if name not in store:
                raise InvalidOperationError("undefined target")
            index = None if expression is None else self.value(expression, frame)
            kind = frame["types"][name]
            value = store[name]
            if isinstance(value, list):
                if index is None:
                    if opcode != "init":
                        raise InvalidOperationError("array without index")
                    store[name] = [kind[0]] * kind[4]
                elif not 0 <= index < len(value):
                    raise InvalidOperationError("index bounds")
                else:
                    value[index] = self.update(value[index], opcode, kind)
            else:
                if index is not None:
                    raise InvalidOperationError("scalar indexing")
                store[name] = self.update(value, opcode, kind)
        frame["pc"] = pc
        frame["pending"] = None
        frame["returned"] = None

    def update(self, value, opcode, kind):
        if opcode == "init":
            return kind[0]
        if opcode == "read":
            if self.offset == len(self.stdin):
                self.past_end += 1
                return 10
            value = ord(self.stdin[self.offset])
            self.offset += 1
            self.reads += 1
            return value
        value += 1 if opcode == "incr" else -1
        return kind[2] if value < kind[0] else kind[3] if value > kind[1] else value
