from pathlib import Path
import copy, hashlib, json, shutil, struct, sys, zipfile

src=Path(sys.argv[1]); images=Path(sys.argv[2]); out=Path(sys.argv[3]); receipt=json.loads((src.parent/'receipt.json').read_text())
def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  while b:=f.read(4*1024*1024): h.update(b)
 return h.hexdigest()
if digest(src)!=receipt['candidate_payload_sha256']:
 raise SystemExit('stage-2 candidate digest mismatch')
if out.exists(): raise SystemExit('refusing existing output')
with zipfile.ZipFile(src) as old, zipfile.ZipFile(out,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as new:
 for item in old.infolist():
  entry=copy.copy(item)
  extra=entry.extra; fields=[]
  while extra:
   if len(extra)<4: raise ValueError('truncated ZIP extra field')
   tag,length=struct.unpack_from('<HH',extra)
   if len(extra)<4+length: raise ValueError('truncated ZIP extra value')
   if tag!=1: fields.append(extra[:4+length])
   extra=extra[4+length:]
  entry.extra=b''.join(fields)
  if item.filename in ('root.img','boot.img'):
   source=(images/item.filename).open('rb')
  else: source=old.open(item)
  with source, new.open(entry,'w',force_zip64=True) as dest: shutil.copyfileobj(source,dest,1024*1024)
  print(item.filename, flush=True)
print('payload_sha256',digest(out),flush=True)
