#include <fstream>
#include <iostream>
#include <regex>
#include <sstream>

#define name "([_a-zA-Z]\\w*)(?:->(\\d+))?"
typedef std::vector<std::pair<std::string, int>> dict;

void error(std::string msg) {
  std::cout << msg << std::endl;

  exit(EXIT_FAILURE);
}

int index(std::string &key, dict &var) {
  std::regex r("(.+)->(.+)");
  std::smatch m;
  int ind = 0;

  if (std::regex_match(key, m, r)) {
    ind += stoi(m[2]);
    key = m[1];
  }

  for (auto k = var.begin(); k != var.end(); k++)
    if (k->first != key)
      ind += k->second;
    else
      return ind;

  error("Identifier is undefined.");
  return 0;
}

int run(std::smatch pre, std::vector<int> &prog, std::vector<int> &tape,
        size_t ptr) {
  char ver = pre[5].str()[0];
  bool out = false;

  int bot = pre[2] != "" ? stoi(pre[2]) : INT_MIN,
      top = pre[3] != "" ? stoi(pre[3]) : INT_MAX;

  auto val = [&](int n) { return &tape[prog[ptr + n]]; };

  while (ptr < prog.size()) {
    int c = prog[ptr++];
    bool neg = false;

    if (c > -3) {
      int num = prog[ptr + 1];

      if (num < 0) {
        num += 10;

        if (num % 2)
          num = --num / -2;
        else
          num /= 2;
      } else {
        num = tape[num];
      }

      if (c == -2)
        num *= -1;

      int &n = *val(0);
      n += num;
      ptr += 2;

      if (n < bot) {
        if (ver == 'h')
          error("Underflow error.");
        if (ver == 'w')
          n = top;
        else
          n = bot;
      }

      if (n > top) {
        if (ver == 'h')
          error("Overflow error.");
        if (ver == 'w')
          n = bot;
        else
          n = top;
      }
    } else if (c > -5) {
      if (prog[ptr++] == -7) {
        neg = true;
        ptr++;
      }

      size_t end = ptr++;
      int pair = 1;

      while (pair != 0) {
        int val = prog[++end];

        if (val == -8)
          pair++;
        else if (val == -9)
          pair--;
      }

      std::vector<int> sub(prog.begin() + ptr, prog.begin() + end);

      if (c == -3) {
        if (!!*val(-2) ^ neg)
          run(pre, sub, tape, 0);
      } else {
        while (!!*val(-2) ^ neg)
          run(pre, sub, tape, 0);
      }

      ptr = ++end;
    } else if (c == -5) {
      std::cout << (char)*val(0);
      out = true;
      ptr++;
    } else {
      if (out)
        std::cout << std::endl;

      std::cout << "Input: ";
      *val(0) = getchar();
      out = false;
      ptr++;

      while ((c = getchar()) != '\n' && c != EOF)
        ;
    }
  }

  return EXIT_SUCCESS;
}

std::vector<std::string> lexer(std::string prog) {
  std::vector<std::string> tokens;

  while (prog.size()) {
    std::smatch m;
    std::regex reg("(\\s*(" name "|\\d+|[!(){"
                   "};]|[+-]=|->|<-)\\s*)[^]*");

    if (std::regex_match(prog, m, reg))
      tokens.push_back(m[2]);
    else
      error("Invalid token.");

    prog = prog.substr(m.length(1));
  }

  return tokens;
}

/* Prefix notation:
 * += : -1
 * -= : -2
 * if : -3
 * while : -4
 * write : -5
 * read  : -6
 * ! : -7
 * { : -8
 * } : -9
 * Nonnegative numbers are variables.
 * Negative numbers below -9 are constants.
 * Odd means positive, even means negative,
 * e.g.
 *  0 : -10
 *  1 : -11,  2 : -13
 * -1 : -12, -2 : -14
 * etc.
 */
