#include <fstream>
#include <iostream>
#include <vector>

int main(int argc, char *argv[]) {
  if (argc == 1)
    return EXIT_FAILURE;

  std::ifstream file(argv[1]);
  std::vector<bool> tape = {0};
  size_t ptr = 0;
  char c;

  if (!file.is_open())
    return EXIT_FAILURE;

  do {
    while (file.get(c)) {
      if (c == '!') {
        if (++ptr == tape.size())
          tape.push_back(0);
        tape[ptr] = !tape[ptr];
      } else if (c == '?' && !tape[ptr]) {
        file.get(c);

        while (c != '!' && c != '?' && c != '<') {
          if (!file.get(c))
            return EXIT_FAILURE;
        }
      } else if (c == '<' && ptr) {
        ptr--;
      }
    }

    for (bool b : tape)
      std::cout << b;
    std::cout << std::endl;

    file.clear();
    file.seekg(0);
  } while (tape[ptr]);

  file.close();
  return EXIT_SUCCESS;
}
