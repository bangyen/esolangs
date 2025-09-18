#include <stdio.h>
#include <string.h>

int main(int argc, char *argv[]) {
  FILE *file = fopen(argv[1], "r");
  FILE *output = fopen("output.c", "w");
  char ch;

  if (!file || !output) {
    if (file)
      fclose(file);
    if (output)
      fclose(output);
    fputs("Error: Could not open files\n", stderr);
    return 1;
  }

  fputs("#include <stdio.h>\n#include <string.h>\n\nint"
        " pool[8], cell = 7;\n\nint binary(int* arr)\n{"
        "\n\tint ind, val = 0;\n\n\tfor(ind = 0; ind < "
        "8; ind++)\n\t\tval += (1 << (7 - ind)) * arr[i"
        "nd];\n\n\treturn val;\n}\n\nint main()\n{\n",
        output);

  while ((ch = getc(file)) != EOF) {
    char *str = "";
    switch (ch) {
    case ':':
      str = "memset(pool, 0, 32); cell = 7;";
      break;
    case '^':
      str = "pool[cell] ^= 1;";
      break;
    case '!':
      str = "printf(\"%c\", binary(pool));";
      break;
    case '<':
      str = "cell--;";
      break;
    }

    if (strcmp(str, "")) {
      fputs("\t", output);
      fputs(str, output);
      fputs("\n", output);
    }
  }

  fputs("\treturn 0;\n}\n", output);
  fclose(output);
  fclose(file);

  return 0;
}
