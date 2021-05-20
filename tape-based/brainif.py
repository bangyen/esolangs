import sys


def run(code):
    cells = [0]
    ind = ptr = 0
    inp = False

    while ind < len(code):
        line = code[ind].strip()
        arr = line.split()

        if line and cells[ptr] == int(arr[1]):
            if 'inc' in line:
                cells[ptr] += 1
            elif 'right' in line:
                ptr += 1
                if ptr == len(cells):
                    cells.append(0)
            elif 'left' in line:
                ptr = max(0, ptr - 1)
            elif 'goto' in line:
                ind = int(arr[3]) - 2
            elif 'input' in line:
                s = ''

                while not s:
                    s = input('\n' * inp + 'Input: ')

                cells[ptr] = ord(s[0])
                inp = False
            elif 'output' in line:
                print(chr(cells[ptr]), end='')
                inp = True

        ind += 1


if __name__ == '__main__':
    f = open(sys.argv[1])
    data = f.readlines()
    f.close()

    run(data)
