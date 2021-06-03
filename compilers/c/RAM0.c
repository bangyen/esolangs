#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int   max, loop, ind;
char  jump[5] = {'G'};
char* string, ch;

char* digits(FILE *symbols) {
    char* num = "";
    char* temp;

    while (1) {
        int len = 0;
        char sym = getc(symbols);
        if (isdigit(sym)) {
            if (len) {
                temp = calloc(len + 1, 1);
                sprintf(temp, "%s%c", num, sym);
                num = temp;
            } else {
                num = calloc(1, 1);
                num[0] = sym;
            }
            len++;
        } else {
            if (len) {
                temp = calloc(len + 11, 1);
                sprintf(temp, "ind = %s - 1;", num);
                num = temp;
            } else if (sym == ' ')
                continue;
            fseek(symbols, -1, SEEK_CUR);
            break;
        }
    }

    return num;
}

int main(int argc, char *argv[]) {
    FILE *file = fopen(argv[1], "r");
    FILE *output = fopen("output.c", "w");

    while ((ch = getc(file)) != EOF) {
        loop += (ch == 'G') || (ch == 'C');
        max += ch == 'A';
    }

    rewind(file);
    fprintf(
        output,
        "#include <stdio.h>\n\nint z, n, %send;\n"
        "int ram[%d];\n\nint main()\n{\n",
        loop ? "ind, " : "", max + 1
    );
    if (loop)
        fputs(
            "\twhile (!end)\n\t{\n\t\tind++;\n"
            "\t\tswitch (ind)\n\t\t{\n", output
        );
    
    while ((ch = getc(file)) != EOF) {
        ind++; string = "";
        switch (ch) {
            case 'Z':  string = "z = 0;"; break;
            case 'A':  string = "z++;"; break;
            case 'N':  string = "n = z;"; break;
            case 'C':  string = "ind += z == 0;"; break;
            case 'L':  string = "z = ram[z];"; break;
            case 'S':  string = "ram[n] = z;"; break;
            case 'G':
                jump[1] = getc(file);
                jump[2] = getc(file);
                jump[3] = getc(file);
                if (!strcmp(jump, "GOTO"))
                    string = digits(file);
                else fseek(file, -3, SEEK_CUR);
                break;
        }
        
        if (strcmp(string, "")) {
            if (loop) {
                fprintf(output, "\t\t\tcase %d: ", ind);
                fprintf(output, "%s break;\n", string);
            } else
                fprintf(output, "\t%s\n", string);
        } else ind--;
    }
    string =
        "\t\t\tdefault: end = 1;"
        " break;\n\t\t}\n\t}\n";
    fprintf(
        output, "%s\treturn 0;\n}",
        loop ? string : ""
    );
    
    fclose(file);
    fclose(output);

    return 0;
}
