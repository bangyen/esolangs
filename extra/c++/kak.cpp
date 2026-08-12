// Kak interpreter (C++ cross-check; see README "Extra Implementations").
//
// A one-bit-tape language: `!` advances the pointer and flips the current
// bit, `<` moves the pointer left, and `?` skips forward past the next
// non-`!`/`?`/`<` command when the current bit is zero.  After the program is
// read once, the whole tape is printed as a bit string, and execution
// restarts from the beginning while the current bit is nonzero.
//
// Error handling: a missing/unreadable program file, or a `?` that runs off
// the end of the program while skipping, exits with EXIT_FAILURE.
//
// Invocation: `kak <program-file>`; program text from `argv[1]`.
// Input: the program file is `argv[1]`; the language has no input command.

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
