#include <iostream>
#include <fstream>

int main(int argc, char* argv[]) {
    std::ifstream file;
    int acc = 0;
    char c;

    if (argc > 1) {
        file = std::ifstream(argv[1]);
        if (!file.is_open()) {
            return EXIT_FAILURE;
        }
    } else {
        return EXIT_FAILURE;
    }

    while (file.get(c)) {
        if (acc > 3003)
            acc = 0;

        switch (c) {
            case 's':
                acc -= 2;
                break;
            case 'i':
                acc -= 3;
                break;
            case 'm':
                acc *= 2;
                break;
            case 'p':
                acc *= -1;
                break;
            case 'l':
                std::cout << acc;
                break;
            case 'e':
                std::cout << (char) acc;
                break;
            case 'n':
                acc = getchar();
                break;
            case '\'':
                acc = 0;
                break;
            case 't':
                if (acc != 0) {
                    file.clear();
                    file.seekg(0);
                }
                break;
        }
    }

    file.close();
    return EXIT_SUCCESS;
}
