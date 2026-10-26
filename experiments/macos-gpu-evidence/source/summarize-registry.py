from pathlib import Path
import plistlib,re,json,hashlib
r=Path(__file__).resolve().parents[1];pattern=re.compile('AGX|RTBuddy|DCP|IOFramebuffer|AppleCLCD|IOMobileFramebuffer|IOGPU',re.I)
def safe(v):
 if isinstance(v,bytes):return {'bytes':len(v),'hex':v.hex()} if len(v)<1024 else {'bytes':len(v),'sha256':hashlib.sha256(v).hexdigest()}
 if isinstance(v,dict):return {str(k):safe(x) for k,x in v.items()}
 if isinstance(v,list):return [safe(x) for x in v]
 return v if isinstance(v,(str,int,float,bool)) or v is None else str(v)
for phase in ['idle','workload','post-idle']:
 forest=plistlib.loads((r/'captures'/phase/'ioservice.plist').read_bytes());entries=[]
 def walk(n,parent='',parent_id=None):
  name=n.get('IORegistryEntryName','?');path=parent+'/'+name;klass=n.get('IOObjectClass',n.get('IOClass',''))
  if pattern.search(str(name)+' '+str(klass)):
   entries.append({'path':path,'registry_id':n.get('IORegistryEntryID'),'parent_path':parent,'parent_registry_id':parent_id,'class':klass,'properties':safe({k:v for k,v in n.items() if k!='IORegistryEntryChildren'})})
  for c in n.get('IORegistryEntryChildren',[]):walk(c,path,n.get('IORegistryEntryID'))
 for n in ([forest] if isinstance(forest,dict) else forest):walk(n)
 (r/'captures'/phase/'gpu-display-attachment-graph.json').write_text(json.dumps(entries,indent=2)+'\n');print(phase,len(entries),'GPU/display related registry entries')
