#!/usr/bin/env python3
"""Stage the pinned Sheng diagnostic font without requiring a UEFI checkout."""
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
REVISION = '20ac23d5e0937106c2129303dfc931b3390ae660'
RELATIVE = 'Silicon/Silicium/SiliciumPkg/Library/FrameBufferSerialPortLib/Font.h'
DIGEST = 'd2a3687db67b069f4e34a961e17fd28b0242986e3fa8dd8a7545cab70834fa8e'
URL = f'https://raw.githubusercontent.com/UniXNU/uefi-sheng/{REVISION}/{RELATIVE}'

def stage(root):
    target = root / 'uefi-sheng' / RELATIVE
    if target.is_file():
        data = target.read_bytes()
    else:
        with urllib.request.urlopen(URL, timeout=60) as response:
            data = response.read()
    if hashlib.sha256(data).hexdigest() != DIGEST:
        raise ValueError('Sheng font SHA256 mismatch; refusing to replace existing input')
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_bytes(data)
    report = root / 'build/boot-progress/font-input.json'
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(dict(url=URL, revision=REVISION, sha256=DIGEST,
                                     target=str(target), firmware_built=False), indent=2) + '\n')
    print(f'PASS: pinned Sheng Font.h {DIGEST}')

if __name__ == '__main__':
    stage(ROOT)
