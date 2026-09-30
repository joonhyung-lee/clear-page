"""Validate every published replay's binary references against the native schema."""
import json
from pathlib import Path
import tempfile
from recording_io import read_recording, validate_binary_arrays

root=Path(__file__).resolve().parents[1]
count=0
for file in sorted((root/'assets/recordings').glob('*.hex.js')):
    encoded=bytes.fromhex(json.loads(file.read_text().rsplit(' = ',1)[1].rstrip(';\n')))
    with tempfile.NamedTemporaryFile() as temporary:
        temporary.write(encoded);temporary.flush()
        record,buffers=read_recording(temporary.name)
    validate_binary_arrays(record,buffers,file.name)
    binary=file.with_name(file.name.removesuffix('.hex.js')+'.viser')
    if binary.exists():assert binary.read_bytes()==encoded, f'Stale binary replay: {binary.name}'
    count+=1
print('PASS',count,'published replay array schemas and matching binary assets')
