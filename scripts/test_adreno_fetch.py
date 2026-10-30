import importlib.util,os,unittest
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('fetch_adreno',Path(__file__).with_name('fetch-adreno-inputs.py'))
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
class HeadersTest(unittest.TestCase):
 def test_github_api_authenticated(self):
  with patch.dict(os.environ,{'GITHUB_TOKEN':'synthetic-test-token'}):
   self.assertEqual(f.request_headers('https://api.github.com/repos/a/b/git/blobs/123')['Authorization'],'Bearer synthetic-test-token')
 def test_other_destinations_receive_no_token(self):
  with patch.dict(os.environ,{'GITHUB_TOKEN':'synthetic-test-token'}):
   for url in ['https://raw.githubusercontent.com/a/b','https://example.org','http://api.github.com/repos/a/b','https://api.github.com.example.org','https://api.github.com:444/repos/a/b']:
    with self.subTest(url=url):self.assertNotIn('Authorization',f.request_headers(url))
 def test_missing_token(self):
  with patch.dict(os.environ,{},clear=True):
   self.assertNotIn('Authorization',f.request_headers('https://api.github.com/repos/a/b'))
if __name__=='__main__':unittest.main()
