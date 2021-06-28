#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void skip(FILE *file, char c) {
    fseek(file, -2, SEEK_CUR);
    char ch = fgetc(file);

    if (ch == 'C') {
        fseek(file, 2, SEEK_CUR);
    } else {
        while ((ch = fgetc(file)) == c) {}
        if (!feof(file))
            fseek(file, -1, SEEK_CUR);
    }
}

int main(int argc, char *argv[]) {
    FILE *file   = fopen(argv[1], "r");
    FILE *output = fopen("output.c", "w");

    int  max = 0, ind = 0, num = 0;
    char jump[5] = {'G'};
    char *str, ch;

    while ((ch = getc(file)) != EOF) {
        num |= ch == 'G' || ch == 'C';
        max += ch == 'A';
    }

    rewind(file);
    fprintf(
        output,
        "#include <stdio.h>\n\nint z, n%s;"
        "\nint ram[%d];\n\nint main()\n{\n",
        num ? ", ind" : "", max);
    if (num)
        fputs(
            "\twhile (++ind)\n\t{\n\t\t"
            "switch (ind)\n\t\t{\n", output);

    while ((ch = getc(file)) != EOF) {
        str = ""; ind++;
        switch (ch) {
            case 'A': str = "z++;";           break;
            case 'L': str = "z = ram[z];";    break;
            case 'C': str = "ind += z == 0;"; break;
            case 'Z': str = "z = 0;";
                      skip(file, ch); break;
            case 'N': str = "n = z;";
                      skip(file, ch); break;
            case 'S': str = "ram[n] = z;";
                      skip(file, ch); break;
            case 'G':
                for (max = 1; max < 4; max++)
                    jump[max] = getc(file);
                if (!strcmp(jump, "GOTO")) {
                    int val;

                    fscanf(file, "%d", &val);
                    int len = snprintf(
                        NULL, 0, "%d", val);
                    str = malloc(len + 12);
                    snprintf(
                        str, len + 12,
                        "ind = %i - 1;", val);
                } else {
                    fseek(file, -3, SEEK_CUR);
                }
                break;
        }

        if (strcmp(str, "")) {
            if (num)
                fprintf(
                    output, "\t\t\tcase %d: "
                    "%s break;\n", ind, str);
            else
                fprintf(output, "\t%s\n", str);
        } else {
            ind--;
        }
    }

    str = "\t\t\tdefault: ind = -1;"
          " break;\n\t\t}\n\t}\n";
    fprintf(
        output, "%s\n\tprintf(\"Z: %s\\nN:"
        " %s\\n\", z, n);\n\treturn 0;\n}",
        num ? str : "", "%d", "%d");

    fclose(file);
    fclose(output);

    return 0;
}
