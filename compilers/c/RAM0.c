#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void skip(FILE *file, char c) {
  if (fseek(file, -2, SEEK_CUR) != 0)
    return;
  int ch = fgetc(file);

  if (ch == 'C') {
    fseek(file, 2, SEEK_CUR);
  } else if (ch != EOF) {
    while (!feof(file) && (ch = fgetc(file)) == c && ch != EOF) {
    }
    if (!feof(file) && ch != EOF)
      fseek(file, -1, SEEK_CUR);
  }
}

int main(int argc, char *argv[]) {
  FILE *file = fopen(argv[1], "r");
  FILE *output = fopen("output.c", "w");

  if (!file || !output) {
    if (file)
      fclose(file);
    if (output)
      fclose(output);
    fputs("Error: Could not open files\n", stderr);
    return 1;
  }

  int max = 0, ind = 0, num = 0;
  char *str, ch;

  while (!feof(file) && !ferror(file) && (ch = getc(file)) != EOF) {
    if (ch == 'C' || isdigit(ch))
      num = 1;
    if (ch == 'A')
      max++;
  }

  if (fseek(file, 0, SEEK_SET) != 0) {
    fclose(file);
    fclose(output);
    fputs("Error: fseek failed\n", stderr);
    return 1;
  }
  fputs("#include <stdio.h>\n\nint z, n", output);
  if (num)
    fputs(", ind", output);
  fputs(";\nint ram[", output);
  char max_str[32];
  snprintf(max_str, sizeof(max_str), "%d", max);
  fputs(max_str, output);
  fputs("];\n\nint main()\n{\n", output);
  if (num)
    fputs("\twhile (++ind)\n\t{\n\t\t"
          "switch (ind)\n\t\t{\n",
          output);

  if (ferror(file)) {
    fclose(file);
    fclose(output);
    fputs("Error: file error occurred\n", stderr);
    return 1;
  }

  while (!feof(file) && !ferror(file) && (ch = getc(file)) != EOF) {
    str = "";
    ind++;
    switch (ch) {
    case 'A':
      str = "z++;";
      break;
    case 'L':
      str = "z = ram[z];";
      break;
    case 'C':
      str = "ind += z == 0;";
      break;
    case 'Z':
      str = "z = 0;";
      skip(file, ch);
      if (ferror(file)) {
        fclose(file);
        fclose(output);
        fputs("Error: file error after skip\n", stderr);
        return 1;
      }
      break;
    case 'N':
      str = "n = z;";
      skip(file, ch);
      if (ferror(file)) {
        fclose(file);
        fclose(output);
        fputs("Error: file error after skip\n", stderr);
        return 1;
      }
      break;
    case 'S':
      str = "ram[n] = z;";
      skip(file, ch);
      if (ferror(file)) {
        fclose(file);
        fclose(output);
        fputs("Error: file error after skip\n", stderr);
        return 1;
      }
      break;
    default:
      if (isdigit(ch)) {
        int val = 0;

        fseek(file, -1, SEEK_CUR);
        char num_str[32];
        int i = 0;
        int c;
        while ((c = fgetc(file)) != EOF && isdigit(c) && i < 31) {
          num_str[i++] = c;
        }
        if (i > 0) {
          num_str[i] = '\0';
          val = atoi(num_str);
        } else {
          val = 0;
        }
        if (c != EOF) {
          fseek(file, -1, SEEK_CUR);
        }

        int len = snprintf(NULL, 0, "%d", val);
        str = malloc(len + 12);
        snprintf(str, len + 12, "ind = %i - 1;", val);
      }
      break;
    }

    if (strcmp(str, "")) {
      if (num) {
        fputs("\t\t\tcase ", output);
        char ind_str[32];
        snprintf(ind_str, sizeof(ind_str), "%d", ind);
        fputs(ind_str, output);
        fputs(": ", output);
        fputs(str, output);
        fputs(" break;\n", output);
      } else {
        fputs("\t", output);
        fputs(str, output);
        fputs("\n", output);
      }
    } else {
      ind--;
    }
  }

  str = "\t\t\tdefault: ind = -1;"
        " break;\n\t\t}\n\t}\n";
  if (num)
    fputs(str, output);
  fputs("\n\tprintf(\"Z: %d\\nN: %d\\n\", z, n);\n\treturn 0;\n}", output);

  fclose(file);
  fclose(output);

  return 0;
}
