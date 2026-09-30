#ifndef SCHEDULE_H
#define SCHEDULE_H
#include <stdio.h>
#define MAX_COURSES 512
#define MAX_FACULTY 128
#define TEXT 256
#define MAX_BLOCKS 128

typedef struct {
    char code[TEXT], title[TEXT], lecturer[TEXT], room[TEXT];
    int session, days, start, end, status; /* 0 scheduled, 1 async, 2 review */
} Course;
typedef struct {
    char name[TEXT], department[TEXT], office[TEXT], courses[2048];
    int days, start, end, weekly, block;
} Faculty;
typedef struct { int day, start, end; } Block;
typedef struct {
    Block blocks[MAX_BLOCKS];
    int count, assigned, blocked;
} Plan;
typedef struct {
    Course courses[MAX_COURSES];
    Faculty faculty[MAX_FACULTY];
    int nc, nf;
} Schedule;

int write_json(FILE *out, const Schedule *s);
int load_inputs(Schedule *s, const char *courses, const char *faculty);
int days_mask(const char *text);
int parse_time(const char *text);
int overlaps(int a, int b, int c, int d);
void plan_hours(const Schedule *s, const Faculty *f, int session, Plan *plan);
int write_schedule(FILE *out, const Schedule *s);
#endif
