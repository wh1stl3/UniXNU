"""Mock external tools to check failure ordering; no image qualification claims."""
import importlib.util
from pathlib import Path
import plistlib
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('prepare_root', Path(__file__).with_name('prepare-sheng-root-inputs.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class RootPreparationTests(unittest.TestCase):
    def test_wrong_digest_stops_before_tools(self):
        with tempfile.TemporaryDirectory() as directory:
            images = [Path(directory) / name for name in m.PINS]
            for image in images:
                image.write_bytes(b'wrong original image')
            with patch.object(m, 'run') as run, self.assertRaises(ValueError):
                m.prepare(*images)
            run.assert_not_called()

    def exercise(self, failure=None):
        calls = []
        def run(*args):
            calls.append([str(a) for a in args])
            if failure and failure in str(args[1]):
                raise subprocess.CalledProcessError(1, args)
        def output(args, **kwargs):
            if args[0] == 'git':
                return 'def026642c6c6e71be0dea267d989df1d29ddc64\n'
            if args[0] == 'brew':
                return '/test/openssl\n'
            self.assertEqual(args[0], 'hdiutil')
            self.assertIn('-readonly', args)
            calls.append(args)
            return plistlib.dumps({'system-entities': [{'dev-entry': '/dev/disk99', 'content-hint': 'GUID_partition_scheme'}]})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'build/verified-root-host').mkdir(parents=True)
            images = [root / name for name in m.PINS]
            for image in images:
                image.touch()
            with patch.object(m, 'ROOT', root), patch.object(m, 'digest', side_effect=lambda p: m.PINS[p.name]), patch.object(m, 'run', side_effect=run), patch.object(m.subprocess, 'check_output', side_effect=output):
                if failure:
                    with self.assertRaises(subprocess.CalledProcessError):
                        m.prepare(*images)
                else:
                    m.prepare(*images)
        return calls

    def test_host_failure_never_attaches(self):
        calls = self.exercise('tests/check.py')
        self.assertFalse(any(c[0] == 'hdiutil' for c in calls))

    def test_policy_failure_detaches(self):
        calls = self.exercise('build-owner-os-policy.py')
        self.assertEqual(calls[-1], ['hdiutil', 'detach', '/dev/disk99'])
        self.assertFalse(any('build-verified-root-probe.py' in str(c) for c in calls))

    def test_success_preserves_full_verification_before_probe(self):
        calls = self.exercise()
        names = [Path(c[1]).name for c in calls if c[0] == 'python3']
        self.assertEqual(names, ['check.py', 'build-owner-os-policy.py', 'manifest.py', 'verify_image.py', 'build-verified-root-probe.py'])


if __name__ == '__main__':
    unittest.main()
