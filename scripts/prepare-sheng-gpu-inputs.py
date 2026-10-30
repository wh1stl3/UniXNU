#!/usr/bin/env python3
"""Prepare pinned GPU sources, firmware and generated Sheng headers before archives."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import urllib.request
ROOT = Path(__file__).resolve().parents[1]
PINS = {
 'prepare-sheng-gmu.py': '5b19fba0201eb217e4c0410621b40c91fda413a922b97f382026d05a658f1c6c',
 'prepare-sheng-gmu-votes.py': 'dfb330a56d990eb71ed60fd73f056fbcacca0a5533e6f011f7ee85286a6157ba',
 'audit-adreno-platform.py': '53ebca1ebff100d187d07a8ff1eb207aee67242e4a2bfbf54d19032ebf526a15',
}

def fetch_board(root):
    pins = json.loads((root / 'scripts/data/adreno-inputs.json').read_text())['board']
    tree = root / '.cache/linux-dts'
    for name, digest in pins['sha256'].items():
        path = tree / name
        if path.is_symlink():
            data = path.readlink().as_posix().encode()
        elif path.is_file():
            data = path.read_bytes()
        else:
            url = pins['repository'].replace('https://github.com/', 'https://raw.githubusercontent.com/') + '/' + pins['commit'] + '/' + name
            with urllib.request.urlopen(url, timeout=60) as response:
                data = response.read()
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError('Pinned board source mismatch: ' + name)
        if not path.exists() and not path.is_symlink():
            path.parent.mkdir(parents=True, exist_ok=True)
            if name == 'include/dt-bindings/input/linux-event-codes.h':
                link = data.decode()
                (path.parent / link).resolve().relative_to(tree.resolve())
                path.symlink_to(link)
            else:
                path.write_bytes(data)
    print(f'PASS: {len(pins["sha256"])} pinned board DTS inputs')

def stage_generators(root):
    for name, digest in PINS.items():
        source = root / ('kits/sheng' if name == 'audit-adreno-platform.py' else 'scripts') / name
        text = source.read_text()
        if hashlib.sha256(text.encode()).hexdigest() != digest:
            raise ValueError('Pinned GPU generator changed: ' + name)
        if name == 'audit-adreno-platform.py':
            text = text.replace('parents[2]', 'parents[1]').replace("ROOT / 'docs/adreno-inputs.json'", "ROOT / 'scripts/data/adreno-inputs.json'")
        else:
            text = text.replace("ROOT/'kits/sheng/audit-adreno-platform.py'", "ROOT/'scripts/generated-audit-adreno-platform.py'")
        (root / 'scripts' / ('generated-' + name)).write_text(text)

if __name__ == '__main__':
    subprocess.run([sys.executable, ROOT / 'scripts/fetch-adreno-inputs.py'], check=True)
    fetch_board(ROOT)
    stage_generators(ROOT)
    for name in ('prepare-sheng-gmu.py', 'prepare-sheng-gmu-votes.py'):
        subprocess.run([sys.executable, ROOT / 'scripts' / ('generated-' + name)], check=True)
