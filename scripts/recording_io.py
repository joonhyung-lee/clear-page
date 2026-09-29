"""Read and write Viser's aligned binary recording format without changing arrays."""
import json
from pathlib import Path
import msgpack,zstandard

def read_recording(path):
 encoded=Path(path).read_bytes();raw=zstandard.ZstdDecompressor().decompress(encoded[8:]);assert int.from_bytes(encoded[:8],'little')==len(raw)
 size=int.from_bytes(raw[:8],'little');record=msgpack.unpackb(raw[8:8+size],raw=False);offset=8+size;buffers=[]
 for length in record['binaryBufferLengths']:
  offset=(offset+7)//8*8;buffers.append(raw[offset:offset+length]);offset+=length
 assert offset==len(raw)
 return record,buffers

def write_recording(path,record,buffers):
 path=Path(path);record['binaryBufferLengths']=[len(b) for b in buffers];packed=msgpack.packb(record,use_bin_type=True);raw=bytearray(len(packed).to_bytes(8,'little')+packed)
 for buffer in buffers:raw.extend(b'\0'*((-len(raw))%8));raw.extend(buffer)
 path.write_bytes(len(raw).to_bytes(8,'little')+zstandard.ZstdCompressor(level=12).compress(raw))
 path.with_suffix('.hex.js').write_text('window.CLEAR_RECORDINGS = window.CLEAR_RECORDINGS || {};\nwindow.CLEAR_RECORDINGS['+json.dumps(path.stem)+'] = '+json.dumps(path.read_bytes().hex())+';\n')
