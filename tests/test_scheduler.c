#include "schedule.h"
#include <assert.h>
#include <stdlib.h>
#include <string.h>

int main(void) {
    assert(parse_time("00:00") == 0 && parse_time("23:59") == 1439);
    assert(parse_time("24:00") == -1 && parse_time("09:60") == -1);
    assert(days_mask("MTWRF") == 31 && days_mask("MM") == -1 && days_mask("X") == -1);
    assert(!overlaps(540, 600, 600, 660));
    Schedule *s = calloc(1, sizeof *s); assert(s);
    Faculty f = {.name="Professor", .days=3, .start=540, .end=720, .weekly=120, .block=60};
    s->courses[0] = (Course){.lecturer="Professor", .session=1, .days=1, .start=540, .end=630}; s->nc=1;
    Plan p; plan_hours(s, &f, 1, &p);
    assert(p.count == 2 && p.assigned == 120 && !p.blocked);
    assert(p.blocks[0].day == 0 && p.blocks[0].start == 630);
    assert(p.blocks[1].day == 1 && p.blocks[1].start == 540);
    f.days=1; plan_hours(s, &f, 1, &p); assert(p.assigned == 60);
    plan_hours(s, &f, 2, &p); assert(p.assigned == 120); /* session isolation */
    s->courses[0].status=2; plan_hours(s, &f, 1, &p); assert(p.blocked && !p.count);
    s->courses[0].status=1; plan_hours(s, &f, 1, &p); assert(!p.blocked && p.assigned == 120);
    s->courses[0].status=0; s->courses[1]=s->courses[0]; s->nc=2;
    plan_hours(s, &f, 1, &p); assert(p.blocked && !p.count);
    assert(load_inputs(s, "data/courses.tsv", "data/faculty.tsv"));
    assert(s->nc == 56 && s->nf == 25);
    int blocked=0;
    for (int i=0; i<s->nf; ++i) for (int session=1; session<=2; ++session) {
        Faculty *faculty=&s->faculty[i]; plan_hours(s, faculty, session, &p);
        if (p.blocked) { ++blocked; assert(!p.count); continue; }
        assert(p.assigned == faculty->weekly);
        for (int j=0; j<p.count; ++j) {
            Block b=p.blocks[j];
            assert((faculty->days & (1 << b.day)) && b.start >= faculty->start && b.end <= faculty->end);
            assert(b.end-b.start == faculty->block);
            for (int k=0; k<j; ++k)
                assert(b.day != p.blocks[k].day || !overlaps(b.start,b.end,p.blocks[k].start,p.blocks[k].end));
            for (int k=0; k<s->nc; ++k) {
                Course *c=&s->courses[k];
                if (c->session == session && !c->status && !strcmp(c->lecturer,faculty->name) && (c->days & (1 << b.day)))
                    assert(!overlaps(b.start,b.end,c->start,c->end));
            }
        }
    }
    assert(blocked == 3);
    free(s); puts("Scheduler tests passed (including all supplied faculty/session plans).");
    return 0;
}
