"""Keep actual Gaussian flow states intact before displaying geometric refinement.

The first six seconds are the saved raw inference replay, byte for byte at the
message/buffer level. Refinement is a separate final state, held for two seconds.
No smoothing or collision projection is applied to the Gaussian initialization.
"""
import copy
from pathlib import Path
from recording_io import read_recording, write_recording, compact_buffers

root=Path(__file__).resolve().parents[1]
for sample in range(4):
    prefix=root/f'assets/recordings/method-flow-{sample}'
    raw,buffers=read_recording(str(prefix)+'-raw.viser')
    refined,other=read_recording(str(prefix)+'-refined.viser')
    record=copy.deepcopy(raw)
    offset=len(buffers)
    def remap(value):
        if isinstance(value,dict):
            if '__binary_index' in value:value['__binary_index']+=offset
            else:
                for child in value.values():remap(child)
        elif isinstance(value,(list,tuple)):
            for child in value:remap(child)
    final=max(t for t,m in refined['messages'])
    for t,message in refined['messages']:
        if abs(t-final)>1e-8:continue
        assert message['type'] in ['SceneNodeUpdateMessage','SetPositionMessage','SetOrientationMessage']
        message=copy.deepcopy(message);remap(message)
        record['messages'].append([6.,message])
    record['durationSeconds']=8.
    assert record['messages'][:len(raw['messages'])]==raw['messages']
    record,packed=compact_buffers(record,buffers+other)
    write_recording(str(prefix)+'-pipeline.viser',record,packed)
    print('Built',sample,'raw Gaussian integration followed by final geometric refinement')
