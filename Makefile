CC = cc
AR = ar
CFLAGS = -std=c11 -O2 -Wall -Wextra -Wpedantic
CPPFLAGS = -Iinclude -Ithird_party/cJSON
PYTHON = python3
COURSES = data/courses.tsv
FACULTY = data/faculty.tsv
LIBOBJ = build/input.o build/scheduler.o build/output.o build/json.o build/cJSON.o

.PHONY: all run test clean import
.DELETE_ON_ERROR:
all: run

build lib output:
	mkdir -p $@

build/%.o: src/%.c include/schedule.h | build
	$(CC) $(CPPFLAGS) $(CFLAGS) -MMD -MP -c $< -o $@

build/cJSON.o: third_party/cJSON/cJSON.c third_party/cJSON/cJSON.h | build
	$(CC) $(CPPFLAGS) $(CFLAGS) -MMD -MP -c $< -o $@

build/json.o: third_party/cJSON/cJSON.h

lib/libschedule.a: $(LIBOBJ) Makefile | lib
	$(AR) rcs $@.tmp $(LIBOBJ)
	mv $@.tmp $@

build/scheduler: build/main.o lib/libschedule.a
	$(CC) $(CFLAGS) build/main.o lib/libschedule.a -o $@

output/schedules.md: build/scheduler $(COURSES) $(FACULTY) scripts/create_database.py | output
	$(PYTHON) scripts/create_database.py $(COURSES) $(FACULTY) > $@.tmp
	mv $@.tmp $@

run: build/scheduler | output
	$(PYTHON) scripts/create_database.py $(COURSES) $(FACULTY) > output/schedules.md.tmp
	mv output/schedules.md.tmp output/schedules.md

import:
	$(PYTHON) scripts/import_schedule.py "CTEC Fall 2026 Schedule - Share (2) (1).xlsx"

test: build/scheduler
	$(CC) $(CPPFLAGS) $(CFLAGS) tests/test_scheduler.c lib/libschedule.a -o build/test_scheduler
	./build/test_scheduler
	$(PYTHON) tests/test_cli.py

clean:
	rm -rf build lib/libschedule.a output/schedules.md output/schedules.md.tmp

-include $(LIBOBJ:.o=.d) build/main.d
