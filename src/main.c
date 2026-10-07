/* C only launches Python; all application behavior lives in scripts/. */
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#ifndef PROJECT_ROOT
#define PROJECT_ROOT "."
#endif
int main(int argc, char **argv) {
    const char *python = getenv("PYTHON");
    if (!python || !*python) python = "python3";
    char **args = calloc((size_t)argc + 2, sizeof *args);
    if (!args) { perror("calloc"); return EXIT_FAILURE; }
    args[0] = (char *)python;
    args[1] = PROJECT_ROOT "/scripts/pipeline.py";
    for (int i = 1; i < argc; ++i) args[i + 1] = argv[i];
    execvp(python, args);
    perror("Unable to launch Python");
    free(args);
    return EXIT_FAILURE;
}
