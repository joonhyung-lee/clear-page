"""Read and write Viser's aligned binary recording format without changing arrays."""
import json
from pathlib import Path
import msgpack,zstandard

def validate_binary_arrays(value,buffers,path='record'):
 """Reject references the native player cannot restore to typed arrays."""
 if isinstance(value,dict):
  if '__binary_index' in value:
   index=value['__binary_index']
   if not isinstance(index,int) or not 0<=index<len(buffers):
    raise ValueError(f'Invalid binary buffer index at {path}')
   dtype=value.get('dtype')
   widths={'<f2':2,'<f4':4,'<f8':8,'|u1':1,'<u2':2,'<u4':4,'|i1':1,'<i2':2,'<i4':4}
   if dtype not in widths:
    raise ValueError(f'Missing or unsupported native array dtype at {path}: {dtype}')
   if len(buffers[index]) % widths[dtype]:
    raise ValueError(f'Misaligned native array at {path}')
  else:
   for key,child in value.items():validate_binary_arrays(child,buffers,path+'.'+str(key))
 elif isinstance(value,(list,tuple)):
  for i,child in enumerate(value):validate_binary_arrays(child,buffers,path+f'[{i}]')

def compact_buffers(record,buffers):
 """Discard buffers no longer referenced after trimming scene messages."""
 result=[];indices={}
 def visit(value):
  if isinstance(value,dict):
   if '__binary_index' in value:
    old=value['__binary_index']
    if old not in indices:indices[old]=len(result);result.append(buffers[old])
    value['__binary_index']=indices[old]
   else:
    for child in value.values():visit(child)
  elif isinstance(value,(tuple,list)):
   for child in value:visit(child)
 visit(record)
 return record,result

def read_recording(path):
 encoded=Path(path).read_bytes();raw=zstandard.ZstdDecompressor().decompress(encoded[8:]);assert int.from_bytes(encoded[:8],'little')==len(raw)
 size=int.from_bytes(raw[:8],'little');record=msgpack.unpackb(raw[8:8+size],raw=False);offset=8+size;buffers=[]
 for length in record['binaryBufferLengths']:
  offset=(offset+7)//8*8;buffers.append(raw[offset:offset+length]);offset+=length
 assert offset==len(raw)
 return record,buffers

def write_recording(path,record,buffers):
 validate_binary_arrays(record,buffers)
 path=Path(path);record['binaryBufferLengths']=[len(b) for b in buffers];packed=msgpack.packb(record,use_bin_type=True);raw=bytearray(len(packed).to_bytes(8,'little')+packed)
 for buffer in buffers:raw.extend(b'\0'*((-len(raw))%8));raw.extend(buffer)
 path.write_bytes(len(raw).to_bytes(8,'little')+zstandard.ZstdCompressor(level=12).compress(raw))
 path.with_suffix('.hex.js').write_text('window.CLEAR_RECORDINGS = window.CLEAR_RECORDINGS || {};\nwindow.CLEAR_RECORDINGS['+json.dumps(path.stem)+'] = '+json.dumps(path.read_bytes().hex())+';\n')
