import sys
import re


def run(code):
    x = code[0].strip()
    y = code[1].strip()
    r = re.compile(
        r'(-_|_-|\\-|/'
        r'_|[^\\/\-_])')

    if x == y and not r.search(x):
        print('Accept.')
    else:
        print('Reject.')


if __name__ == '__main__':
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data)
