"""Update on start: pulls the latest main in a git folder, never breaks a start."""
import subprocess
import tempfile
import unittest
from pathlib import Path

from wfm.updater import update


def git(repo, *a):
    return subprocess.run(['git', '-C', str(repo), '-c', 'user.name=t', '-c', 'user.email=t@t', *a],
                          capture_output=True, text=True, check=True)


class UpdaterTests(unittest.TestCase):
    def test_pulls_new_code_then_reports_up_to_date(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            origin, clone = d / 'origin', d / 'clone'
            origin.mkdir()
            git(origin, 'init', '-q', '-b', 'main')
            (origin / 'app.txt').write_text('v1', encoding='utf-8')
            git(origin, 'add', '.'); git(origin, 'commit', '-q', '-m', 'v1')
            subprocess.run(['git', 'clone', '-q', str(origin), str(clone)], check=True, capture_output=True)
            self.assertEqual(update(clone), (False, 'already up to date'))
            (origin / 'app.txt').write_text('v2', encoding='utf-8')
            git(origin, 'commit', '-q', '-am', 'v2')
            self.assertEqual(update(clone), (True, 'updated to the latest version'))
            self.assertEqual((clone / 'app.txt').read_text(encoding='utf-8'), 'v2')

    def test_a_zip_folder_is_left_alone(self):
        with tempfile.TemporaryDirectory() as d:
            changed, what = update(Path(d))
            self.assertFalse(changed)
            self.assertIn('ZIP', what)


if __name__ == '__main__':
    unittest.main()
