#include <stdio.h>
#include <string.h>

int loop, brackets;
char *string, ch;

int main(int argc, char *argv[]) {
    FILE* file = fopen(argv[1], "r");
    FILE* output = fopen("output.c", "w");

    fprintf(
        output,
        "#include <stdio.h>\n\nchar stack[500];\n"
        "int n, line;\n\nvoid input() {\n\tprintf"
        "(\"%sInput: \", line ? \"\\n\" : \"\");"
        "\n\tscanf(\"%s\", &stack[++n]);\n\tline"
        " = 0;\n}\n\nint main() {\n", "%s", "%s");

    while ((ch = getc(file)) != EOF) {
        switch (ch) {
            case '.':  string = "printf(\"%c\","
                                " stack[n]); line++;";    break;
            case ',':  string = "input();";               break;
            case '>':  string = "stack[++n] = 0;";        break;
            case '<':  string = "n = n > 1 ? n - 1 : 0;"; break;
            case '+':  string = "stack[n]++;";            break;
            case '-':  string = "stack[n] += 255;";       break;
            case '[':  string = "while (stack[n]) {";     break;
            case ']':  string = "}"; brackets--;          break;
        }

        for (loop = 0; loop < brackets; loop++)
            fputs("\t", output);
        if (strcmp(string, ""))
            fprintf(output, "\t%s\n", string);

        brackets += ch == '[';
        string = "";
    }

    fputs("\treturn 0;\n}\n", output);
    fclose(file); fclose(output);

    return 0;
}
