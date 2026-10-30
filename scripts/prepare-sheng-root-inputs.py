#!/usr/bin/env python3
"""Prepare genuine pinned Sheng policies with an ephemeral CI-only owner anchor."""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PINS = {
    '044-76040-038.dmg': '3f99b859c9728379110b66657c7b15285bcb1925ad8b5726542e2cdcf8b1028d',
    '044-76034-038.dmg': 'b4908cde41d23e6bc05e6af51a2c9eeb00cf0f863a6a18b1600c96a3fd70414f',
}
SYSTEM_UUID = '8846FE78-2910-4297-AF97-D59BB6F8FC16'


def digest(path):
    with path.open('rb') as stream:
        value = hashlib.sha256()
        for data in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(data)
        return value.hexdigest()


def run(*args):
    subprocess.run([str(a) for a in args], cwd=ROOT, check=True)


def prepare(os_image, system_image):
    images = [os_image.resolve(), system_image.resolve()]
    for path, name in zip(images, PINS):
        if path.name != name or digest(path) != PINS[name]:
            raise ValueError('Unexpected original Sheng image: ' + str(path))
    kit = ROOT / 'kits/VerifiedRoot'
    revision = subprocess.check_output(['git', '-C', str(kit), 'rev-parse', 'HEAD'], text=True).strip()
    if revision != 'def026642c6c6e71be0dea267d989df1d29ddc64':
        raise ValueError('Unexpected VerifiedRoot source revision')
    host = ROOT / 'build/verified-root-host'
    prefix = subprocess.check_output(['brew', '--prefix', 'openssl@3'], text=True).strip()
    # The upstream suite generates restricted local keys, compiles the real C
    # verifier and checks signatures, corrupted blocks and rejection cases.
    run('python3', kit / 'tests/check.py', '--output', host, '--openssl-prefix', prefix)
    target = ROOT / '.cache/firmware/target-volumes'
    target.mkdir(parents=True, exist_ok=True)
    for image in images:
        link = target / image.name
        if link.exists() or link.is_symlink():
            if link.resolve() != image:
                raise ValueError('Refusing to replace a different image input')
        else:
            link.symlink_to(image)
    mount = target / 'os-mount'
    mount.mkdir(exist_ok=True)
    attached = plistlib.loads(subprocess.check_output([
        'hdiutil', 'attach', '-readonly', '-nobrowse', '-mountpoint', str(mount), '-plist', str(images[0])]))
    disks = [e['dev-entry'] for e in attached['system-entities'] if e.get('content-hint') == 'GUID_partition_scheme']
    if len(disks) != 1:
        raise ValueError('Expected exactly one original OS virtual disk')
    try:
        # Existing checks require read-only virtual media, the exact UUID/size,
        # real RSA verification and every original block, without weakening them.
        run('python3', ROOT / 'scripts/build-owner-os-policy.py')
    finally:
        run('hdiutil', 'detach', disks[0])
    policy = ROOT / 'build/verified-root-systemos'
    run('python3', kit / 'tools/manifest.py', '--image', images[1],
        '--private-key', host / 'keys/owner.pem', '--public-key', host / 'keys/owner-public.pem',
        '--volume-uuid', SYSTEM_UUID, '--generation', '1', '--output', policy)
    run('python3', kit / 'tools/verify_image.py', '--library', host / 'verified-root.dylib',
        '--manifest', policy / 'manifest.bin', '--trusted-key', policy / 'trusted-key.bin',
        '--image', images[1], '--volume-uuid', SYSTEM_UUID, '--minimum-generation', '1',
        '--output', policy / 'verification.json')
    run('python3', ROOT / 'scripts/build-verified-root-probe.py', '--component', 'os', '--include-systemos')
    (host / 'ci-provenance.json').write_text(json.dumps(dict(
        source_revision=revision, source_sha256=PINS, ephemeral_ci_anchor=True,
        runtime_qualified=False, hardware_tested=False, deployable=False), indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('os_image', type=Path)
    parser.add_argument('system_image', type=Path)
    args = parser.parse_args()
    prepare(args.os_image, args.system_image)
