#!/usr/bin/env python3
"""Extract the supplied XLSX into two editable TSV inputs (standard library only)."""
import argparse
import csv
from pathlib import Path
import re
from xml.etree import ElementTree as ET
from zipfile import ZipFile

NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
# Explicit, reviewable identity assumptions; original names remain in source.
ALIASES = {'Bemley': 'Bemley, Jesse', 'Bemley, J': 'Bemley, Jesse',
           'Eugene Harris': 'Eugene T. Harris'}


def extract(path):
    with ZipFile(path) as archive:
        strings = [''.join(e.itertext()) for e in
                   ET.fromstring(archive.read('xl/sharedStrings.xml'))]
        sheet = ET.fromstring(archive.read('xl/worksheets/sheet1.xml'))
        for row in sheet.findall('.//m:row', NS)[1:]:
            cells = {}
            for cell in row.findall('m:c', NS):
                value = cell.find('m:v', NS)
                if value is not None:
                    cells[re.sub(r'\d', '', cell.get('r'))] = (
                        strings[int(value.text)] if cell.get('t') == 's' else value.text).strip()
            if cells.get('A'):
                yield cells


def clock(value):
    minutes = round(float(value) * 1440)
    return f'{minutes // 60:02}:{minutes % 60:02}'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workbook', type=Path)
    parser.add_argument('--output', type=Path, default=Path('data'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    courses = []
    faculty = {}
    for row in extract(args.workbook):
        name = ALIASES.get(row['H'], row['H'])
        faculty.setdefault(name, []).append(row['A'])
        session = re.search(r'\((7R[12])\)', row['B'])
        if not session:
            raise ValueError(f"Missing session: {row['A']}")
        asynchronous = 'Asynchronous' in row.get('E', '')
        start, end = ('-', '-') if asynchronous else (clock(row['E']), clock(row['F']))
        state = 'async' if asynchronous else ('scheduled' if start < end else 'review')
        courses.append([row['A'], row['B'], name, session[1], row.get('D', '-') or '-',
                        start, end, row['G'], state])
    with (args.output / 'courses.tsv').open('w', newline='') as out:
        writer = csv.writer(out, delimiter='\t', lineterminator='\n')
        writer.writerow(['course', 'title', 'lecturer', 'session', 'days', 'start', 'end', 'room', 'status'])
        writer.writerows(courses)
    with (args.output / 'faculty.tsv').open('w', newline='') as out:
        writer = csv.writer(out, delimiter='\t', lineterminator='\n')
        writer.writerow(['lecturer', 'department', 'office', 'days', 'available_start',
                         'available_end', 'weekly_minutes', 'block_minutes', 'courses'])
        for name, codes in sorted(faculty.items()):
            writer.writerow([name, 'CTEC', 'TBD', 'MTWRF', '09:00', '17:00', '120', '60', ';'.join(codes)])
    print(f'Imported {len(courses)} courses and {len(faculty)} faculty. Faculty availability is sample data.')


if __name__ == '__main__':
    main()
