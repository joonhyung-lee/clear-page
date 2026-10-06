"""Check publication limits, anonymous URL policy and download behavior offline."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('publish_page', ROOT/'scripts/publish_page.py')
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)
for url in ['http://anonymous.example/model.zip', 'https://user:secret@localhost/model.zip',
            'https://github.com/account/repo/releases/model.zip', 'https://account.github.io/model.zip',
            'https://anonymous.example/private_person/model.zip']:
    try:
        publisher.check_url(url, ['private_person'])
    except ValueError:
        pass
    else:
        raise AssertionError('Unsafe download URL accepted')
assert publisher.check_url('https://anonymous.example/models/model.zip', [])
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    large = root/'large.bin'
    with large.open('wb') as stream:
        stream.truncate(publisher.LIMIT+1)
    with patch.object(publisher, 'ROOT', root):
        try:
            publisher.check_payloads([large])
        except ValueError:
            pass
        else:
            raise AssertionError('Oversized Git file accepted')
javascript = r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('code/code.js','utf8');
const a=source.indexOf("  for(const node of document.querySelectorAll('[data-archive]'))");
const b=source.indexOf('  function formatBytes',a);assert(a>=0&&b>a);
for(const [hostname,configured,expected] of [
 ['localhost',null,'../assets/code-downloads/clear-pretrained.zip?v=abc'],
 ['anonymous.4open.science',null,null],
 ['anonymous.4open.science','https://anonymous.example/model.zip','https://anonymous.example/model.zip']]){
 const link={attrs:{},setAttribute(k,v){this.attrs[k]=v;},removeAttribute(k){delete this.attrs[k];if(k==='href')delete this.href;}};
 const node={dataset:{archive:'checkpoints'},closest(){return link;}};
 vm.runInNewContext(source.slice(a,b),{
  document:{querySelectorAll(){return [node];}},location:{hostname,protocol:'https:'},
  window:{CLEAR_CODE_ARCHIVES:{checkpoints:{url:'../assets/code-downloads/clear-pretrained.zip',sha256:'abc',bytes:1800000000,files:153}},CLEAR_CODE_DOWNLOADS:{checkpoints:configured}}
 });
 assert.equal(link.href,expected??undefined);
 if(expected){assert.equal(link.referrerPolicy,'no-referrer');assert(!link.attrs['aria-disabled']);}
 else{assert.equal(link.attrs['aria-disabled'],'true');assert(node.textContent.includes('pending'));}
}
console.log('PASS local archive, unpublished hosted archive, and anonymous external link behavior');
'''
subprocess.run(['node','-e',javascript],cwd=ROOT,check=True)
print('PASS oversized payload rejection and anonymous URL constraints')
