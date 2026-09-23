#include "schedule.h"
#include <string.h>

int overlaps(int a, int b, int c, int d) { return a < d && c < b; }
static int belongs(const Course *c, const Faculty *f, int session) {
    return c->session == session && !strcmp(c->lecturer, f->name);
}
void plan_hours(const Schedule *s, const Faculty *f, int session, Plan *p) {
    memset(p, 0, sizeof *p);
    /* Uncertain times or existing teaching conflicts make this session unsafe. */
    for (int i = 0; i < s->nc; ++i) {
        const Course *c = &s->courses[i];
        if (!belongs(c, f, session)) continue;
        if (c->status == 2) p->blocked = 1;
        for (int j = 0; j < i; ++j) {
            const Course *d = &s->courses[j];
            if (belongs(d, f, session) && !c->status && !d->status && (c->days & d->days) &&
                overlaps(c->start, c->end, d->start, d->end)) p->blocked = 1;
        }
    }
    if (p->blocked) return;
    /* Earliest-fit, Monday through Friday; one full block at a time. */
    for (int day = 0; day < 5 && p->assigned < f->weekly; ++day) {
        if (!(f->days & (1 << day))) continue;
        for (int t = f->start; t+f->block <= f->end && p->assigned < f->weekly;) {
            int free_slot = 1;
            for (int i = 0; i < s->nc; ++i) {
                const Course *c = &s->courses[i];
                if (belongs(c, f, session) && !c->status && (c->days & (1 << day)) &&
                    overlaps(t, t+f->block, c->start, c->end)) free_slot = 0;
            }
            if (free_slot) {
                p->blocks[p->count++] = (Block){day, t, t+f->block};
                p->assigned += f->block;
                t += f->block;
            } else ++t;
        }
    }
}
