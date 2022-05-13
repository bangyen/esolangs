#include <unordered_map>
#include <algorithm>
#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

int parse(std::string prog, int ind) {
    std::string sub = prog.substr(ind);
    return stoi(sub);
}

int index(
        std::string prog,
        int ind,
        char start,
        char end) {
    int match = 1;
    char c;

    while (match != 0) {
        if (!(c = prog[ind++]))
            break;

        if (c == start)
            match++;
        else if (c == end)
            match--;
    }

    return ind;
}

int* move(
        std::vector<int>& ptr,
        std::vector<int>& prime,
        int dim) {
    while (dim + 1 > ptr.size()) {
        int n = prime.back() + 1;

        while (true) {
            bool p = std::all_of(
                prime.begin(),
                prime.end(),
                [n](int k) {return n % k;}
            );

            if (p) break;
            n++;
        }

        prime.push_back(n);
        ptr.push_back(0);
    }

    return &ptr[dim];
}

char* value(
        std::vector<int>& ptr,
        std::vector<int>& prime,
        std::unordered_map<int, char>& tape) {
    int num = 1;

    for (int k = 0; k < ptr.size(); k++)
        num *= (int) pow(prime[k], ptr[k]);

    if (tape.find(num) == tape.end())
        tape[num] = 0;

    return &tape[num];
}

int main(int argc, char* argv[]) {
    std::unordered_map<int, char> tape;
    std::vector<int> ptr, prime = {2};
    std::vector<int> loop, dloop;
    std::string prog;

    bool out = false;
    int dim, ind = 0;
    char c;
    
    auto val = [&]() {
        return value(ptr, prime, tape);
    };

    auto mov = [&]() {
        return move(ptr, prime, dim);
    };

    if (argc > 1) {
        std::ifstream file =
            std::ifstream(argv[1]);

        if (!file.is_open())
            return EXIT_FAILURE;

        std::stringstream buffer;
        buffer << file.rdbuf();
        prog = buffer.str();
        file.close();
    } else {
        return EXIT_FAILURE;
    }

    while (ind < prog.size()) {
        c = prog[ind++];

        switch (c) {
            case '>':
            case '<':
                if (isdigit(prog[ind]))
                    dim = parse(prog, ind);
                else
                    dim = *val();

                *mov() += c == '>' ? 1 : -1;
                break;
            case '+':
                *val() += 1;
                break;
            case '-':
                *val() -= 1;
                break;
            case ':':
                *val() = prog[ind++];
                break;
            case '=':
                *val() = stoi(
                    prog.substr(ind),
                    nullptr, 16
                );

                break;
            case '.':
                std::cout << *val();
                out = true;
                break;
            case ',':
                if (out)
                    std::cout << std::endl;

                std::cout << "Input: ";
                out = false;

                *val() = getchar();
                while ((c = getchar()) != '\n'
                       && c != EOF);
                break;
            case '[':
                if (*val() != 0)
                    loop.push_back(ind - 1);
                else
                    ind = index(prog, ind, '[', ']');

                break;
            case ']':
                ind = loop.back();
                loop.pop_back();
                break;
            case '{':
                dim = parse(prog, ind);

                if (*mov() != 0)
                    dloop.push_back(ind - 1);
                else
                    ind = index(prog, ind, '{', '}');

                break;
            case '}':
                ind = dloop.back();
                dloop.pop_back();
                break;
            case '?':
                dim = parse(prog, ind);
                *val() = *mov() % 256;
                break;
            case '!':
                dim = parse(prog, ind);
                *mov() = 0;
                break;
            case '*':
                while (prog[ind++] != '*');
                break;
        }
    }

    return EXIT_SUCCESS;
}
