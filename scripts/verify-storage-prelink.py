#!/usr/bin/env python3
"""Verify static storage predictions against this build's final prelink image."""
import hashlib
import json
from pathlib import Path
import struct
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'kits/XnuPrelink'))
import native_prelink as np

def verify(image_path, audit_path):
    audit = json.loads(audit_path.read_text())
    image = image_path.read_bytes()
    report = json.loads(image_path.with_suffix('.json').read_text())
    if (audit['schema'] != 'storage-static-v1' or audit['runtime_qualified'] is not False or
        report['candidate_sha256'] != hashlib.sha256(image).hexdigest() or
        report['original_sha256'] != audit['donor_sha256'] or report['slide'] != audit['slide']):
        raise ValueError('Storage/prelink provenance mismatch')
    if [row['slot'] for row in audit['methods']] != list(range(190)):
        raise ValueError('Incomplete storage method manifest')
    macho = np.macho(image)
    exports = {name: va for va, names in np.exports(image, macho).items() for name in names}
    extents = [e for e in report['extents'] if e['module'] == 'com.apple.iokit.IOStorageFamily']
    def owned(va):
        return any(e['va'] <= va < e['va'] + e['size'] for e in extents)
    for name in ('vtable', 'original_metaclass', 'original_protected_constructor', 'original_base_destructor'):
        if not owned(int(audit[name], 16)):
            raise ValueError('Storage binding outside final donor: ' + name)
    table = int(audit['vtable'], 16)
    off = np.backed_offset(macho['segments'], table + 16, 190 * 8, len(image))
    actual = struct.unpack_from('<190Q', image, off)
    for row in audit['methods']:
        target = exports[row['reference_name']] if row['kernel_names'] else int(row['candidate_target'], 16)
        if actual[row['slot']] != target:
            raise ValueError('Final storage vtable target mismatch: ' + str(row['slot']))
    # The real kernel must have consumed exactly the predicted absolute imports.
    checked = 0
    for manifest in (ROOT / 'build').glob('*/bindings.json'):
        binding = json.loads(manifest.read_text())
        if binding.get('donor_sha256') != audit['donor_sha256']:
            continue
        for name, target in binding['bindings'].items():
            if exports.get(name) != int(target, 16) or not owned(int(target, 16)):
                raise ValueError('Final kernel binding mismatch: ' + name)
            checked += 1
    if not checked:
        raise ValueError('No static storage imports verified in final kernel')
    pmgr_path = ROOT / 'build/sheng-platform-power/build-report.json'
    if pmgr_path.is_file():
        pmgr = json.loads(pmgr_path.read_text())
        entries = pmgr['compiled_entries']
        if len(entries) != 340 or not pmgr['final_verification_required']:
            raise ValueError('Incomplete PMGR evidence')
        base = exports['__ZTV6IOPMGR'] + 16
        for slot, name in enumerate(entries):
            if slot in (0, 1, 7) or 168 <= slot < 340:
                continue
            off = np.backed_offset(macho['segments'], base + slot * 8, 8, len(image))
            if exports.get(name) != struct.unpack_from('<Q', image, off)[0]:
                raise ValueError('Final PMGR native inheritance mismatch: ' + str(slot))
        for name, target in pmgr['bindings'].items():
            va = int(target, 16)
            if exports.get(name) != va or not any(e['module'] == 'com.apple.driver.ApplePMGR' and
                    e['va'] <= va < e['va'] + e['size'] for e in report['extents']):
                raise ValueError('Final PMGR absolute import mismatch: ' + name)
        print('PASS: final PMGR imports and native inheritance; runtime remains unqualified')
    result = dict(candidate_sha256=report['candidate_sha256'], slots_verified=190,
                  imports_verified=checked, runtime_qualified=False)
    (ROOT / 'build/storage-abi/final-prelink.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))

if __name__ == '__main__':
    verify(Path(sys.argv[1]), ROOT / 'build/storage-abi/static-interface.json')
