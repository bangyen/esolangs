import sys


class Con:
    def __init__(self, name):
        self.name = name
        self.rules = []

    def add(self, cond):
        n, c = cond.split()
        self.rules.append((int(n), c))

    def update(self, var):
        def val(s):
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

        res = max(res, 0)

        return res


def run(code):
    queue: list = []
    inp = False
    obj = []
    var = {}
    new = {}

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

    while True:
        for o in obj:
            new[o.name] = o.update(var)

        if "PRINT" in var and var["PRINT"] == 0 and bool(new["PRINT"]) and "OUT" in var:
            print(chr(new["OUT"] % (1 << 7)), end="")
            inp = True
        if "" in var and var[""] == 0 and bool(new[""]):
            while not queue:
                s = input("\n" * inp + "Input: ")
                queue += list(s)

            new["INPUT"] = ord(queue[0])
            queue = queue[1:]
            inp = True
        if "EXIT" in var and var["EXIT"] != new["EXIT"]:
            sys.exit(new["EXIT"])

        var = new.copy()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data)
