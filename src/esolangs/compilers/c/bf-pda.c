#include <stdio.h>
#include <string.h>

int main(int argc, char *argv[]) {
  FILE *file = fopen(argv[1], "r");
  FILE *output = fopen("output.c", "w");
  int ind, tabs = 0;
  char *str, ch;

  if (!file || !output) {
    if (file)
      fclose(file);
    if (output)
      fclose(output);
    fputs("Error: Could not open files\n", stderr);
    return 1;
  }

  fputs("#include <stdio.h>\n\nint stk[50]"
        ", ptr;\n\nint main() {\n",
        output);

  while ((ch = getc(file)) != EOF) {
    char *str = "";
    switch (ch) {
    case '@':
      str = "stk[ptr] ^= 1;";
      break;
    case '.':
      str = "printf(\"%d\", "
            "stk[ptr]);";
      break;
    case '<':
      str = "stk[++ptr] = 0;";
      break;
    case '>':
      str = "ptr -= !!ptr;";
      break;
    case '[':
      str = "while (stk[ptr]) {";
      break;
    case ']':
      str = "}";
      tabs--;
      break;
    }

    for (ind = 0; ind < tabs; ind++)
      fputs("\t", output);
    if (strcmp(str, "")) {
      fputs("\t", output);
      fputs(str, output);
      fputs("\n", output);
    }

    tabs += ch == '[';
  }

  fputs("\treturn 0;\n}\n", output);
  fclose(output);
  fclose(file);

  return 0;
}
