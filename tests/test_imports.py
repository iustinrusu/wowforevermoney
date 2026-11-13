"""Every module imports: catches syntax errors in code the other tests don't exercise (e.g. the server)."""
import importlib
import pkgutil
import unittest

import wfm


class ImportTests(unittest.TestCase):
    def test_every_module_imports(self):
        for mod in pkgutil.iter_modules(wfm.__path__):
            with self.subTest(module=mod.name):
                importlib.import_module(f'wfm.{mod.name}')


if __name__ == '__main__':
    unittest.main()
