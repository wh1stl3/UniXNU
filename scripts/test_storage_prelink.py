"""Synthetic Mach-O regression tests for final storage binding verification."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('storage_verify', Path(__file__).with_name('verify-storage-prelink.py'))
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)

class StorageFinalTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.original_root = verify.ROOT
        verify.ROOT = self.root
        self.addCleanup(setattr, verify, 'ROOT', self.original_root)
        (self.root / 'build/storage-abi').mkdir(parents=True)
        (self.root / 'build/ramblock').mkdir()
        self.image = self.root / 'kernel.macho'
        self.audit = self.root / 'build/storage-abi/static-interface.json'
        self.base = 0x100000
        data = bytearray(0x3000)
        strings = b'\0_native\0_base\0'
        segment = struct.pack('<II16s4Q4I', 0x19, 72, b'__DATA_CONST', self.base, len(data), 0, len(data), 7, 3, 0, 0)
        symbols = struct.pack('<6I', 2, 24, 0x2000, 2, 0x2100, len(strings))
        header = struct.pack('<8I', 0xfeedfacf, 0x100000c, 0, 2, 2, 96, 0, 0) + segment + symbols
        data[:len(header)] = header
        data[0x2100:0x2100 + len(strings)] = strings
        struct.pack_into('<IBBHQ', data, 0x2000, 1, 0xf, 1, 0, self.base + 0x900)
        struct.pack_into('<IBBHQ', data, 0x2010, 9, 0x3, 0, 0, self.base + 0x800)
        struct.pack_into('<190Q', data, 0x110, self.base + 0x800, *([self.base + 0x900] * 189))
        self.image.write_bytes(data)
        self.report = dict(candidate_sha256=hashlib.sha256(data).hexdigest(), original_sha256='donor', slide=-4096,
                           extents=[dict(module='com.apple.iokit.IOStorageFamily', va=self.base, size=0x1000)])
        self.write_report()
        audit = dict(schema='storage-static-v1', runtime_qualified=False, donor_sha256='donor', slide=-4096,
                     vtable=hex(self.base + 0x100), original_metaclass=hex(self.base + 0x810),
                     original_protected_constructor=hex(self.base + 0x800), original_base_destructor=hex(self.base + 0x804),
                     methods=[dict(slot=i, reference_name='_native' if i else '_base', kernel_names=['_native'] if i else [],
                                   candidate_target=hex(self.base + 0x800)) for i in range(190)])
        self.audit.write_text(json.dumps(audit))
        self.manifest = self.root / 'build/ramblock/bindings.json'
        self.manifest.write_text(json.dumps(dict(donor_sha256='donor', bindings={'_base': hex(self.base + 0x800)})))

    def write_report(self):
        self.image.with_suffix('.json').write_text(json.dumps(self.report))

    def test_matching_image(self):
        verify.verify(self.image, self.audit)

    def test_wrong_donor(self):
        self.report['original_sha256'] = 'other'
        self.write_report()
        with self.assertRaisesRegex(ValueError, 'provenance'):
            verify.verify(self.image, self.audit)

    def test_changed_slot_with_valid_image_digest(self):
        data = bytearray(self.image.read_bytes())
        struct.pack_into('<Q', data, 0x110, self.base + 0x804)
        self.image.write_bytes(data)
        self.report['candidate_sha256'] = hashlib.sha256(data).hexdigest()
        self.write_report()
        with self.assertRaisesRegex(ValueError, 'vtable target'):
            verify.verify(self.image, self.audit)

    def test_wrong_absolute_import(self):
        self.manifest.write_text(json.dumps(dict(donor_sha256='donor', bindings={'_base': hex(self.base + 0x804)})))
        with self.assertRaisesRegex(ValueError, 'kernel binding'):
            verify.verify(self.image, self.audit)

    def test_changed_slide(self):
        self.report['slide'] = 0
        self.write_report()
        with self.assertRaisesRegex(ValueError, 'provenance'):
            verify.verify(self.image, self.audit)

    def test_incomplete_slots(self):
        audit = json.loads(self.audit.read_text())
        audit['methods'].pop()
        self.audit.write_text(json.dumps(audit))
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            verify.verify(self.image, self.audit)

    def test_missing_manifest(self):
        self.manifest.unlink()
        with self.assertRaisesRegex(ValueError, 'No static storage'):
            verify.verify(self.image, self.audit)

if __name__ == '__main__':
    unittest.main()
