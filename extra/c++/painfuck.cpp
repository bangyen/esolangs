// Painfuck interpreter (C++ cross-check; see README "Extra Implementations").
//
// A brainfuck-like tape language whose source is first translated through a
// fixed substitution (the `trans` table maps each source character to a
// program character).  `p`/`s` add 2/subtract 1, `r`/`l` move the pointer,
// `i`/`j` read a number/byte, `o`/`u` print decimal/byte, `a`/`b` open/close
// a loop, `k` squares, `z` zeroes, `h` halves, `w`/`q` copy from the
// neighbor, `c` repeats the next command 7^r times, `y` conditionally skips
// one command at random, `v` skips one command on a nonzero cell, `d` resets
// the pointer, `t` repeats the previous command 3^r times, and `e` halts.
//
// `y` is intentionally nondeterministic (a random skip), so a single run's
// output is not reproducible; the generators avoid it.
//
// Invocation: `painfuck <program-file>`; program text from `argv[1]`.
// Input: the program file is `argv[1]`; `i`/`j` read from stdin.

#include <cstdlib>
#include <ctime>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>

constexpr int EXIT_INVALID_OP = 3;

void prompt(bool &out) {
  if (out) {
    std::cout << std::endl;
    out = false;
  }

  std::cout << "Input: ";
}

char trans(char c, int &n) {
  std::vector<std::string> arr = {"pevkjzwr", "yuctsobqihald"};

  for (auto s : arr) {
    size_t p = s.find(c);

    if (p != std::string::npos)
      return s[(p + n++) % s.size()];
  }

  return 0;
}

int main(int argc, char *argv[]) {
  srand((unsigned int)time(nullptr));
  std::ifstream text;

  std::vector<int> loop, tape = {0};
  std::string inp, prog;
  int val, ptr = 0, ind = 0, rep = 1;
  bool line = false;
  char c;

  if (argc > 1) {
    text = std::ifstream(argv[1]);
    int n = 0;

    if (!text.is_open())
      return EXIT_FAILURE;

    while (text.get(c))
      if ((c = trans(c, n)))
        prog += c;

    text.close();
  } else {
    return EXIT_FAILURE;
  }

  while ((c = prog[ind++])) {
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
        if (ptr)
          ptr--;
        break;
      case 'i':
        prompt(line);
        if (!(std::cin >> inp))
          std::exit(EXIT_INVALID_OP);

        tape[ptr] = stoi(inp);
        break;
      case 'j': {
        prompt(line);
        int ch = getchar();
        if (ch == EOF)
          std::exit(EXIT_INVALID_OP);

        tape[ptr] = ch;
        while ((c = getchar()) != '\n' && c != EOF)
          ;
        break;
      }
      case 'o':
        std::cout << tape[ptr];
        line = true;
        break;
      case 'u':
        std::cout << (char)tape[ptr];
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
        if (loop.empty()) {
          std::cerr << "unmatched b" << std::endl;
          std::exit(EXIT_INVALID_OP);
        }

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
        if (arc4random() % 2)
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
      case 't': {
        val = ind;
        rep = 1;

        // walk back over the run of 't's; at the start of the program the
        // byte before it reads as NUL (a command that matches no case),
        // matching the Python interpreter
        while (ind > 0 && prog[ind - 1] == 't') {
          ind--;
          rep *= 3;
        }

        c = (ind > 0) ? prog[ind - 1] : 0;
        ind = val;
        break;
      }
      }
    }

    rep++;
  }

  return EXIT_SUCCESS;
}