std::vector<int> parser(std::vector<std::string> &prog, dict &var) {
  size_t size = prog.size(), ind = 0;
  std::vector<int> tokens;
  int pair = 0;

  auto out = []() { error("Invalid syntax."); };

  auto match = [](std::string str) {
    std::regex r(name);
    return std::regex_match(str, r);
  };

  auto find = [&](int n) {
    std::string t = prog[ind + n];
    tokens.push_back(index(t, var));
  };

  while (ind < size) {
    std::string s = prog[ind++];

    if ((s == "if" || s == "while") && ind + 4 < size) {
      tokens.push_back(s == "if" ? -3 : -4);

      if ((s = prog[ind]) == "!") {
        tokens.push_back(-7);
        ind++;
      }

      if (prog[ind++] == "(" && match(prog[ind++]) && prog[ind++] == ")" &&
          prog[ind++] == "{") {
        pair++;
        find(-3);
        tokens.push_back(-8);
      } else {
        out();
      }
    } else if ((s == "write" || s == "read") && ind + 2 < size) {
      std::string t = s == "write" ? "<-" : "->";

      if (prog[ind++] == t && match(prog[ind++]) && prog[ind++] == ";") {
        tokens.push_back(s == "write" ? -5 : -6);
        find(-2);
      } else {
        out();
      }
    } else if (match(s) && ind + 2 < size) {
      if (prog[ind][1] != '=' || prog[ind + 2] != ";")
        out();

      tokens.push_back(prog[ind++] == "+=" ? -1 : -2);

      std::string sec = prog[ind];
      find(-2);

      if (!match(sec)) {
        if (!isdigit(sec[0]))
          out();

        int n = 2 * stoi(sec);
        if (n > 0)
          n--;

        tokens.push_back(-n - 10);
      } else {
        find(0);
      }

      ind += 2;
    } else if (s == "}") {
      tokens.push_back(-9);
      pair--;
    } else {
      out();
    }
  }

  if (pair != 0)
    out();

  return tokens;
}

int main(int argc, char *argv[]) {
  std::regex com("\\s*//[^\n]*");
  std::vector<int> ops, tape;
  dict var;

  std::string prog, temp;
  std::smatch pre, m;
  std::ifstream file;
  int lim = -1;

  if (argc > 1) {
    std::regex dir("#basicfuck t="
                   "(\\d+|unbounded)"
                   " r=(\\d*)~(\\d*)"
                   "( o=(wrap|halt|n"
                   "earest))?\\s*");

    std::regex all("#allocate(?: " name ",?)*\\s*");

    std::ifstream file = std::ifstream(argv[1]);

    if (!file.is_open())
      return EXIT_FAILURE;

    getline(file, prog);
    temp = prog;

    if (std::regex_match(temp, pre, dir)) {
      int mode = 0;

      if (pre[2] != "")
        mode++;
      if (pre[3] != "")
        mode++;

      if (mode != 0 && pre[4] == "")
        error("Missing overflow directive.");
      else if (mode != 2 && pre[5] == "wrap")
        error("Invalid overflow directive.");

      if (pre[1] != "unbounded")
        lim = stoi(pre[1]);
    } else {
      error("Missing/Invalid directives.");
    }

    getline(file, prog);
    if (std::regex_match(prog, m, all)) {
      std::regex id("( " name ",?)[^]*");
      prog = prog.substr(9);

      while (std::regex_match(prog, m, id)) {
        int len = (int)m.length(1), off = m[3] != "" ? stoi(m[3]) : 1;

        for (int k = 0; k < off; k++)
          tape.push_back(0);

        if (m[2] == "if" || m[2] == "while" || m[2] == "write" ||
            m[2] == "read")
          error("Invalid identifier.");

        var.push_back(std::make_pair(m[2], off));
        prog = prog.substr(len);
      }
    } else {
      error("Missing/Invalid identifiers.");
    }

    std::stringstream buffer;
    buffer << file.rdbuf();
    prog = buffer.str();
    file.close();
  } else {
    return EXIT_FAILURE;
  }

  prog = std::regex_replace(prog, com, "");
  std::regex add(name "\\s*[+-]=\\s*" name);

  if (std::regex_search(prog, add) && lim != -1)
    lim--;

  if (lim != -1 && lim < tape.size())
    error("Insufficient memory.");

  std::vector<std::string> words = lexer(prog);
  ops = parser(words, var);

  return run(pre, ops, tape, 0);
}
