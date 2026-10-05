"""Independent structured Packlang parser; no native parser imports."""

from tests.interpreters.packlang_expression_reference import Expression, native_tree


class Program(Expression):
    def __init__(self, source):
        super().__init__(source)
        self.functions = {}
        self.globals = {}
        self.dependencies = {}
        self.order = []
        while self.peek() is not None:
            kind = self.take()
            if kind not in ("Package", "Dependency"):
                raise ValueError("expected package")
            deps = []
            if self.peek() == ":":
                self.take()
                deps.append(self.identifier())
                while self.peek() == ",":
                    self.take()
                    deps.append(self.identifier())
            self.take("{")
            functions = []
            variables = {}
            while self.peek() != "}":
                declared = self.datatype()
                name = self.identifier()
                if self.peek() == ";":
                    self.take()
                    variables[name] = declared
                    continue
                params = []
                uses = []
                local_types = {}
                if self.peek() == ":":
                    self.take()
                    while True:
                        if self.peek() in (
                            "Integer",
                            "Char",
                            "Array",
                            "String",
                            "Pointer",
                        ):
                            datatype = self.datatype()
                            param = self.identifier()
                            params.append(param)
                            local_types[param] = datatype
                        else:
                            uses.append(self.identifier())
                        if self.peek() != ",":
                            break
                        self.take()
                body = self.block(local_types)
                functions.append((name, params, uses, local_types, body))
            self.take("}")
            package = self.identifier()
            self.take(";")
            self.order.append(package)
            self.dependencies[package] = set(deps)
            for name, datatype in variables.items():
                self.globals[package, name] = datatype
            for name, params, uses, local_types, body in functions:
                if (package, name) in self.functions:
                    raise ValueError("duplicate function")
                self.functions[package, name] = {
                    "params": params,
                    "uses": uses,
                    "locals": local_types,
                    "body": body,
                }
        if not self.order:
            raise ValueError("empty program")

    def identifier(self):
        value = self.take()
        if not (value[0].isalpha() or value[0] == "_"):
            raise ValueError("expected identifier")
        return value

    def number(self):
        value = self.take()
        if any(char not in "0123456789" for char in value):
            raise ValueError("expected number")
        return int(value)

    def datatype(self):
        name = self.take()
        if name == "Pointer":
            self.take("(")
            value = self.datatype()
            self.take(")")
            return value
        if name == "Array":
            self.take("(")
            inner = self.datatype()
            self.take(",")
            length = self.number()
            self.take(")")
            return (*inner[:4], length)
        if name not in ("Integer", "Char", "String"):
            raise ValueError("unknown type")
        if name == "Integer" and self.peek() == "(":
            self.take()
            values = [self.number()]
            for _ in range(3):
                self.take(",")
                values.append(self.number())
            self.take(")")
            if values[0] > values[1]:
                raise ValueError("reversed bounds")
            return (*values, None)
        return (0, 255, 255, 0, 0 if name == "String" else None)

    def block(self, local_types):
        self.take("{")
        body = []
        while self.peek() != "}":
            word = self.peek()
            if word in ("Integer", "Char", "Array", "String", "Pointer"):
                value = self.datatype()
                name = self.identifier()
                self.take(";")
                local_types[name] = value
            elif word in ("INIT", "INCR", "DECR"):
                self.take()
                target = self.identifier()
                index = None
                if self.peek() == "(":
                    self.take()
                    index = self.chain()
                    self.take(")")
                self.take(";")
                body.append([word.lower(), target, index])
            elif word in ("If", "While"):
                self.take()
                expression = self.chain()
                self.take("Then" if word == "If" else "Do")
                body.append([word.lower(), expression, self.block(local_types)])
            else:
                expression = self.chain()
                self.take(";")
                if expression[0] == "apply" and expression[1] in ("charPut", "charGet"):
                    arguments = expression[2]
                    if len(arguments) != 1:
                        raise ValueError("IO arity")
                    argument = arguments[0]
                    if expression[1] == "charPut":
                        body.append(["print", argument])
                        continue
                    if argument[0] == "variable":
                        body.append(["read", argument[1], None])
                    elif argument[0] == "apply" and len(argument[2]) == 1:
                        body.append(["read", argument[1], argument[2][0]])
                    else:
                        raise ValueError("invalid input target")
                else:
                    body.append(["val", expression])
        self.take("}")
        return body


def lower(body):
    result = []

    def append(statements):
        for node in statements:
            opcode = node[0]
            if opcode in ("if", "while"):
                top = len(result)
                result.append(["jz", native_tree(node[1]), None])
                append(node[2])
                if opcode == "while":
                    result.append(["jmp", top])
                result[top][2] = len(result)
            elif opcode in ("init", "incr", "decr", "read"):
                result.append(
                    [opcode, node[1], None if node[2] is None else native_tree(node[2])]
                )
            else:
                result.append([opcode, native_tree(node[1])])

    append(body)
    return tuple(tuple(statement) for statement in result)
