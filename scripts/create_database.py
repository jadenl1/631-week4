#!/usr/bin/env python3
"""Run the C scheduler and store its structured results using Python SQLite."""
import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

SCHEMA = [
    'CREATE TABLE IF NOT EXISTS Faculty (name TEXT PRIMARY KEY, department TEXT NOT NULL, office TEXT NOT NULL);',
    'CREATE TABLE IF NOT EXISTS Availability (faculty_name TEXT PRIMARY KEY REFERENCES Faculty(name), days_mask INTEGER NOT NULL, start_minute INTEGER NOT NULL, end_minute INTEGER NOT NULL, weekly_minutes INTEGER NOT NULL, block_minutes INTEGER NOT NULL);',
    'CREATE TABLE IF NOT EXISTS Courses (code TEXT PRIMARY KEY, title TEXT NOT NULL, faculty_name TEXT NOT NULL REFERENCES Faculty(name));',
    'CREATE TABLE IF NOT EXISTS ClassMeetings (course_code TEXT PRIMARY KEY REFERENCES Courses(code), session INTEGER NOT NULL, days_mask INTEGER, start_minute INTEGER, end_minute INTEGER, room TEXT NOT NULL, status TEXT NOT NULL);',
    'CREATE TABLE IF NOT EXISTS OfficeHourPlans (faculty_name TEXT REFERENCES Faculty(name), session INTEGER, assigned_minutes INTEGER NOT NULL, required_minutes INTEGER NOT NULL, status TEXT NOT NULL, PRIMARY KEY(faculty_name,session));',
    'CREATE TABLE IF NOT EXISTS OfficeHours (faculty_name TEXT NOT NULL, session INTEGER NOT NULL, day INTEGER NOT NULL, start_minute INTEGER NOT NULL, end_minute INTEGER NOT NULL, PRIMARY KEY(faculty_name,session,day,start_minute), FOREIGN KEY(faculty_name,session) REFERENCES OfficeHourPlans(faculty_name,session));',
]
TABLES = ('Faculty', 'Availability', 'Courses', 'ClassMeetings', 'OfficeHourPlans', 'OfficeHours')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('courses')
    parser.add_argument('faculty')
    parser.add_argument('--database', default=os.environ.get('SCHEDULE_DB', 'schedule.db'))
    parser.add_argument('--scheduler', default=str(Path(__file__).resolve().parents[1] / 'build/scheduler'))
    args = parser.parse_args()
    command = [args.scheduler, args.courses, args.faculty]
    try:
        result = subprocess.run(command, env={**os.environ, 'SCHEDULE_FORMAT': 'json'},
                                capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        report = subprocess.run(command, env={**os.environ, 'SCHEDULE_FORMAT': 'markdown'},
                                capture_output=True, text=True, check=True).stdout
        with closing(sqlite3.connect(args.database)) as db:
            db.execute('PRAGMA foreign_keys=ON')
            with db:
                db.execute('BEGIN IMMEDIATE')
                for statement in SCHEMA:
                    db.execute(statement)
                for table in reversed(TABLES):
                    db.execute(f'DELETE FROM {table}')
                for table in TABLES:
                    rows = data[table]
                    if rows:
                        placeholders = ','.join('?' for _ in rows[0])
                        db.executemany(f'INSERT INTO {table} VALUES ({placeholders})', rows)
        sys.stdout.write(report)
    except subprocess.CalledProcessError as error:
        sys.stderr.write(error.stderr)
        return 1
    except (OSError, ValueError, sqlite3.Error) as error:
        print(f'Database generation failed: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
