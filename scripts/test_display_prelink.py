"""Synthetic final display/HID rejection tests; no runtime qualification."""
import hashlib,importlib.util,json,struct,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('display_verify',Path(__file__).with_name('verify-display-prelink.py'))
v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
class DisplayTests(unittest.TestCase):
 def setUp(self):
  tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name)
  prev=v.ROOT;v.ROOT=self.root;self.addCleanup(setattr,v,'ROOT',prev)
  self.image=self.root/'kernel.macho';self.base=0x100000
  data=bytearray(0x4000);strings=b'\0_native\0_base\0'
  seg=struct.pack('<II16s4Q4I',0x19,72,b'__DATA_CONST',self.base,len(data),0,len(data),7,3,0,0)
  sym=struct.pack('<6I',2,24,0x3000,2,0x3100,len(strings))
  head=struct.pack('<8I',0xfeedfacf,0x100000c,0,2,2,96,0,0)+seg+sym;data[:len(head)]=head
  data[0x3100:0x3100+len(strings)]=strings
  struct.pack_into('<IBBHQ',data,0x3000,1,0xf,1,0,self.base+0x2800)
  struct.pack_into('<IBBHQ',data,0x3010,9,3,0,0,self.base+0x2900)
  struct.pack_into('<358Q',data,0x110,*([self.base+0x2800]*358))
  struct.pack_into('<207Q',data,0x1110,*([self.base+0x2800]*207));self.image.write_bytes(data)
  self.plan=dict(candidate_sha256=hashlib.sha256(data).hexdigest(),original_sha256='donor',slide=-0x1000000,extents=[dict(module='com.apple.iokit.IOHIDFamily',va=self.base,size=0x4000)])
  self.put('kernel.json',self.plan)
  self.audit=dict(original_sha256='donor',legacy_vptr=hex(self.base+0x110),methods=[dict(slot=i,address='0',kernel_names=['_native']) for i in range(358)])
  self.put('build/display-analysis/mobile-graphics-legacy-abi.json',self.audit)
  self.report=dict(donor_sha256='donor',final_verification_required=True,bindings={'_base':hex(self.base+0x2900)})
  self.put('build/native-legacy-display/build-report.json',self.report)
  self.hid=dict(donor_sha256='donor',vptr=self.base+0x1110,methods=[dict(address=0,kernel_names=['_native']) for i in range(207)],bindings={'_base':self.base+0x2900})
  self.put('build/sheng-hid-input/abi-audit.json',self.hid)
 def put(self,path,data):
  p=self.root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data))
 def test_valid(self):
  with patch.object(v.subprocess,'run') as run:
   v.verify(self.image);run.assert_called_once()
 def test_wrong_donor(self):
  self.plan['original_sha256']='other';self.put('kernel.json',self.plan)
  with self.assertRaisesRegex(ValueError,'provenance'):v.verify(self.image)
 def test_wrong_slide(self):
  self.plan['slide']=0;self.put('kernel.json',self.plan)
  with self.assertRaisesRegex(ValueError,'provenance'):v.verify(self.image)
 def test_slot_mismatch(self):
  self.audit['methods'][0]['kernel_names']=['_base'];self.put('build/display-analysis/mobile-graphics-legacy-abi.json',self.audit)
  with self.assertRaisesRegex(ValueError,'display slot'):v.verify(self.image)
 def test_binding_mismatch(self):
  self.report['bindings']['_base']=hex(self.base+0x2904);self.put('build/native-legacy-display/build-report.json',self.report)
  with self.assertRaisesRegex(ValueError,'display import'):v.verify(self.image)
 def test_hid_mismatch(self):
  self.hid['methods'][0]['kernel_names']=['_base'];self.put('build/sheng-hid-input/abi-audit.json',self.hid)
  with self.assertRaisesRegex(ValueError,'HID slot'):v.verify(self.image)
 def test_missing_hid(self):
  (self.root/'build/sheng-hid-input/abi-audit.json').unlink()
  with self.assertRaises(FileNotFoundError):v.verify(self.image)
if __name__=='__main__':unittest.main()
