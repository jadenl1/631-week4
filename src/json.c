#include "schedule.h"
#include "cJSON.h"
#include <stdarg.h>

/* Add a table row: s = string, i = integer, n = SQL-style null. */
static int add_row(cJSON *table, const char *types, ...) {
    cJSON *row = cJSON_CreateArray();
    if (!row) return 0;
    va_list args;
    va_start(args, types);
    for (const char *t = types; *t; ++t) {
        cJSON *value = *t == 's' ? cJSON_CreateString(va_arg(args, const char *)) :
                       *t == 'i' ? cJSON_CreateNumber(va_arg(args, int)) : cJSON_CreateNull();
        if (!value || !cJSON_AddItemToArray(row, value)) {
            cJSON_Delete(value);
            cJSON_Delete(row);
            va_end(args);
            return 0;
        }
    }
    va_end(args);
    if (cJSON_AddItemToArray(table, row)) return 1;
    cJSON_Delete(row);
    return 0;
}

/* Python owns SQL/database operations; C exports the calculated results. */
int write_json(FILE *out, const Schedule *s) {
    cJSON *root = cJSON_CreateObject();
    if (!root) return 0;
    cJSON *faculty = cJSON_AddArrayToObject(root, "Faculty");
    cJSON *availability = cJSON_AddArrayToObject(root, "Availability");
    cJSON *courses = cJSON_AddArrayToObject(root, "Courses");
    cJSON *meetings = cJSON_AddArrayToObject(root, "ClassMeetings");
    cJSON *plans = cJSON_AddArrayToObject(root, "OfficeHourPlans");
    cJSON *hours = cJSON_AddArrayToObject(root, "OfficeHours");
    if (!faculty || !availability || !courses || !meetings || !plans || !hours) goto fail;
    for (int i = 0; i < s->nf; ++i) {
        const Faculty *f = &s->faculty[i];
        if (!add_row(faculty, "sss", f->name, f->department, f->office) ||
            !add_row(availability, "siiiii", f->name, f->days, f->start, f->end, f->weekly, f->block)) goto fail;
        for (int session = 1; session <= 2; ++session) {
            Plan p;
            plan_hours(s, f, session, &p);
            const char *status = p.blocked ? "withheld" : p.assigned < f->weekly ? "insufficient" : "complete";
            if (!add_row(plans, "siiis", f->name, session, p.assigned, f->weekly, status)) goto fail;
            for (int j = 0; j < p.count; ++j) {
                Block b = p.blocks[j];
                if (!add_row(hours, "siiii", f->name, session, b.day, b.start, b.end)) goto fail;
            }
        }
    }
    for (int i = 0; i < s->nc; ++i) {
        const Course *c = &s->courses[i];
        if (!add_row(courses, "sss", c->code, c->title, c->lecturer)) goto fail;
        if (c->status == 1) {
            if (!add_row(meetings, "sinnnss", c->code, c->session, c->room, "async")) goto fail;
        } else if (!add_row(meetings, "siiiiss", c->code, c->session, c->days, c->start, c->end,
                            c->room, c->status == 2 ? "review" : "scheduled")) goto fail;
    }
    char *json = cJSON_PrintUnformatted(root);
    if (!json) goto fail;
    int ok = fputs(json, out) != EOF && fputc('\n', out) != EOF;
    cJSON_free(json);
    cJSON_Delete(root);
    return ok;
fail:
    fputs("Unable to allocate JSON output\n", stderr);
    cJSON_Delete(root);
    return 0;
}
