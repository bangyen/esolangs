#include <stdio.h>

char* str = "", ch;

int main(int argc, char* argv[])
{
    FILE* file = fopen(argv[1], "r");
    FILE* output = fopen("output.c", "w");

    fputs
    (
        "#include <stdio.h>\n#include <string.h>\n\nint"
        " pool[8], cell = 7;\n\nint binary(int* arr)\n{"
        "\n\tint ind, val = 0;\n\n\tfor(ind = 0; ind < "
        "8; ind++)\n\t\tval += (1 << (7 - ind)) * arr[i"
        "nd];\n\n\treturn val;\n}\n\nint main()\n{\n",
        output
    );

    while ((ch = getc(file)) != EOF)
    {
        switch (ch)
        {
        case ':': str = "memset(pool, 0, 32); cell = 7;"; break;
        case '^': str = "pool[cell] ^= 1;";               break;
        case '!': str = "printf(\"\%c\", binary(pool));"; break;
        case '<': str = "cell--;";                        break;
        }
        
        if (strcmp(str, ""))
            fprintf(output, "\t%s\n", str);
        str = "";
    }
    fputs("\treturn 0;\n}\n", output);

    fclose(output);
    fclose(file);

    return 0;
}
