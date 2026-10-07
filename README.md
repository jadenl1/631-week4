# Faculty Schedules & Syllabus Office Hours

Python parses course data and syllabi, writes reports, and saves SQLite data. C only launches Python; Make compiles and runs the launcher. Office hours are **extracted from syllabi, never scheduled automatically**.

## Build → run → view

Requires a C compiler, Make, and Python 3.10+.

```sh
make build/scheduler
python3 -m pip install -r requirements.txt
make run
```

View [output/schedules.md](output/schedules.md). Without syllabi, it lists professors, courses, class times, and locations, with office hours marked unavailable.

## Supply a syllabus

Add your OpenAI API key to `.env` in the project root:

```dotenv
OPENAI_API_KEY=your-api-key
OPENAI_MODEL=gpt-4.1-mini
```

Python loads this file automatically. `.env` is ignored by Git; existing terminal environment variables take precedence. Then supply a file:

```sh
make run ARGS='--syllabus "path/to/syllabus.docx"'
```

- Supports `.txt`, `.md`, `.docx`, and text-based `.pdf` files.
- For PDF support: `python3 -m pip install -r requirements.txt` (use a virtual environment if required).
- Scanned PDFs need OCR first. No local models are required.
- Syllabus text is sent to the OpenAI Responses API. Defaults to `gpt-4.1-mini`; override with `--model` or `OPENAI_MODEL`.
- Missing/ambiguous fields remain unknown. Quotes are checked against the source; all extracted hours require review.
- Each syllabus remains separate, preserving appointment instructions and conflicting versions. Faculty matches require equivalent full names; new professors get their own section.

Multiple files or a folder:

```sh
./build/scheduler --syllabus "first.pdf" --syllabus "second.docx"
./build/scheduler --syllabi-dir "path/to/syllabi"
```

Folder input reads supported files directly inside that folder. Extractions are kept in `schedule.db`; supplying the same syllabus path updates its stored extraction. Running without syllabi rebuilds the report from stored results.

## Outputs

| File | Contents |
| --- | --- |
| `output/schedules.md` | Faculty/course tables and syllabus excerpts |
| `schedule.db` | Faculty, Courses, ClassMeetings, Syllabi, OfficeHours |

Python creates both outputs. Extraction details are stored in SQLite; the report displays office hours under each professor. Database updates are transactional. The old generated office-hour plans and sample availability tables are removed on the first run; unrelated tables are preserved. SQLite stores source excerpts, not computed time slots.

## Optional commands

```sh
make test       # Offline tests with mocked OpenAI responses
make clean      # Remove build/report files; preserve inputs and database
make import     # Recreate both TSV files from the original XLSX (overwrites edits)
./build/scheduler --help
```

Custom inputs/output paths:

```sh
./build/scheduler courses.tsv faculty.tsv --syllabus syllabus.txt \
  --output report.md --database schedule.db
```

## Files

```text
├── 📁 data/                    # Faculty and course TSV inputs
├── 📁 scripts/
│   ├── 🐍 inputs.py            # Faculty/course validation
│   ├── 🐍 syllabus.py          # Document reading + OpenAI extraction
│   ├── 🐍 pipeline.py          # Report and database creation
│   ├── 🐍 import_schedule.py   # XLSX → TSV
│   └── 🐍 create_database.py   # Compatibility entry point to pipeline
├── 📄 src/main.c               # Python launcher only
├── 📁 tests/
├── 📁 output/
└── ⚙️ Makefile
```

API reference: [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses).
