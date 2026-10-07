"""Exercise Python extraction, persistence, and the actual C launcher offline."""
from contextlib import redirect_stdout, redirect_stderr
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import pipeline
import syllabus

TEXT = '''CTEC 350.170
Your instructor is Dr. Anthony Adedoyin.
Come see me Tuesdays 2–4 PM in Room 210, or by appointment on Zoom.
Class meetings: Monday and Wednesday, 4–6:50 PM.
'''


def field(value):
    return {'value': value, 'evidence': value}


DATA = {'instructor': field('Dr. Anthony Adedoyin'),
        'courses': [field('CTEC 350.170')],
        'office_hours': [field('Tuesdays 2–4 PM in Room 210, or by appointment on Zoom.')]}


def response(data=DATA, **overrides):
    payload = {'status': 'completed', 'output': [
        {'type': 'reasoning'},
        {'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(data)}]}]}
    payload.update(overrides)
    return io.BytesIO(json.dumps(payload).encode())


class ExtractionTests(unittest.TestCase):
    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-only'})
    def test_openai_request_and_source_validation(self):
        with patch('syllabus.urlopen', return_value=response()) as call:
            result = syllabus.extract_openai(TEXT, 'test-model')
        self.assertEqual(syllabus.validate_extraction(result, TEXT), DATA)
        request = call.call_args.args[0]
        self.assertEqual(request.full_url, 'https://api.openai.com/v1/responses')
        self.assertEqual(request.get_header('Authorization'), 'Bearer test-only')
        body = json.loads(request.data)
        self.assertEqual(body['model'], 'test-model')
        self.assertEqual(body['input'], TEXT)
        self.assertFalse(body['store'])
        self.assertTrue(body['text']['format']['strict'])

    @patch.dict(os.environ, {'OPENAI_API_KEY': ''})
    def test_missing_key_does_not_send(self):
        with patch('syllabus.urlopen') as call, self.assertRaisesRegex(ValueError, 'OPENAI_API_KEY'):
            syllabus.extract_openai(TEXT, 'test-model')
        call.assert_not_called()

    def test_invented_hours_rejected(self):
        data = {**DATA, 'office_hours': [field('Monday 9–11 AM')]}
        with self.assertRaisesRegex(ValueError, 'unsupported source evidence'):
            syllabus.validate_extraction(data, TEXT)

    def test_malformed_fields_rejected(self):
        for data in ({}, {**DATA, 'office_hours': 'Tuesday'}, {**DATA, 'instructor': {'value': ''}},
                     {**DATA, 'office_hours': [{'value': 12, 'evidence': 'Tuesday'}]}):
            with self.subTest(data=data), self.assertRaises(ValueError):
                syllabus.validate_extraction(data, TEXT)

    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-only'})
    def test_incomplete_refused_and_empty_responses(self):
        for kwargs in ({'status': 'incomplete'}, {'output': []}, {'output': [
                {'type': 'message', 'content': [{'type': 'refusal', 'refusal': 'No'}]}]}):
            with self.subTest(kwargs=kwargs), patch('syllabus.urlopen', return_value=response(**kwargs)), self.assertRaises(ValueError):
                syllabus.extract_openai(TEXT, 'test-model')

    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-only'})
    def test_api_errors_are_actionable(self):
        for error, message in [(HTTPError('url', 401, 'Unauthorized', {}, None), 'OPENAI_API_KEY'),
                               (HTTPError('url', 429, 'Quota', {}, None), 'quota'),
                               (URLError('offline'), 'connection')]:
            with patch('syllabus.urlopen', side_effect=error), self.assertRaisesRegex(ValueError, message):
                syllabus.extract_openai(TEXT, 'test-model')

    def test_name_matching_is_conservative(self):
        self.assertEqual(syllabus.name_key('Dr. Anthony Adedoyin'), syllabus.name_key('Adedoyin, Anthony'))
        self.assertNotEqual(syllabus.name_key('A. Adedoyin'), syllabus.name_key('Adedoyin, Anthony'))

    def test_document_readers(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'syllabus.docx'
            with ZipFile(path, 'w') as archive:
                archive.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Office hours</w:t></w:r></w:p><w:tbl><w:tr><w:tc><w:p><w:r><w:t>By appointment</w:t></w:r></w:p></w:tc></w:tr></w:tbl></w:body></w:document>')
            self.assertEqual(syllabus.read_document(path), 'Office hours\nBy appointment')
            text = Path(directory) / 'syllabus.txt'
            text.write_text(TEXT)
            self.assertEqual(syllabus.read_document(text), TEXT)
            text.write_text('')
            with self.assertRaisesRegex(ValueError, 'no readable text'):
                syllabus.read_document(text)


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.report = self.directory / 'report.md'
        self.db = self.directory / 'schedule.db'
        self.args = ['--output', str(self.report), '--database', str(self.db)]

    def run_pipeline(self, extra=()):
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            return pipeline.main([*self.args, *extra])

    def test_c_launcher_and_no_generated_hours(self):
        result = subprocess.run([ROOT / 'build/scheduler', *self.args], cwd=self.directory, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = self.report.read_text()
        self.assertEqual(report.count('Department: CTEC'), 25)
        self.assertIn('Monday & Wednesday 4:00 PM – 6:50 PM', report)
        self.assertIn('Teaching conflict:', report)
        self.assertNotIn('120/120', report)
        self.assertEqual(pipeline.load_syllabi(self.db), [])
        with sqlite3.connect(self.db) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM Courses').fetchone()[0], 56)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM OfficeHours').fetchone()[0], 0)
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(), [])

    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-only'})
    def test_syllabus_end_to_end_and_conflicts_kept_separate(self):
        first = self.directory / 'first.txt'
        second = self.directory / 'second.md'
        first.write_text(TEXT)
        second.write_text(TEXT.replace('Tuesdays 2–4 PM', 'Fridays 10–11 AM'))
        other = {**DATA, 'office_hours': [field('Fridays 10–11 AM in Room 210, or by appointment on Zoom.')]}
        with patch('syllabus.urlopen', side_effect=[response(), response(other)]):
            self.assertEqual(self.run_pipeline(['--syllabus', str(first), '--syllabus', str(second)]), 0)
        data = pipeline.load_syllabi(self.db)
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]['matched_faculty'], 'Adedoyin, Anthony')
        self.assertEqual(data[0]['status'], 'needs_review')
        self.assertTrue(data[0]['method'].startswith('openai:'))
        self.assertIn('Tuesdays 2–4 PM', self.report.read_text())
        self.assertIn('Fridays 10–11 AM', self.report.read_text())
        with sqlite3.connect(self.db) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM OfficeHours').fetchone()[0], 2)

    def test_missing_and_unmatched_fields(self):
        file = self.directory / 'unknown.txt'
        file.write_text('An unnamed instructor. No office hours stated.')
        with patch('syllabus.extract_openai', return_value={'instructor': None, 'courses': [], 'office_hours': []}):
            self.assertEqual(self.run_pipeline(['--syllabus', str(file)]), 0)
        data = pipeline.load_syllabi(self.db)[0]
        self.assertIsNone(data['matched_faculty'])
        self.assertEqual(data['status'], 'not_found')

    def test_new_professor_persists_without_json_or_review_section(self):
        file = self.directory / 'new.txt'
        file.write_text('Professor Jane Doe. Office hours: Thursday 3–5 PM. COSC 573')
        data = {'instructor': field('Jane Doe'), 'courses': [field('COSC 573')],
                'office_hours': [field('Thursday 3–5 PM')]}
        with patch('syllabus.extract_openai', return_value=data):
            self.assertEqual(self.run_pipeline(['--syllabus', str(file)]), 0)
        self.assertEqual(self.run_pipeline(), 0)
        report = self.report.read_text()
        self.assertEqual(report.count('## Jane Doe'), 1)
        self.assertIn('**Office hours:** Thursday 3–5 PM', report)
        for unwanted in ('Source:', 'Status:', 'Method:', 'Syllabus extraction review'):
            self.assertNotIn(unwanted, report)
        self.assertFalse(list(self.directory.glob('*.json')))
        with sqlite3.connect(self.db) as db:
            self.assertEqual(db.execute("SELECT name FROM Faculty WHERE name='Jane Doe'").fetchone()[0], 'Jane Doe')
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(), [])

    def test_failure_preserves_outputs_and_database(self):
        self.assertEqual(self.run_pipeline(), 0)
        before = [p.read_bytes() for p in (self.report, self.db)]
        file = self.directory / 'syllabus.txt'
        file.write_text(TEXT)
        with patch('syllabus.extract_openai', side_effect=ValueError('API failed')):
            self.assertEqual(self.run_pipeline(['--syllabus', str(file)]), 1)
        self.assertEqual(before, [p.read_bytes() for p in (self.report, self.db)])

    def test_database_transaction_rolls_back(self):
        self.assertEqual(self.run_pipeline(), 0)
        courses, faculty = pipeline.load_inputs(ROOT / 'data/courses.tsv', ROOT / 'data/faculty.tsv')
        with self.assertRaises(sqlite3.IntegrityError):
            pipeline.save_database(self.db, courses, faculty + faculty[:1], [])
        with sqlite3.connect(self.db) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM Faculty').fetchone()[0], 25)

    def test_legacy_tables_removed_and_unrelated_tables_preserved(self):
        with sqlite3.connect(self.db) as db:
            db.execute('CREATE TABLE Availability (sample TEXT)')
            db.execute('CREATE TABLE OfficeHourPlans (sample TEXT)')
            db.execute('CREATE TABLE OfficeHours (generated TEXT)')
            db.execute('CREATE TABLE UserNotes (note TEXT)')
            db.execute("INSERT INTO UserNotes VALUES ('keep')")
        self.assertEqual(self.run_pipeline(), 0)
        with sqlite3.connect(self.db) as db:
            tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertNotIn('Availability', tables)
            self.assertNotIn('OfficeHourPlans', tables)
            self.assertEqual(db.execute('SELECT note FROM UserNotes').fetchone()[0], 'keep')

    def test_output_cannot_overwrite_input(self):
        self.assertEqual(self.run_pipeline(['--output', str(ROOT / 'data/courses.tsv')]), 1)

    def test_bad_course_input(self):
        original = (ROOT / 'data/courses.tsv').read_text()
        for text in ('bad header\n', original.replace('16:00', '25:00', 1), original.replace('\tMW\t', '\tMX\t', 1),
                     original + original.splitlines()[1] + '\n'):
            file = self.directory / 'courses.tsv'
            file.write_text(text)
            self.assertEqual(self.run_pipeline([str(file), str(ROOT / 'data/faculty.tsv')]), 1)

    def test_import_reproducible(self):
        result = subprocess.run([sys.executable, ROOT / 'scripts/import_schedule.py', next(ROOT.glob('*.xlsx')),
                                 '--output', self.directory], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        for name in ('courses.tsv', 'faculty.tsv'):
            self.assertEqual((self.directory / name).read_text(), (ROOT / 'data' / name).read_text())


if __name__ == '__main__':
    unittest.main()
