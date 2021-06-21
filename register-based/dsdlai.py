import random
import sys
import dig


def rand():
    num = random.randint(20, 90)

    def chance():
        n = random.randint(1, 100)
        if n <= num:
            print('\nYou died.')
        return n <= num
    return chance


if __name__ == '__main__':
    f = open(sys.argv[1])
    data = f.readlines()
    f.close()

    dig.run(data, rand())
