"""Independent activations at the repository's statement/row boundaries."""

from dataclasses import dataclass, field

from tests.interpreters.forbin_reference import (
    Function,
    Reference,
    ReturnedError,
    Scope,
)


@dataclass
class Activation:
    scope: Scope
    index: int = 0
    rows: list | None = None
    names: list = field(default_factory=list)
    next_row: int = 0
    body: list = field(default_factory=list)
    body_index: int = 0


class SteppedReference(Reference):
    def __init__(self, source, stdin=""):
        super().__init__(source, stdin)
        main = self.functions["main"]
        self.activations = [self.activation(main, [0], self.global_scope)]
        self.length = len(source)

    def activation(self, function, arguments, parent):
        values = dict.fromkeys(function.parameters, 0)
        values.update(zip(function.parameters, arguments, strict=False))
        return Activation(Scope(function, parent, values))

    @property
    def halted(self):
        return not self.activations

    def perform(self, node, activation):
        scope = activation.scope
        if node[0] == "invoke":
            function = self.value(node[1], scope)
            arguments = [self.value(value, scope) for value in node[2]]
            if isinstance(function, Function):
                return (self.activation(function, arguments, scope), False)
            self.call(function, arguments, scope)
            return (None, False)
        try:
            self.execute([node], scope)
        except ReturnedError:
            return (None, True)
        return (None, False)

    def step(self):
        if self.halted:
            return
        active = self.activations[-1]
        statements = active.scope.function.statements
        if active.rows is not None:
            if active.body_index < len(active.body):
                node = active.body[active.body_index]
                child, returned = self.perform(node, active)
                active.body_index += 1
                if returned:
                    self.activations.pop()
                elif child:
                    self.activations.append(child)
            elif active.next_row < len(active.rows):
                row = active.rows[active.next_row]
                active.next_row += 1
                active.scope.values.update(
                    (
                        (name, value)
                        for name, value in zip(active.names, row, strict=False)
                        if name != "_"
                    )
                )
                active.body = statements[active.index][2]
                active.body_index = 0
            else:
                active.rows = None
                active.index += 1
            return
        if active.index == len(statements):
            self.activations.pop()
            return
        node = statements[active.index]
        if node[0] == "loop":
            active.names, active.rows = self.rows_for(node[1], active.scope)
            active.next_row = 0
            return
        child, returned = self.perform(node, active)
        active.index += 1
        if returned:
            self.activations.pop()
        elif child:
            self.activations.append(child)

    def rows_for(self, header, scope):
        return super().rows(header, scope)

    def unread_bits(self):
        return [self.byte >> 7 - index & 1 for index in range(self.bit_index, 8)]
