#include <fstream>
#include <iostream>
#include <math.h>
#include <sstream>
#include <string>

bool prime(int n) {
  if (n < 2)
    return false;

  for (int k = 2; k < sqrt(n) + 1; k++)
    if (n % k == 0)
      return false;

  return true;
}

int main(int argc, char *argv[]) {
  std::string prog;
  int val, num = 0;

  if (argc > 1) {
    std::ifstream file = std::ifstream(argv[1]);
    char c;

    if (!file.is_open())
      return EXIT_FAILURE;

    while (file.get(c))
      if (c == 't')
        num++;
      else if (isdigit(c))
        break;

    if (file.eof())
      return EXIT_FAILURE;

    file.seekg(-1, file.cur);
    std::stringstream buffer;
    buffer << file.rdbuf();

    prog = buffer.str();
    val = stoi(prog);
    file.close();
  } else {
    return EXIT_FAILURE;
  }

  if (num) {
    if (prime(val)) {
      for (int k = 0; k < num; k++)
        while (!prime(++val))
          ;

      std::cout << val << std::endl;
    } else {
      std::cout << 0 << std::endl;
    }
  }

  return EXIT_SUCCESS;
}
