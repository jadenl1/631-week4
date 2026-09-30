#include "schedule.h"
#include <stdlib.h>
#include <string.h>
int main(int argc, char **argv) {
    if (argc != 3) {
        fprintf(stderr, "Usage: %s courses.tsv faculty.tsv\n", argv[0]);
        return EXIT_FAILURE;
    }
    Schedule *s = calloc(1, sizeof *s);
    if (!s) { perror("allocation"); return EXIT_FAILURE; }
    int ok = load_inputs(s, argv[1], argv[2]);
    const char *format = getenv("SCHEDULE_FORMAT");
    if (ok) ok = (format && !strcmp(format, "json") ?
                  write_json(stdout, s) : write_schedule(stdout, s)) && fflush(stdout) == 0;
    free(s);
    return ok ? EXIT_SUCCESS : EXIT_FAILURE;
}
