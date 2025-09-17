#include <iostream>
#include <fstream>
#include <string>
#include <vector>
#include <ctime>

void prompt(bool& out) {
    if (out) {
        std::cout << std::endl;
        out = false;
    }

    std::cout << "Input: ";
}

char trans(char c, int& n) {
    std::vector<std::string> arr = { "pevkjzwr", "yuctsobqihald" };

    for (auto s : arr) {
        size_t p = s.find(c);

        if (p != std::string::npos)
            return s[(p + n++) % s.size()];
    }

    return 0;
}

int main(int argc, char* argv[]) {
    srand((unsigned int) time(nullptr));
    std::ifstream text;

    std::vector<int> loop, tape = {0};
    std::string inp, prog;
    int  val,
         ptr = 0,
         ind = 0,
         rep = 1;
    bool line = false;
    char c;

    if (argc > 1) {
        text = std::ifstream(argv[1]);
        int n = 0;

        if (!text.is_open())
            return EXIT_FAILURE;

        while (text.get(c))
            if (c = trans(c, n))
                prog += c;

        text.close();
    } else {
        return EXIT_FAILURE;
    }

    while (c = prog[ind++]) {
        while (rep > 0) {
            rep--;

            switch (c) {
                case 'p':
                    tape[ptr] += 2;
                    break;
                case 's':
                    tape[ptr] -= 1;
                    break;
                case 'r':
                    ptr += 2;

                    while (ptr >= tape.size())
                        tape.push_back(0);

                    break;
                case 'l':
                    if (ptr) ptr--;
                    break;
                case 'i':
                    prompt(line);
                    std::cin >> inp;
                    tape[ptr] = stoi(inp);
                    break;
                case 'j':
                    prompt(line);
                    tape[ptr] = getchar();
                    while ((c = getchar()) != '\n'
                           && c != EOF);
                    break;
                case 'o':
                    std::cout << tape[ptr];
                    line = true;
                    break;
                case 'u':
                    std::cout << (char) tape[ptr];
                    line = true;
                    break;
                case 'a':
                    if (tape[ptr] != 0) {
                        loop.push_back(ind - 1);
                    } else {
                        val = 1;
                        while (val != 0) {
                            if (!(c = prog[ind++]))
                                break;

                            if (c == 'a')
                                val++;
                            else if (c == 'b')
                                val--;
                        }
                    }

                    break;
                case 'b':
                    ind = loop.back();
                    loop.pop_back();
                    break;
                case 'k':
                    val = tape[ptr];
                    tape[ptr] = val * val;
                    break;
                case 'z':
                    tape[ptr] = 0;
                    break;
                case 'h':
                    tape[ptr] /= 2;
                    break;
                case 'w':
                    if (ptr + 1 != tape.size())
                        tape[ptr] = tape[ptr + 1];
                    else
                        tape[ptr] = 0;
                    break;
                case 'q':
                    if (ptr)
                        tape[ptr] = tape[ptr - 1];
                    break;
                case 'c':
                    rep = 1;

                    while (c == 'c') {
                        c = prog[ind++];
                        rep *= 7;
                    }

                    break;
                case 'y':
                    if (rand() % 2)
                        c = prog[ind++];
                    break;
                case 'e':
                    return EXIT_SUCCESS;
                case 'v':
                    if (tape[ptr] != 0)
                        c = prog[ind++];
                    break;
                case 'd':
                    ptr = 0;
                    break;
                case 't':
                    val = ind;
                    rep = 1;

                    while (prog[--ind] == 't')
                        rep *= 3;

                    c = prog[ind];
                    ind = val;
                    break;
            }
        }

        rep++;
    }

    return EXIT_SUCCESS;
}
