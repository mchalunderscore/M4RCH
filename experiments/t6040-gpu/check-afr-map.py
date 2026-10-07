#!/usr/bin/env python3
"""Pin AFR constructor provenance without loading or executing Apple code."""
import argparse, hashlib, json, struct
from pathlib import Path
SHA='3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e'
WORDS={0xa7b3c:0x528b7c08,0xa7b40:0x8b080017,
       0xa7c40:0x52a00088,0xa7c44:0xb9020ae8,0xa7c48:0x52800088,
       0xa7c54:0x290022e9,0xa7c58:0xd2b16008,0xa7c5c:0xf2c00048,
       0xa7c60:0xf92df668,0xa7c64:0xf0ff3a09,0xa7c68:0x3dc38520,
       0xa7c6c:0x3d96fe60,0xa7c70:0xb26b0508,0xa7c74:0xf92e0268}
def verify(data):
 if hashlib.sha256(data).hexdigest()!=SHA:raise ValueError('Wrong Apple binary')
 for off,word in WORDS.items():
  if struct.unpack_from('<I',data,off)[0]!=word:raise ValueError(f'Changed AFR instruction at {off:#x}')
 if struct.unpack_from('<QQ',data,0xe60)!=(0x28b200000,0x28b400000):raise ValueError('Changed AFR constants')
 return {'binary_sha256':SHA,'instruction_words_verified':len(WORDS),'constant_pair_verified':True}
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('macho',type=Path);a=p.parse_args()
 print(json.dumps(verify(a.macho.read_bytes()),indent=2))
