CC = cc
CFLAGS = -std=c11 -O2 -Wall -Wextra -Wpedantic
PYTHON = python3
COURSES = data/courses.tsv
FACULTY = data/faculty.tsv
ARGS =

.PHONY: all run test clean import
all: run

build:
	mkdir -p $@

build/scheduler: src/main.c Makefile | build
	$(CC) $(CFLAGS) -DPROJECT_ROOT='"$(CURDIR)"' $< -o $@

run: build/scheduler
	PYTHON="$(PYTHON)" ./build/scheduler "$(COURSES)" "$(FACULTY)" $(ARGS)

import:
	$(PYTHON) scripts/import_schedule.py "CTEC Fall 2026 Schedule - Share (2) (1).xlsx"

test: build/scheduler
	PYTHON="$(PYTHON)" $(PYTHON) -m unittest discover -s tests -v

clean:
	rm -rf build
	rm -f output/schedules.md
