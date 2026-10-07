# SPDX-License-Identifier: GPL-2.0-only
"""Read only the trial's owned-object sysfs snapshot during bounded observation."""
import hashlib,json,time
from pathlib import Path
def observe(path,out,layout,done,seconds=45):
 started=time.monotonic();frames=[];previous=None;errors=[];out=Path(out);out.mkdir(exist_ok=True)
 while not done.is_set() and time.monotonic()-started<seconds:
  if not path.exists():done.wait(.1);continue
  try:
   data=path.read_bytes()
   if len(data)!=layout['arena_bytes']:raise ValueError('Live graph extent changed')
   changes=[]
   if previous is not None:
    for obj in layout['objects']:
     start=obj['arena_offset'];end=start+obj['reserved_bytes']
     count=sum(x!=y for x,y in zip(previous[start:end],data[start:end]))
     if count:changes.append({'name':obj['name'],'changed_bytes':count})
   frame={'elapsed_seconds':round(time.monotonic()-started,3),'sha256':hashlib.sha256(data).hexdigest(),'changed_objects':changes}
   if previous is None or data!=previous:
    frame['snapshot_file']=f'{len(frames):03}.bin';(out/frame['snapshot_file']).write_bytes(data)
   frames.append(frame);previous=data
  except (OSError,ValueError) as error:errors.append(str(error));break
  done.wait(1)
 result={'scope':'Non-atomic live snapshots of owned trial RAM only; no register scan or submission','frames':frames,'errors':errors}
 (out/'observations.json').write_text(json.dumps(result,indent=2)+'\n')
 return result
