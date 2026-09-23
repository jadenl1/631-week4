#include "schedule.h"
#include <stdlib.h>
#include <string.h>

int parse_time(const char *s) {
    if (strlen(s) != 5 || s[2] != ':' || s[0] < '0' || s[0] > '2' ||
        s[1] < '0' || s[1] > '9' || s[3] < '0' || s[3] > '5' || s[4] < '0' || s[4] > '9') return -1;
    int h = (s[0]-'0')*10+s[1]-'0';
    return h < 24 ? h*60+(s[3]-'0')*10+s[4]-'0' : -1;
}
int days_mask(const char *s) {
    const char *codes = "MTWRF";
    int mask = 0;
    if (!*s) return -1;
    for (; *s; ++s) {
        const char *p = strchr(codes, *s);
        if (!p || (mask & (1 << (p-codes)))) return -1;
        mask |= 1 << (p-codes);
    }
    return mask;
}
static int number(const char *s) {
    char *end;
    long n = strtol(s, &end, 10);
    return *s && !*end && n > 0 && n <= 7200 ? (int)n : -1;
}
/* TSV deliberately excludes embedded tabs/newlines and quoted fields. */
static int fields(char *line, char **v, int n) {
    line[strcspn(line, "\r\n")] = '\0';
    v[0] = line;
    int count = 1;
    for (char *p = line; *p; ++p) if (*p == '\t') {
        *p = '\0';
        if (count == n) return 0;
        v[count++] = p+1;
    }
    if (count != n) return 0;
    for (int i = 0; i < n; ++i) if (!*v[i] || strlen(v[i]) >= (i == 8 ? 2048 : TEXT)) return 0;
    return 1;
}
static int has_course(const char *list, const char *code) {
    size_t len = strlen(code);
    for (const char *p = list; *p;) {
        const char *end = strchr(p, ';');
        size_t n = end ? (size_t)(end-p) : strlen(p);
        if (n == len && !strncmp(p, code, n)) return 1;
        if (!end) break;
        p = end+1;
    }
    return 0;
}
static int load(Schedule *s, const char *path, int faculty) {
    FILE *in = fopen(path, "r");
    if (!in) { perror(path); return 0; }
    char line[8192], *v[9];
    int row = 1, ok = 1;
    const char *header = faculty ?
        "lecturer\tdepartment\toffice\tdays\tavailable_start\tavailable_end\tweekly_minutes\tblock_minutes\tcourses" :
        "course\ttitle\tlecturer\tsession\tdays\tstart\tend\troom\tstatus";
    if (!fgets(line, sizeof line, in)) ok = 0;
    else { line[strcspn(line, "\r\n")] = 0; ok = !strcmp(line, header); }
    while (ok && fgets(line, sizeof line, in)) {
        ++row;
        if (!strchr(line, '\n') && !feof(in)) { ok = 0; break; }
        if (!fields(line, v, 9)) { ok = 0; break; }
        if (faculty) {
            if (s->nf == MAX_FACULTY) { ok = 0; break; }
            Faculty *f = &s->faculty[s->nf++];
            strcpy(f->name, v[0]); strcpy(f->department, v[1]); strcpy(f->office, v[2]); strcpy(f->courses, v[8]);
            f->days = days_mask(v[3]); f->start = parse_time(v[4]); f->end = parse_time(v[5]);
            f->weekly = number(v[6]); f->block = number(v[7]);
            ok = f->days > 0 && f->start >= 0 && f->end > f->start &&
                 f->weekly > 0 && f->block > 0 && f->weekly % f->block == 0 && f->weekly/f->block <= MAX_BLOCKS;
            for (int i = 0; i < s->nf-1; ++i) if (!strcmp(f->name, s->faculty[i].name)) ok = 0;
        } else {
            if (s->nc == MAX_COURSES || strlen(v[8]) >= TEXT) { ok = 0; break; }
            Course *c = &s->courses[s->nc++];
            strcpy(c->code, v[0]); strcpy(c->title, v[1]); strcpy(c->lecturer, v[2]); strcpy(c->room, v[7]);
            c->session = !strcmp(v[3], "7R1") ? 1 : !strcmp(v[3], "7R2") ? 2 : 0;
            c->status = !strcmp(v[8], "scheduled") ? 0 : !strcmp(v[8], "async") ? 1 : !strcmp(v[8], "review") ? 2 : -1;
            c->days = days_mask(v[4]); c->start = parse_time(v[5]); c->end = parse_time(v[6]);
            ok = c->session && c->status >= 0;
            if (c->status == 1) ok = ok && !strcmp(v[4], "-") && !strcmp(v[5], "-") && !strcmp(v[6], "-");
            else ok = ok && c->days > 0 && c->start >= 0 && c->end >= 0 && (c->status == 2 || c->end > c->start);
            for (int i = 0; i < s->nc-1; ++i) if (!strcmp(c->code, s->courses[i].code)) ok = 0;
        }
    }
    if (ferror(in)) ok = 0;
    fclose(in);
    if (!ok) fprintf(stderr, "%s:%d: invalid header, row, duplicate, or capacity exceeded\n", path, row);
    return ok;
}
int load_inputs(Schedule *s, const char *courses, const char *faculty) {
    memset(s, 0, sizeof *s);
    if (!load(s, courses, 0) || !load(s, faculty, 1) || !s->nc || !s->nf) return 0;
    for (int i = 0; i < s->nc; ++i) {
        Course *c = &s->courses[i];
        int found = 0;
        for (int j = 0; j < s->nf; ++j)
            if (!strcmp(c->lecturer, s->faculty[j].name) && has_course(s->faculty[j].courses, c->code)) found = 1;
        if (!found) { fprintf(stderr, "%s: lecturer/course missing from faculty file\n", c->code); return 0; }
    }
    for (int i = 0; i < s->nf; ++i) {
        char copy[2048]; strcpy(copy, s->faculty[i].courses);
        for (char *code = strtok(copy, ";"); code; code = strtok(NULL, ";")) {
            int found = 0;
            for (int j = 0; j < s->nc; ++j)
                if (!strcmp(code, s->courses[j].code) && !strcmp(s->faculty[i].name, s->courses[j].lecturer)) found = 1;
            if (!found) { fprintf(stderr, "%s: unknown assigned course %s\n", s->faculty[i].name, code); return 0; }
        }
    }
    return 1;
}
