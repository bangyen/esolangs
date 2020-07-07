import sys

if __name__ == '__main__':
    with open(sys.argv[1]) as file:
        code = file.readlines()

    commands = {
        '\\': 1
    }

    extra = 0
    period = False
    bracket = False

    for line in code:
        if extra:
            extra -= 1
            continue
        if bracket:
            if line[0] == '|':
                ...
            else:
                ...
        if period:
            if line[0] == '_':
                ...
            else:
                ...
