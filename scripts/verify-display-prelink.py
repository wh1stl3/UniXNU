#!/usr/bin/env python3
"""Verify every offline display vtable prediction and absolute import after prelink."""
import hashlib,json,os,struct,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'kits/XnuPrelink'))
import native_prelink as np
def verify(path):
    path=Path(path);blob=path.read_bytes();plan=json.loads(path.with_suffix('.json').read_text())
    audit=json.loads((ROOT/'build/display-analysis/mobile-graphics-legacy-abi.json').read_text())
    report=json.loads((ROOT/'build/native-legacy-display/build-report.json').read_text())
    if (hashlib.sha256(blob).hexdigest()!=plan['candidate_sha256'] or plan['original_sha256']!=report['donor_sha256'] or
        plan['original_sha256']!=audit['original_sha256'] or plan['slide']!=-0x1000000 or
        not report['final_verification_required'] or len(audit['methods'])!=358):
        raise ValueError('Display evidence/provenance mismatch')
    image=np.macho(blob);names={n:v for v,group in np.exports(blob,image).items() for n in group}
    def read(va,n):
        off=np.backed_offset(image['segments'],va,n,len(blob));return blob[off:off+n]
    actual=struct.unpack('<358Q',read(int(audit['legacy_vptr'],16),358*8))
    for i,row in enumerate(audit['methods']):
        if row['slot']!=i:raise ValueError('Incomplete display slots')
        targets={names[n] for n in row['kernel_names'] if n in names} if row['kernel_names'] else {int(row['address'],16)}
        if targets!={actual[i]}:raise ValueError('Final display slot mismatch: '+str(i))
    for name,address in report['bindings'].items():
        va=int(address,16)
        if names.get(name)!=va or not any(e['va']<=va<e['va']+e['size'] for e in plan['extents']):
            raise ValueError('Final display import mismatch: '+name)
    hid=json.loads((ROOT/'build/sheng-hid-input/abi-audit.json').read_text())
    if hid['donor_sha256']!=plan['original_sha256'] or len(hid['methods'])!=207:
        raise ValueError('HID provenance/slot count mismatch')
    hid_actual=struct.unpack('<207Q',read(hid['vptr'],207*8))
    for i,row in enumerate(hid['methods']):
        targets={names[n] for n in row['kernel_names'] if n in names} if row['kernel_names'] else {row['address']}
        if targets!={hid_actual[i]}:raise ValueError('Final HID slot mismatch: '+str(i))
    for name,va in hid['bindings'].items():
        if names.get(name)!=va or not any(e['module']=='com.apple.iokit.IOHIDFamily' and e['va']<=va<e['va']+e['size'] for e in plan['extents']):
            raise ValueError('Final HID import mismatch: '+name)
    env=dict(os.environ,UNIXNU_FINAL_DISPLAY=str(path));env.pop('UNIXNU_STATIC_DONOR',None)
    subprocess.run([sys.executable,ROOT/'scripts/audit-mobile-graphics-legacy.py'],env=env,check=True)
    print(json.dumps(dict(candidate_sha256=plan['candidate_sha256'],slots_verified=358,imports_verified=len(report['bindings']),runtime_qualified=False)))

if __name__=='__main__':
    verify(sys.argv[1])
