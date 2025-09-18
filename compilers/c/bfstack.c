#include <stdio.h>
#include <string.h>

int main(int argc, char *argv[]) {
  FILE *file = fopen(argv[1], "r");
  FILE *output = fopen("output.c", "w");
  int loop, brackets = 0;
  char ch;

  if (!file || !output) {
    if (file)
      fclose(file);
    if (output)
      fclose(output);
    fputs("Error: Could not open files\n", stderr);
    return 1;
  }

  fputs("#include <stdio.h>\n\nchar stack[500];\n"
        "int n, line;\n\nvoid input() {\n\tprintf"
        "(\"%sInput: \", line ? \"\\n\" : \"\");"
        "\n\tscanf(\"%s\", &stack[++n]);\n\tline"
        " = 0;\n}\n\nint main() {\n",
        output);

  while ((ch = getc(file)) != EOF) {
    char *str = "";
    switch (ch) {
    case '.':
      str = "printf(\"%c\", "
            "stack[n]); line++;";
      break;
    case ',':
      str = "input();";
      break;
    case '>':
      str = "stack[++n] = 0;";
      break;
    case '<':
      str = "n -= !!n;";
      break;
    case '+':
      str = "stack[n]++;";
      break;
    case '-':
      str = "stack[n] += 255;";
      break;
    case '[':
      str = "while (stack[n]) {";
      break;
    case ']':
      str = "}";
      brackets--;
      break;
    }

    for (loop = 0; loop < brackets; loop++)
      fputs("\t", output);
    if (strcmp(str, "")) {
      fputs("\t", output);
      fputs(str, output);
      fputs("\n", output);
    }

    brackets += ch == '[';
  }

  fputs("\treturn 0;\n}\n", output);
  fclose(file);
  fclose(output);

  return 0;
}
