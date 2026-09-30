#include "schedule.h"
#include <string.h>
static const char *days[] = {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday"};
static void escaped(FILE *out, const char *s) {
    for (; *s; ++s) {
        if (*s == '<') fputs("&lt;", out);
        else if (*s == '>') fputs("&gt;", out);
        else if (*s == '|') fputs("&#124;", out);
        else if (strchr("\\`*_[]", *s)) { fputc('\\', out); fputc(*s, out); }
        else fputc(*s, out);
    }
}
static void time_text(FILE *out, int t) {
    fprintf(out, "%d:%02d %s", (t/60)%12 ? (t/60)%12 : 12, t%60, t < 720 ? "AM" : "PM");
}
int write_schedule(FILE *out, const Schedule *s) {
    fputs("# Faculty Schedules\n\n"
          "Proposed office hours use sample availability and avoid class times. "
          "7R1 and 7R2 are separate sessions. Office hours support all courses listed in that session.\n", out);
    for (int fidx = 0; fidx < s->nf; ++fidx) {
        const Faculty *f = &s->faculty[fidx];
        fputs("\n## ", out); escaped(out, f->name);
        fputs("\n\nDepartment: ", out); escaped(out, f->department);
        fputs(" · Office: ", out); escaped(out, f->office); fputc('\n', out);
        for (int session = 1; session <= 2; ++session) {
            fprintf(out, "\n### 7R%d\n\n", session);
            int count = 0;
            for (int i = 0; i < s->nc; ++i) {
                const Course *c = &s->courses[i];
                if (c->session != session || strcmp(c->lecturer, f->name)) continue;
                if (!count++) fputs("| Course | Class times | Location |\n| --- | --- | --- |\n", out);
                fputs("| ", out); escaped(out, c->code); fputs(" — ", out); escaped(out, c->title); fputs(" | ", out);
                if (c->status == 1) fputs("Asynchronous", out);
                else {
                    int first = 1;
                    for (int d = 0; d < 5; ++d) if (c->days & (1 << d)) {
                        if (!first) fputs(" & ", out);
                        fputs(days[d], out); first = 0;
                    }
                    fputc(' ', out); time_text(out, c->start); fputs(" – ", out); time_text(out, c->end);
                    if (c->status == 2) fputs(" **REVIEW: invalid source time range**", out);
                }
                fputs(" | ", out); escaped(out, c->room); fputs(" |\n", out);
            }
            if (!count) fputs("No classes this session.\n", out);
            Plan p; plan_hours(s, f, session, &p);
            fputs("\n**Office hours:** ", out);
            if (p.blocked) {
                fputs("**Withheld: resolve invalid class times or overlapping teaching assignments in this session.**\n", out);
                for (int i = 0; i < s->nc; ++i) for (int j = 0; j < i; ++j) {
                    const Course *a = &s->courses[i], *b = &s->courses[j];
                    if (a->session == session && b->session == session && !strcmp(a->lecturer, f->name) &&
                        !strcmp(b->lecturer, f->name) && !a->status && !b->status && (a->days & b->days) &&
                        overlaps(a->start, a->end, b->start, b->end)) {
                        fputs("\nTeaching conflict: ", out); escaped(out, a->code); fputs(" / ", out); escaped(out, b->code); fputc('\n', out);
                    }
                }
                continue;
            }
            if (!p.count) fputs("None available.", out);
            for (int b = 0; b < p.count; ++b) {
                int day = p.blocks[b].day;
                int start = p.blocks[b].start, end = p.blocks[b].end;
                /* Merge adjacent blocks for display without changing the plan. */
                while (b + 1 < p.count && p.blocks[b+1].day == day && p.blocks[b+1].start == end)
                    end = p.blocks[++b].end;
                fprintf(out, "%s ", days[day]);
                time_text(out, start); fputs(" – ", out); time_text(out, end);
                if (b + 1 < p.count) fputs("; ", out);
            }
            fprintf(out, " (%d/%d min weekly)\n", p.assigned, f->weekly);
            if (p.assigned < f->weekly)
                fputs("\n**INSUFFICIENT AVAILABILITY: weekly target unmet.**\n", out);
        }
    }
    return !ferror(out);
}
