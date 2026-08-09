import sys

from esolangs.interpreters.io import IO


class Con:
    def __init__(self, name: str) -> None:
        self.name = name
        self.rules: list[tuple[int, str]] = []

    def add(self, cond: str) -> None:
        n, c = cond.split()
        self.rules.append((int(n), c))

    def update(self, var: dict[str, int]) -> int:
        def val(s: str) -> int:
            if s in var:
                return var[s]
            return int(s)

        res = var[self.name]
        for n, c in self.rules:
            if "<" in c:
                x, y = c.split("<=")
                b = val(x) <= val(y)
            else:
                x, y = c.split(">=")
                b = val(x) >= val(y)

            if b:
                res += n

        return max(res, 0)


def run(code: list[str], io: IO) -> None:
    queue: list[str] = []
    obj: list[Con] = []
    var: dict[str, int] = {}
    new: dict[str, int] = {}

    for raw in code:
        line = raw.strip()
        if ":" in line:
            line = line[:-1]
            if "=" in line:
                x, y = line.split("=")
                var[x] = int(y)
                obj.append(Con(x))
            else:
                var[line] = 0
                obj.append(Con(line))
        elif line:
            obj[-1].add(line)

    if not obj:
        return  # nothing to evaluate: an empty program halts immediately

    while True:
        for o in obj:
            new[o.name] = o.update(var)

        if "PRINT" in var and var["PRINT"] == 0 and bool(new["PRINT"]) and "OUT" in var:
            io.print_char(chr(new["OUT"] % (1 << 7)))
        if "" in var and var[""] == 0 and bool(new[""]):
            while not queue:
                s = io.input_str()
                queue += list(s)

            new["INPUT"] = ord(queue[0])
            queue = queue[1:]
        if "EXIT" in var and var["EXIT"] != new["EXIT"]:
            sys.exit(new["EXIT"])

        var = new.copy()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data, IO())
