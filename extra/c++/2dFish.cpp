// 2dFish interpreter (C++ cross-check; see README "Extra Implementations").
//
// A 2D grid language where a pointer moves in one of four directions set by
// `/`, `\`, `v`, `^` and executes the command on the cell it lands on.  `i`
// increments the accumulator, `d` decrements it, `s` squares it, `o` prints
// it in decimal, `a` prints it as a character (or, inside `(`..`)`, as a
// string), `$` reads a line of input, `%` reads a number, `*` prints the
// collected string, and `@` halts.  `(`..`)` captures the text between them
// as a string.
//
// Spec decisions: the pointer starts at the top-left cell and the first cell
// must set a direction, otherwise the program exits with EXIT_MALFORMED (a
// malformed program, the Python ValueError analog).  Moving off the grid is
// an invalid runtime operation, EXIT_INVALID_OP.  A missing, unreadable, or
// empty program file exits with status 1 (unclassified).  The exit-code
// convention is defined below.
//
// Invocation: `2dFish <program-file>`; program text from `argv[1]`.
// Input: the program file is `argv[1]`; `$`/`%` read from stdin.

#include <fstream>
#include <iostream>
#include <string>
#include <vector>

// Cross-check exit-code convention (see README "Extra Implementations"):
// 0 = success, 2 = malformed program, 3 = invalid runtime operation, 1 =
// unclassified failure.
constexpr int EXIT_MALFORMED = 2;
constexpr int EXIT_INVALID_OP = 3;

void prompt(bool &out) {
  if (out)
    std::cout << std::endl;

  std::cout << "Input: ";
  out = false;
}

char get(std::vector<std::string> &prog, int x, int y) {
  if (y < 0 || x < 0 || y == prog.size() || x == prog[y].size())
    exit(EXIT_INVALID_OP);

  return prog[y][x];
}

void direct(char &c, int &x, int &y, char &dir) {
  if (c == '/' || c == '\\' || c == 'v' || c == '^')
    dir = c;

  switch (dir) {
  case '/':
    x += 1;
    break;
  case '\\':
    x -= 1;
    break;
  case 'v':
    y += 1;
    break;
  case '^':
    y -= 1;
    break;
  }
}

int main(int argc, char *argv[]) {
  std::vector<std::string> prog;
  std::ifstream file;
  std::string str;
  bool mode = false, out = false;
  char dir = 0, c = 0;
  int acc = 0, x = 0, y = 0;

  if (argc > 1) {
    file = std::ifstream(argv[1]);
    std::string line;

    if (!file.is_open())
      return EXIT_FAILURE;

    while (!file.eof()) {
      getline(file, line);
      prog.push_back(line);
    }

    if (prog.size() == 0)
      return EXIT_FAILURE;
  } else {
    return EXIT_FAILURE;
  }

  direct(prog[0][0], x, y, dir);

  if (!dir)
    return EXIT_MALFORMED;

  c = get(prog, x, y);

  while (c != '@') {
    switch (c) {
    case 'i':
      mode = false;
      acc++;
      break;
    case 'd':
      mode = false;
      acc--;
      break;
    case 's':
      mode = false;
      acc *= acc;
      break;
    case 'o':
      std::cout << acc;
      out = true;
      break;
    case 'a':
      if (mode) {
        std::cout << str[0];
        str = str.substr(1);
      } else {
        std::cout << (char)acc;
      }

      out = true;
      break;
    case '$':
      prompt(out);
      getline(std::cin, str);
      break;
    case '%':
      prompt(out);
      mode = false;
      std::cin >> acc;
      break;
    case '(':
      str = "";
      mode = true;

      if (prog[y].substr(x).find(')') != std::string::npos) {
        int temp = x;

        while (prog[y][++x] != ')')
          str += prog[y][x];

        if (dir != '/')
          x = temp;
      } else {
        return EXIT_MALFORMED;
      }

      break;
    case '*':
      std::cout << str;
      str = "";
      out = true;
      break;
    }

    direct(c, x, y, dir);
    c = get(prog, x, y);
  }

  return EXIT_SUCCESS;
}
