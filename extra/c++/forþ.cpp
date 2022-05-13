#include <unordered_map>
#include <functional>
#include <iostream>
#include <fstream>
#include <sstream>
#include <vector>
#include <string>

int run(std::string& s,
        std::vector<int>& stack,
        std::unordered_map
            <int, std::string>& table,
        bool& out) {
    auto top = [&stack]() {
        if (stack.size())
            return stack.back();

        exit(EXIT_FAILURE);
    };

    auto push = [&stack](int n) {
        stack.push_back(n);
    };

    auto pop = [&stack, &top]() {
        int n = top();
        stack.pop_back();

        return n;
    };

    auto exec = [&](std::string str) {
        run(str, stack, table, out);
    };

    for (int k = 0; k < s.size(); k++) {
        char c = s[k];

        if (47 < c && c < 58) {
            stack.push_back(c - 48);
        } else if (64 < c && c < 71) {
            stack.push_back(c - 55);
        } else if (c == ':') {
            push(top());
        } else if (c == '~') {
            push(~pop());
        } else if (c == '.') {
            std::cout << (char) pop();
            out = true;
        } else if (c == ',') {
            if (out)
                std::cout << std::endl;

            out = false;
            std::string input;
            std::cout << "Input: ";
            getline(std::cin, input);

            for (char ch : input)
                push(ch);
        } else if (c == ';') {
            std::string str = table[pop()];
            exec(str);
        } else if (c == 'o') {
            for (int n = 0; n < stack.size(); n++) {
                int val = pop();
                auto it = stack.begin();
                stack.insert(it + n, val);
            }
        } else if (c == 'c') {
            if (stack.size() < 3)
                return EXIT_FAILURE;

            push(stack[stack.size() - 3]);
            stack.erase(stack.end() - 3);
        } else if (c == '('
                || c == '['
                || c == '{') {
            char add = c,
                 sub = (c != '(') + c + 1;
            int  start = k,
                 match = 1;

            while (match != 0) {
                c = s[++k];

                if (c == 0)
                    return EXIT_FAILURE;
                else if (c == add)
                    match++;
                else if (c == sub)
                    match--;
            }

            std::string scope
                = s.substr(++start, k - start);

            if (add == '(' && top())
                exec(scope);
            else if (add == '[')
                while (top())
                    exec(scope);
            else
                table[top()] = scope;
        } else {
            if (stack.size() < 2)
                return EXIT_FAILURE;

            int two = pop();
            int one = pop();

            switch (c) {
                case '+':
                    push(one + two);
                    break;
                case '-':
                    push(one - two);
                    break;
                case '*':
                    push(one * two);
                    break;
                case '/':
                    if (two == 0)
                        return EXIT_FAILURE;

                    push(one / two);
                    break;
                case '%':
                    if (two == 0)
                        return EXIT_FAILURE;

                    push(one % two);
                    break;
                case 'v':
                    push(two);
                    push(one);
                    break;
                default:
                    push(one);
                    push(two);
                    break;
            }
        }
    }

    return EXIT_SUCCESS;
}

int main(int argc, char* argv[]) {
    std::unordered_map
        <int, std::string> table;
    std::vector<int> stack;
    std::string prog;
    bool out = false;

    if (argc > 1) {
        std::ifstream file
            = std::ifstream(argv[1]);

        if (!file.is_open())
            return EXIT_FAILURE;

        std::stringstream buffer;
        buffer << file.rdbuf();
        prog = buffer.str();
        file.close();
    } else {
        return EXIT_FAILURE;
    }

    return run(prog, stack, table, out);
}
