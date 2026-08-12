// %^2^-1 interpreter (C++ cross-check; see README "Extra Implementations").
//
// A single accumulator with six operations: `s`/`i` subtract 2/3, `m` doubles
// it, `p` negates it, `'` resets it to zero, `l`/`e` print it (decimal / as
// byte), `n` reads one byte of input, and `t` rewinds to the start of the
// program when the accumulator is nonzero.  The accumulator is reset to zero
// whenever it exceeds 3003.
//
// Deviation from the wiki: the wiki's spec is "simplen't" (divide by 100 /
// 1000, square, reciprocate, set to 1), but this implementation follows the
// Deadfish-style variant the repository's generator targets: `s`/`i`/`m`/`p`
// subtract/double/negate and `'` zeroes.  The accumulator resets to zero when
// it exceeds 3003 (the wiki resets to one by magnitude; this implementation
// uses a plain greater-than test against the raw value).
//
// Input: the program file is `argv[1]`; `n` reads from stdin.  A missing or
// unreadable file exits with EXIT_FAILURE (a malformed program).

#include <fstream>
#include <iostream>

int main(int argc, char *argv[]) {
  std::ifstream file;
  bool out = false;
  int acc = 0;
  char c;

  if (argc > 1) {
    file = std::ifstream(argv[1]);
    if (!file.is_open())
      return EXIT_FAILURE;
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
      out = true;
      break;
    case 'e':
      std::cout << (char)acc;
      out = true;
      break;
    case 'n':
      if (out)
        std::cout << std::endl;
      std::cout << "Input: ";
      out = false;

      acc = getchar();
      while ((c = getchar()) != '\n' && c != EOF)
        ;
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
