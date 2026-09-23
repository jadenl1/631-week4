"""Exercise the actual executable using temporary inputs."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / 'build/scheduler'
COURSES = (ROOT / 'data/courses.tsv').read_text()
FACULTY = (ROOT / 'data/faculty.tsv').read_text()


class CommandTests(unittest.TestCase):
    def run_files(self, courses=COURSES, faculty=FACULTY):
        with tempfile.TemporaryDirectory() as directory:
            a, b = Path(directory) / 'courses.tsv', Path(directory) / 'faculty.tsv'
            a.write_text(courses)
            b.write_text(faculty)
            return subprocess.run([BIN, a, b], capture_output=True, text=True)

    def test_output(self):
        result = self.run_files()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.count('## ')-result.stdout.count('### '), 25)
        self.assertEqual(result.stdout.count('**Withheld:'), 3)
        self.assertEqual(result.stdout.count('REVIEW:'), 3)
        self.assertIn('Teaching conflict: CTEC 435.180 / CTEC 402.180', result.stdout)
        self.assertEqual(result.stdout, self.run_files().stdout)

    def test_exactly_two_inputs(self):
        for args in [[], ['x'], ['x', 'y', 'z']]:
            result = subprocess.run([BIN, *args], capture_output=True)
            self.assertNotEqual(result.returncode, 0)

    def test_bad_inputs(self):
        for courses, faculty in [
            ('bad header\n', FACULTY),
            (COURSES.replace('16:00', '25:00', 1), FACULTY),
            (COURSES.replace('\tMW\t', '\tMX\t', 1), FACULTY),
            (COURSES.replace('scheduled', 'invalid', 1), FACULTY),
            (COURSES + COURSES.splitlines()[1] + '\n', FACULTY),
            (COURSES, FACULTY + FACULTY.splitlines()[1] + '\n'),
            (COURSES, FACULTY.replace('Adedoyin, Anthony', 'Unknown', 1)),
            (COURSES, FACULTY.replace('120\t60', '121\t60', 1)),
            (COURSES, FACULTY.replace('120\t60', '120\t0', 1)),
            (COURSES, FACULTY.replace('CTEC 350.170;', 'NONEXISTENT;', 1)),
            (COURSES.splitlines()[0] + '\n', FACULTY),
            (COURSES, FACULTY.splitlines()[0] + '\n'),
            (COURSES.replace('CTEC 350.170', 'x'*300, 1), FACULTY),
        ]:
            with self.subTest(courses=courses[:30], faculty=faculty[:30]):
                result = self.run_files(courses, faculty)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, '')

    def test_shortfall(self):
        result = self.run_files(faculty=FACULTY.replace('09:00\t17:00', '09:00\t09:30'))
        self.assertEqual(result.returncode, 0)
        self.assertIn('INSUFFICIENT AVAILABILITY', result.stdout)

    def test_missing_file(self):
        result = subprocess.run([BIN, '/nonexistent/courses.tsv', '/nonexistent/faculty.tsv'], capture_output=True)
        self.assertNotEqual(result.returncode, 0)

    def test_import_reproducible(self):
        with tempfile.TemporaryDirectory() as directory:
            subprocess.run(['python3', ROOT / 'scripts/import_schedule.py',
                            next(ROOT.glob('*.xlsx')), '--output', directory], check=True, capture_output=True)
            self.assertEqual((Path(directory) / 'courses.tsv').read_text(), COURSES)
            self.assertEqual((Path(directory) / 'faculty.tsv').read_text(), FACULTY)


if __name__ == '__main__':
    unittest.main()
