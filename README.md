# Faculty Schedule Generator

COSC 631 · C program · 56 courses · 25 faculty

## Compile and run

Requires: GCC/Clang, Make, `ar`. Python 3 for tests and workbook import.

Run these steps from the project root:

1. **Compile** the program and static library:

   ```sh
   make build/scheduler
   ```

2. **Run** using `data/courses.tsv` and `data/faculty.tsv`:

   ```sh
   make run
   ```

3. **View** [output/schedules.md](output/schedules.md).

Shortcut: `make` compiles and generates the schedules in one command.

## Optional commands

```sh
make test      # Run tests
make clean     # Remove generated files
```

Custom inputs (exactly two files):

```sh
./build/scheduler courses.tsv faculty.tsv > schedules.md
```

## Files

```text
├── 📁 data/
│   ├── 📊 courses.tsv          # Classes, instructors, times, rooms
│   └── 📊 faculty.tsv          # Availability and office-hour requirements
├── 🔖 include/schedule.h       # Shared interface
├── 📁 src/                     # Main, input, scheduling, output modules
├── 📦 lib/libschedule.a        # Generated static library
├── 🐍 scripts/import_schedule.py
├── 📁 tests/
├── 📝 output/schedules.md
└── ⚙️ Makefile
```

## Notes

- **Inputs:** local TSV files; no Internet needed. Days: `MTWRF` (`R` = Thursday). Times: 24-hour `HH:MM`.
- **Scheduling:** separate 7R1/7R2 sessions; earliest available blocks; no class overlaps.
- **Sample availability:** weekdays, 9 AM–5 PM; two 60-minute blocks weekly; offices `TBD`. Edit `faculty.tsv` as needed.
- **Source issues:** invalid times and teaching conflicts are flagged; affected office hours are withheld. Instructor name aliases are listed in the import script.
- **Reimport:** `make import` recreates both inputs from the XLSX, **overwriting input edits**.
- **Library:** `ar rcs` archives compiled modules; the linker includes required code in the executable.
- **Makefile:** tracks dependencies, rebuilds changed modules, and generates output.

References: [Static libraries](https://www.gnu.org/software/libtool/manual/html_node/Static-libraries.html) · [GNU Make](https://www.gnu.org/software/make/manual/make.html)
