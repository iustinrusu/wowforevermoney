"""Settings "Motion" (the Night watch look, 2026-11-20): saved like the other settings, checked, and never a reason to
recalculate; the page and stylesheet stop every animation when it is off."""
import re
import tempfile
import threading
import unittest
from copy import deepcopy
from pathlib import Path

from wfm import app as app_mod
from wfm.settings import DEFAULTS, Settings

WEB = Path(__file__).resolve().parent.parent / 'web'


def make_app(tmp: Path):
    """An App with only what update_settings touches: settings in a temporary file, the recalculation flag."""
    a = app_mod.App.__new__(app_mod.App)
    s = Settings.__new__(Settings)
    s._lock, s.path, s.data = threading.Lock(), tmp / 'settings.json', deepcopy(DEFAULTS)
    a.settings, a._settings_dirty = s, threading.Event()
    return a


class MotionSettingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = make_app(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_default_follows_the_system(self):
        self.assertEqual(DEFAULTS['motion'], 'system')

    def test_saved_without_recalculating(self):
        new = self.app.update_settings({'motion': 'on'})
        self.assertEqual(new['motion'], 'on')
        self.assertIn('"motion": "on"', self.app.settings.path.read_text(encoding='utf-8'))
        self.assertFalse(self.app._settings_dirty.is_set(), 'a page-only setting must not recalculate')

    def test_other_settings_still_recalculate(self):
        self.app.update_settings({'motion': 'off', 'ah_cut': 0.05})
        self.assertTrue(self.app._settings_dirty.is_set())

    def test_unknown_value_ignored(self):
        new = self.app.update_settings({'motion': 'sometimes'})
        self.assertEqual(new['motion'], 'system')


class MotionPageTests(unittest.TestCase):
    css = (WEB / 'style.css').read_text(encoding='utf-8')
    js = (WEB / 'app.js').read_text(encoding='utf-8')
    html = (WEB / 'index.html').read_text(encoding='utf-8')

    def test_motion_off_stops_everything(self):
        self.assertIn('html[data-motion="off"] *, html[data-motion="off"] *::before, html[data-motion="off"] *::after '
                      '{ animation: none !important; transition: none !important; }', self.css)
        self.assertIn('@media (prefers-reduced-motion: reduce)', self.css)   # before the page script runs

    def test_page_sets_motion_before_first_paint_and_on_change(self):
        self.assertIn('document.documentElement.dataset.motion', self.html)
        self.assertIn("document.documentElement.dataset.motion = motionOn() ? 'on' : 'off'", self.js)
        self.assertIn("REDUCE.addEventListener('change', applyMotion)", self.js)

    def test_new_animations_move_only_transform_and_opacity(self):
        # the brief: animate only transform and opacity, so 400-row tables and live updates stay smooth.
        # yours-glow (the Biggest markets glow, 2026-11-19) is older and kept as the user asked for it.
        frames = re.findall(r'@keyframes\s+([\w-]+)\s*\{((?:[^{}]*\{[^{}]*\})*)\s*\}', self.css)
        self.assertGreater(len(frames), 10)
        for name, body in frames:
            if name == 'yours-glow':
                continue
            props = set(re.findall(r'([\w-]+)\s*:', body))
            self.assertLessEqual(props, {'transform', 'opacity'}, f'@keyframes {name} animates {props}')

    def test_font_is_ours_to_ship(self):
        self.assertTrue((WEB / 'fonts' / 'cinzel-latin.woff2').is_file())
        self.assertIn('SIL Open Font License', (WEB / 'fonts' / 'OFL.txt').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
