# Faculty Schedule Generator

COSC 631 · C program · 56 courses · 25 faculty

## Compile and run

Requires: GCC/Clang, Make, `ar`, and Python 3 (with its built-in `sqlite3` module).

Run these steps from the project root:

1. **Compile** the program and static library:

   ```sh
   make build/scheduler
   ```

2. **Run** using `data/courses.tsv` and `data/faculty.tsv`:

   ```sh
   make run
   ```

3. **View** [output/schedules.md](output/schedules.md). Imported data and generated office hours are also saved to `schedule.db`.

Shortcut: `make` compiles and generates the schedules and database in one command.

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

## SQLite database

The C program reads the two TSV files and calculates office hours.
`scripts/create_database.py` runs it with `SCHEDULE_FORMAT=json`, reads the structured
results, and creates/populates `schedule.db` using Python’s built-in `sqlite3` module.
The script also runs the C Markdown output mode and prints the report; the Makefile
saves it to `output/schedules.md`. C contains no SQL or SQLite dependency.
The scheduler uses in-memory structs; it does not reload data from SQL.

`make run` runs this complete workflow. Running `./build/scheduler` directly only
prints schedules. For custom inputs with database storage:

```sh
python3 scripts/create_database.py courses.tsv faculty.tsv > schedules.md
```

| Table | Stores |
| --- | --- |
| Faculty | Names, departments, offices |
| Availability | Available days/times and weekly requirements |
| Courses | Course codes, titles, faculty references |
| ClassMeetings | Session, days, times, room, source status |
| OfficeHourPlans | Required/assigned minutes and complete, withheld, or insufficient status |
| OfficeHours | Generated blocks linked to each professor/session plan |

Every successful run replaces these tables' data in one transaction. Failed database
writes roll back to the previous data. TSV files remain the source of truth; edits
made directly to these SQL tables are replaced on the next run. Other tables are left alone.
`make clean` preserves the database. Set `SCHEDULE_DB` to use another database path.

With the SQLite command-line tool installed:

```sh
sqlite3 -header -column schedule.db "SELECT * FROM Faculty;"
sqlite3 -header -column schedule.db "SELECT * FROM OfficeHourPlans;"
sqlite3 -header -column schedule.db "SELECT faculty_name, session, day, printf('%02d:%02d', start_minute/60, start_minute%60) AS start_time, printf('%02d:%02d', end_minute/60, end_minute%60) AS end_time FROM OfficeHours;"
```

Sessions are 1 (7R1) and 2 (7R2). Office-hour days are 0 (Monday) through 4 (Friday).
Times are minutes after midnight. Day masks use Monday=1, Tuesday=2, Wednesday=4,
Thursday=8, Friday=16, added together. Asynchronous class days/times are SQL NULL.

JSON export uses vendored [cJSON v1.7.19](https://github.com/DaveGamble/cJSON/tree/v1.7.19)
in `third_party/cJSON/` (MIT license included). Make compiles it into the static
library automatically; no additional installation or network access is needed.
