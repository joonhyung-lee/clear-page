"""Check client JavaScript after applying supplied hosting redaction patterns.

Patterns are command-line inputs so personal anonymization settings are never
stored in the public repository. This checks syntax only, not browser behavior.
"""
import argparse
from pathlib import Path
import re
import subprocess
import tempfile

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--term',action='append',required=True)
a=p.parse_args()
patterns=[re.compile(value) for value in a.term]
root=Path(__file__).resolve().parents[1]
changed=0
with tempfile.TemporaryDirectory(prefix='redaction-syntax-') as directory:
    for path in sorted((root/'assets').rglob('*.js')):
        source=path.read_text()
        redacted=source
        for i,pattern in enumerate(patterns):
            redacted=pattern.sub('XXXX-['+str(i)+']',redacted)
        if redacted==source:
            continue
        changed+=1
        temporary=Path(directory)/'client.js'
        temporary.write_text(redacted)
        result=subprocess.run(['node','--check',str(temporary)],capture_output=True,text=True)
        assert result.returncode==0, 'Redaction breaks JavaScript syntax: '+str(path.relative_to(root))
print('PASS supplied redactions preserve JavaScript syntax in',changed,'affected client files')
