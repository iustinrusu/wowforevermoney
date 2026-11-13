"""Cheap checks on the page script (there's no JavaScript engine on this PC): an unescaped apostrophe in a
flag label broke the whole page twice on 2026-11-13."""
import re
import unittest
from pathlib import Path

JS = Path(__file__).resolve().parent.parent / 'web' / 'app.js'
STR = r"""(?:'(?:[^'\\\n]|\\.)*'|"(?:[^"\\\n]|\\.)*")"""


class WebTests(unittest.TestCase):
    def test_flag_labels_are_quoted_strings(self):
        text = JS.read_text(encoding='utf-8')
        block = text[text.index('const FLAGS = {'):text.index('};', text.index('const FLAGS = {'))]
        entry = re.compile(r'^\s+\w+: \[\s*' + STR + r'(\s*,\s*' + STR + r')*\s*\],?\s*$')
        for line in block.splitlines()[1:]:
            if line.strip():
                self.assertRegex(line, entry, 'a flag label is not a valid quoted string (unescaped quote?)')


if __name__ == '__main__':
    unittest.main()
