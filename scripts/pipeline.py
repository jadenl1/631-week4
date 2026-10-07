#!/usr/bin/env python3
"""Build faculty reports and extract stated office hours from supplied syllabi."""
import argparse
from contextlib import closing
import html
import json
import os
from pathlib import Path
import re
import shlex
import sqlite3
import sys
import tempfile

from inputs import DAYS, load_inputs, minutes
from syllabus import collect_paths, name_key, parse_syllabus

ROOT = Path(__file__).resolve().parents[1]


def load_env(path):
    """Load simple KEY=value settings without executing shell expressions."""
    if not path.exists():
        return
    settings = {}
    for number, line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('export '):
            line = line[7:].lstrip()
        key, separator, value = line.partition('=')
        key = key.strip()
        if not separator or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', key):
            raise ValueError(f'{path.name} line {number}: expected KEY=value')
        try:
            parts = shlex.split(value, comments=True)
        except ValueError:
            raise ValueError(f'{path.name} line {number}: invalid quoting') from None
        if len(parts) > 1:
            raise ValueError(f'{path.name} line {number}: quote values containing spaces')
        settings[key] = parts[0] if parts else ''
    for key, value in settings.items():
        os.environ.setdefault(key, value)


def escape(value):
    value = html.escape(str(value), quote=False).replace('|', '&#124;')
    return re.sub(r'([\\`*_\[\]#])', r'\\\1', value).replace('\n', '<br>')


def clock(value):
    total = minutes(value)
    hour, minute = divmod(total, 60)
    return f'{hour % 12 or 12}:{minute:02} {"AM" if hour < 12 else "PM"}'


def report(courses, faculty, syllabi):
    lines = ['# Faculty Schedules']
    for person in faculty:
        name = person['lecturer']
        lines += ['', f'## {escape(name)}', '',
                  f'Department: {escape(person["department"])} · Office: {escape(person["office"])}']
        hours = list(dict.fromkeys(h['value'] for item in syllabi
                                   if item['matched_faculty'] == name
                                   for h in item['office_hours']))
        lines += ['', '**Office hours:** ' + ('; '.join(escape(h) for h in hours) or 'Not provided.')]
        if not any(c['lecturer'] == name for c in courses):
            codes = list(dict.fromkeys(c['value'] for item in syllabi
                                      if item['matched_faculty'] == name for c in item['courses']))
            if codes:
                lines += ['', 'Courses: ' + ', '.join(escape(code) for code in codes)]
            continue
        for session in ('7R1', '7R2'):
            rows = [c for c in courses if c['lecturer'] == name and c['session'] == session]
            lines += ['', f'### {session}', '']
            if rows:
                lines += ['| Course | Class times | Location |', '| --- | --- | --- |']
            else:
                lines.append('No classes this session.')
            for course in rows:
                times = 'Asynchronous'
                if course['status'] != 'async':
                    times = ' & '.join(DAYS[d] for d in course['days']) + f' {clock(course["start"])} – {clock(course["end"])}'
                    if course['status'] == 'review':
                        times += ' **REVIEW: source time range**'
                lines.append(f'| {escape(course["course"])} — {escape(course["title"])} | {times} | {escape(course["room"])} |')
            for i, a in enumerate(rows):
                for b in rows[:i]:
                    if (a['status'] == b['status'] == 'scheduled' and set(a['days']) & set(b['days'])
                            and minutes(a['start']) < minutes(b['end']) and minutes(b['start']) < minutes(a['end'])):
                        lines += ['', f'Teaching conflict: {escape(a["course"])} / {escape(b["course"])}']
    return '\n'.join(lines).rstrip() + '\n'


def load_syllabi(path):
    if not path.exists():
        return []
    with closing(sqlite3.connect(path)) as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='Syllabi'").fetchone():
            return []
        return [json.loads(row[0]) for row in db.execute('SELECT extraction_json FROM Syllabi ORDER BY source')]


def add_syllabus_faculty(faculty, syllabi):
    """Link known names and add named instructors missing from the TSV roster."""
    faculty = [dict(person) for person in faculty]
    for item in syllabi:
        if not item['instructor']:
            item['matched_faculty'] = None
            continue
        name = item['instructor']['value']
        matches = [f['lecturer'] for f in faculty if name_key(f['lecturer']) == name_key(name)]
        if not matches:
            faculty.append({'lecturer': name, 'department': 'Not provided', 'office': 'Not provided'})
            matches = [name]
        item['matched_faculty'] = matches[0] if len(matches) == 1 else None
    return faculty


