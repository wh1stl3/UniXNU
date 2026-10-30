"""Read a pinned donor at planned kext addresses without constructing a kernel candidate."""
import hashlib
import struct
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'kits/XnuPrelink'))
import native_prelink as np

class DonorView:
    def __init__(self,path,slide):
        self.blob=Path(path).read_bytes();self.slide=slide
        self.digest=hashlib.sha256(self.blob).hexdigest()
        if self.digest!='f18b4df865405f2a287b84977d7aca745e056d656d9fc9df1662970ce2969de7' or slide!=-0x1000000:
            raise ValueError('Unqualified display donor or slide')
        self.image=np.macho(self.blob);self.owned=[];self.extents=[];self.hashes={}
        info=next(s for s in self.image['segments'] if s['name']=='__PRELINK_INFO')
        meta=np.unserialize_xml(self.raw(info['va'],info['filesize']))
        for entry in meta['_PrelinkInfoDictionary']:
            va=entry.get('_PrelinkExecutableLoadAddr')
            if not va or entry.get('OSKernelResource'):continue
            module=np.macho(self.blob,np.backed_offset(self.image['segments'],va,32,len(self.blob)))
            for s in module['segments']:
                if not s['size'] or s['name']=='__LINKEDIT':continue
                self.owned.append((s['va'],s['va']+s['size']))
                self.extents.append(dict(module=entry['CFBundleIdentifier'],segment=s['name'],va=s['va']+slide,size=s['size']))
                if s['name']=='__TEXT_EXEC':self.hashes[entry['CFBundleIdentifier']]=hashlib.sha256(self.raw(s['va'],s['size'])).hexdigest()
        offsets=meta['_PrelinkLinkKASLROffsets'];count,=struct.unpack_from('<I',offsets)
        if len(offsets)!=4+count*4:raise ValueError('Invalid donor relocation table')
        base=next(s['va'] for s in self.image['segments'] if s['name']=='__PRELINK_TEXT')
        self.fixups=sorted(base+x for x in struct.unpack_from(f'<{count}I',offsets,4))
        self.names={n:v for v,group in np.exports(self.blob,self.image).items() for n in group}
    def raw(self,va,n):
        off=np.backed_offset(self.image['segments'],va,n,len(self.blob));return self.blob[off:off+n]
    def read(self,va,n):
        original=va-self.slide
        if not any(lo<=original and original+n<=hi for lo,hi in self.owned):
            return self.raw(va,n)
        out=bytearray(self.raw(original,n))
        from bisect import bisect_left
        for site in self.fixups[bisect_left(self.fixups,original):]:
            if site>=original+n:break
            if site+8>original+n:raise ValueError('Partial relocation read')
            target,=struct.unpack_from('<Q',out,site-original)
            if any(lo<=target<hi for lo,hi in self.owned):struct.pack_into('<Q',out,site-original,target+self.slide)
        return bytes(out)
