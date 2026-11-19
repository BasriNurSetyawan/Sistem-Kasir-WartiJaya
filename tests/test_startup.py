import os
import subprocess
import sys
import unittest


def _startup_env():
    env = os.environ.copy()
    env.update({
        'SECRET_KEY': 'startup-test-secret-key-long-enough-12345',
        'API_TOKEN': 'startup-test-api-token-long-enough-12345',
        'DATABASE_URL': 'sqlite:///:memory:',
        'PORT': '7860',
        'PYTHONDONTWRITEBYTECODE': '1',
    })
    return env


class StartupTestCase(unittest.TestCase):
    def test_importing_app_does_not_load_numpy_or_sklearn(self):
        code = (
            'import sys; import app.run; '
            "assert 'numpy' not in sys.modules; "
            "assert not any(name == 'sklearn' or name.startswith('sklearn.') "
            'for name in sys.modules)'
        )
        subprocess.run(
            [sys.executable, '-c', code],
            check=True,
            capture_output=True,
            text=True,
            env=_startup_env(),
        )

    def test_main_prints_ready_before_starting_waitress(self):
        code = '''
import runpy
import waitress
waitress.serve = lambda app, host, port: print(f'SERVE_CALLED {port}')
runpy.run_module('app.run', run_name='__main__')
'''
        result = subprocess.run(
            [sys.executable, '-c', code],
            check=True,
            capture_output=True,
            text=True,
            env=_startup_env(),
        )
        ready = 'Server siap! Buka http://127.0.0.1:7860 (Tekan Ctrl+C untuk berhenti)'
        self.assertIn(ready, result.stdout)
        self.assertLess(result.stdout.index(ready), result.stdout.index('SERVE_CALLED 7860'))


if __name__ == '__main__':
    unittest.main()
