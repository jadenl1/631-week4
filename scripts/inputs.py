"""Faculty and course parsing is independent of syllabus extraction."""
import csv
import re

DAYS = dict(zip('MTWRF', ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']))


def read_tsv(path, required, unique):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream, delimiter='\t')
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f'{path}: missing required columns: {sorted(required)}')
        rows = list(reader)
    if not rows:
        raise ValueError(f'{path}: no data rows')
    seen = set()
    for row in rows:
        if None in row or any(row.get(key) is None or not row[key].strip() for key in required):
            raise ValueError(f'{path}: incomplete or malformed row')
        if row[unique] in seen:
            raise ValueError(f'{path}: duplicate {unique}: {row[unique]}')
        seen.add(row[unique])
    return rows


def minutes(value):
    if not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', value):
        raise ValueError(f'Invalid time: {value}')
    hour, minute = map(int, value.split(':'))
    return hour * 60 + minute


def load_inputs(courses_path, faculty_path):
    faculty = read_tsv(faculty_path, {'lecturer', 'department', 'office'}, 'lecturer')
    courses = read_tsv(courses_path, {'course', 'title', 'lecturer', 'session', 'days', 'start', 'end', 'room', 'status'}, 'course')
    names = {f['lecturer'] for f in faculty}
    for course in courses:
        if course['lecturer'] not in names:
            raise ValueError(f"Unknown instructor: {course['lecturer']}")
        if course['session'] not in {'7R1', '7R2'} or course['status'] not in {'scheduled', 'async', 'review'}:
            raise ValueError(f"Invalid session/status: {course['course']}")
        if course['status'] != 'async':
            if not course['days'] or any(day not in DAYS for day in course['days']):
                raise ValueError(f"Invalid days: {course['days']}")
            if minutes(course['start']) >= minutes(course['end']):
                course['status'] = 'review'
    return courses, faculty