def save_database(path, courses, faculty, syllabi):
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as db:
        db.execute('PRAGMA foreign_keys=ON')
        with db:
            db.execute('BEGIN IMMEDIATE')
            # Replace only project-owned tables, including the obsolete generated plans.
            for table in ('OfficeHours', 'OfficeHourPlans', 'Availability', 'Syllabi', 'ClassMeetings', 'Courses', 'Faculty'):
                db.execute(f'DROP TABLE IF EXISTS {table}')
            db.execute('CREATE TABLE Faculty (name TEXT PRIMARY KEY, department TEXT NOT NULL, office TEXT NOT NULL)')
            db.execute('CREATE TABLE Courses (code TEXT PRIMARY KEY, title TEXT NOT NULL, faculty_name TEXT REFERENCES Faculty(name))')
            db.execute('CREATE TABLE ClassMeetings (course_code TEXT PRIMARY KEY REFERENCES Courses(code), session TEXT, days TEXT, start_time TEXT, end_time TEXT, room TEXT, status TEXT)')
            db.execute('CREATE TABLE Syllabi (source TEXT PRIMARY KEY, faculty_name TEXT REFERENCES Faculty(name), instructor TEXT, method TEXT, status TEXT, extraction_json TEXT NOT NULL)')
            db.execute('CREATE TABLE OfficeHours (id INTEGER PRIMARY KEY, source TEXT REFERENCES Syllabi(source), excerpt TEXT NOT NULL, evidence TEXT NOT NULL)')
            db.executemany('INSERT INTO Faculty VALUES (?,?,?)', [(f['lecturer'], f['department'], f['office']) for f in faculty])
            for c in courses:
                db.execute('INSERT INTO Courses VALUES (?,?,?)', (c['course'], c['title'], c['lecturer']))
                times = (None, None, None) if c['status'] == 'async' else (c['days'], c['start'], c['end'])
                db.execute('INSERT INTO ClassMeetings VALUES (?,?,?,?,?,?,?)', (c['course'], c['session'], *times, c['room'], c['status']))
            for item in syllabi:
                db.execute('INSERT INTO Syllabi VALUES (?,?,?,?,?,?)', (item['source'], item['matched_faculty'],
                           item['instructor']['value'] if item['instructor'] else None,
                           item['method'], item['status'], json.dumps(item, ensure_ascii=False)))
                db.executemany('INSERT INTO OfficeHours (source, excerpt, evidence) VALUES (?,?,?)',
                               [(item['source'], h['value'], h['evidence']) for h in item['office_hours']])


def stage_file(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(content)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    return temporary


def main(argv=None):
    try:
        load_env(ROOT / '.env')
    except (OSError, ValueError) as error:
        print(f'Configuration failed: {error}', file=sys.stderr)
        return 1
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('courses', type=Path, nargs='?', default=ROOT / 'data/courses.tsv')
    parser.add_argument('faculty', type=Path, nargs='?', default=ROOT / 'data/faculty.tsv')
    parser.add_argument('--syllabus', type=Path, action='append', default=[], help='PDF, DOCX, TXT, or MD file; repeat for multiple files')
    parser.add_argument('--syllabi-dir', type=Path, help='Read supported files directly inside this directory')
    parser.add_argument('--model', default=os.environ.get('OPENAI_MODEL', 'gpt-4.1-mini'),
                        help='OpenAI model (default: OPENAI_MODEL or gpt-4.1-mini)')
    parser.add_argument('--output', type=Path, default=ROOT / 'output/schedules.md')
    parser.add_argument('--database', type=Path, default=Path(os.environ.get('SCHEDULE_DB', str(ROOT / 'schedule.db'))))
    args = parser.parse_args(argv)
    staged = []
    try:
        paths = collect_paths(args.syllabus, args.syllabi_dir)
        destinations = [p.resolve() for p in (args.output, args.database)]
        sources = {args.courses.resolve(), args.faculty.resolve(), *paths}
        if len(set(destinations)) != 2 or sources.intersection(destinations):
            raise ValueError('Output/database paths must be distinct and must not overwrite input files')
        courses, faculty = load_inputs(args.courses, args.faculty)
        stored = {item['source']: item for item in load_syllabi(args.database)}
        for path in paths:
            stored[str(path)] = parse_syllabus(path, faculty, args.model)
        syllabi = list(stored.values())
        faculty = add_syllabus_faculty(faculty, syllabi)
        contents = [(args.output, report(courses, faculty, syllabi))]
        for path, content in contents:
            if path.exists() and not path.is_file():
                raise ValueError(f'{path}: output is not a regular file')
            staged.append((stage_file(path, content), path))
        save_database(args.database, courses, faculty, syllabi)
        for temporary, path in staged:
            temporary.replace(path)
        print(f'Wrote {args.output} and {args.database} ({len(syllabi)} syllabi).')
        return 0
    except Exception as error:
        print(f'Generation failed: {error}', file=sys.stderr)
        return 1
    finally:
        for temporary, _ in staged:
            temporary.unlink(missing_ok=True)


if __name__ == '__main__':
    raise SystemExit(main())
