#include <iostream>
#include <fstream>
#include <string>
#include <ctime>
#include <vector>
#include "common/Tape.h"

void prompt(bool& out) {
    if (out) {
        std::cout << std::endl;
        out = false;
    }
        
    std::cout << "Input: ";
}

char trans(char c, int n) {
    std::vector<std::string> arr = { "pevkjzwr", "yuctsobqihald" };

    for (const auto& s : arr) {
        size_t p = s.find(c);

        if (p != std::string::npos)
            return s[(p + n) % s.size()];
    }

    return c;
}

int main(int argc, char* argv[]) {
    srand((unsigned int) time(nullptr));
    std::ifstream text;

    Tape tape = Tape();
    TapeCell* temp;

    std::string inp, prog;
    std::vector<int> loop;
    int  val,
         ind = 0,
         rep = 1;
    bool line = false;
    char c;

    if (argc > 1) {
        text = std::ifstream(argv[1]);

        if (!text.is_open())
            return EXIT_FAILURE;

        while (text.get(c))
            prog += trans(c, (int) text.tellg() - 1);

        text.close();
    } else {
        return EXIT_FAILURE;
    }

    while (c = prog[ind++]) {
        while (rep > 0) {
            rep--;

            switch (c) {
                case 'p':
                    tape.add(2);
                    break;
                case 's':
                    tape.add(-1);
                    break;
                case 'r':
                    tape.next();
                    tape.next();
                    break;
                case 'l':
                    if (tape.curr->prev != nullptr)
                        tape.prev();
                    break;
                case 'i':
                    prompt(line);
                    std::cin >> inp;
                    tape.set(stoi(inp));
                    break;
                case 'j':
                    prompt(line);
                    tape.set(getchar());
                    while ((c = getchar()) != '\n' && c != EOF);
                    break;
                case 'o':
                    std::cout << tape.value();
                    line = true;
                    break;
                case 'u':
                    std::cout << (char) tape.value();
                    line = true;
                    break;
                case 'a':
                    if (tape.value() != 0) {
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
                    val = tape.value();
                    tape.set(val * val);
                    break;
                case 'z':
                    tape.set(0);
                    break;
                case 'h':
                    val = tape.value();
                    tape.set(val / 2);
                    break;
                case 'w':
                    temp = tape.curr->next;
                    if (temp != nullptr)
                        tape.set(temp->value);
                    else
                        tape.set(0);
                    break;
                case 'q':
                    temp = tape.curr->prev;
                    if (temp != nullptr)
                        tape.set(temp->value);
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
                    if (tape.curr->value != 0)
                        c = prog[ind++];
                    break;
                case 'd':
                    tape.start();
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
