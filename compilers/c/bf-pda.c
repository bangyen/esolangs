#include <stdio.h>

char* str = "", ch;
int tabs, ind;

int main(int argc, char* argv[])
{
    FILE* file = fopen(argv[1], "r");
    FILE* output = fopen("output.c", "w");

    fputs
    (
        "#include <stdio.h>\n\nint stack[500"
        "], point;\n\nint main() {\n", output
    );

    while ((ch = getc(file)) != EOF)
    {
        str = "";
        switch (ch)
        {
            case '@':
                str = "stack[point] = point && !stack[point];";
                break;
            case '.':
                str = "printf(\"\%d\", stack[point]);";
                break;
            case '<':
                str = "stack[++point] = 0;";
                break;
            case '>':
                str = "point -= !!point;";
                break;
            case '[':
                str = "while (stack[point]) {";
                break;
            case ']':
                str = "}"; tabs--;
                break;
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
