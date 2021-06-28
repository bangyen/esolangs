#include <stdio.h>

int main(int argc, char* argv[]) {
    FILE *file = fopen(argv[1], "r");
    FILE *output = fopen("output.c", "w");
    int  ind, tabs = 0;
    char *str, ch;

    fputs(
        "#include <stdio.h>\n\nint stk[50]"
        ", ptr;\n\nint main() {\n", output);

    while ((ch = getc(file)) != EOF) {
        char *str = "";
        switch (ch) {
            case '@': str = "stk[ptr] ^= 1;";     break;
            case '.': str = "printf(\"%d\", "
                            "stk[ptr]);";         break;
            case '<': str = "stk[++ptr] = 0;";    break;
            case '>': str = "ptr -= !!ptr;";      break;
            case '[': str = "while (stk[ptr]) {"; break;
            case ']': str = "}"; tabs--;          break;
        }

        for (ind = 0; ind < tabs; ind++)
            fputs("\t", output);
        if (strcmp(str, ""))
            fprintf(output, "\t%s\n", str);

        tabs += ch == '[';
    }

    fputs("\treturn 0;\n}\n", output);
    fclose(output);
    fclose(file);

    return 0;
}
