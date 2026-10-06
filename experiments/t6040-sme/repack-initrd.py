#!/usr/bin/env python3
"""Build an isolated SME trial initrd without replacing installed package files."""
import argparse, gzip, hashlib, json, stat
from pathlib import Path

RELEASE = '7.1.3-m4rch-sme'

def parse(data):
    offset=0; items=[]
    while True:
        if data[offset:offset+6] != b'070701': raise ValueError('Expected newc')
        head=data[offset:offset+110]
        fields=[int(head[6+i*8:14+i*8],16) for i in range(13)]
        end=offset+110+fields[11]; name=data[offset+110:end]
        if not name.endswith(b'\0'): raise ValueError('Invalid name')
        start=(end+3)&~3; body=data[start:start+fields[6]]
        if len(body)!=fields[6]: raise ValueError('Truncated member')
        offset=(start+fields[6]+3)&~3; items.append((name,fields,body))
        if name==b'TRAILER!!!\0': return items,offset

def encode(items):
    result=bytearray()
    for name,fields,body in items:
        fields=fields.copy(); fields[6]=len(body); fields[11]=len(name)
        result+=b'070701'+''.join(f'{n:08x}' for n in fields).encode()+name
        result+=b'\0'*(-len(result)%4); result+=body; result+=b'\0'*(-len(result)%4)
    return bytes(result)

def repack(old,root):
    _,end=parse(old); z=old.find(b'\x1f\x8b\x08',end)
    if z<end or old[end:z].strip(b'\0'): raise ValueError('Expected early cpio and gzip')
    raw=gzip.decompress(old[z:]); items,used=parse(raw)
    if raw[used:].strip(b'\0'): raise ValueError('Unexpected suffix')
    tree=root/'lib/modules'/RELEASE
    files=sorted(p for p in tree.rglob('*') if p.is_file() and not p.is_symlink())
    if not any(p.suffix=='.ko' for p in files): raise ValueError('No matching modules')
    manifest=''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(tree))+'\n' for p in files)
    token=hashlib.sha256(manifest.encode()).hexdigest()
    injection=f'''# SME trial: install only its separate, non-pacman module directory.
[ "$(uname -r)" = "{RELEASE}" ] || stop 'Wrong SME kernel'
trial=/newroot/usr/lib/modules/{RELEASE}
for parent in /newroot/usr /newroot/usr/lib /newroot/usr/lib/modules; do
    [ -d "$parent" ] && [ ! -L "$parent" ] || stop 'Unsafe module parent'
done
[ ! -L "$trial" ] || stop 'Symlink at SME module destination'
if [ -e "$trial" ]; then
    [ "$(cat "$trial/.m4rch-trial" 2>/dev/null)" = {token} ] || stop 'Different SME trial already installed'
else
    staged=$(mktemp -d /newroot/usr/lib/modules/.sme-XXXXXX) || stop 'Cannot stage SME modules'
    /bin/busybox cp -a /sme-modules/. "$staged/" || stop 'Cannot copy SME modules'
    (cd "$staged" && /bin/busybox sha256sum -c /sme-checksums) || stop 'SME module verification failed'
    printf '%s\\n' {token} > "$staged/.m4rch-trial"
    sync
    mv "$staged" "$trial" || stop 'Cannot publish SME modules'
    sync
fi
'''
    result=[]
    for name,fields,body in items[:-1]:
        path=name[:-1].decode()
        if path.startswith('usr/lib/modules/'): continue
        if path=='etc/sdboot.conf': body=body.replace(b'7.1.3-m4rch',RELEASE.encode())
        if path=='init':
            key=b'# The installed kernel package owns its module tree.'
            if body.count(key)!=1: raise ValueError('Unexpected init layout')
            body=body.replace(key,injection.encode()+b'\n'+key)
        result.append((name,fields,body))
    def add(path,mode,body=b''):
        fields=[len(result)+1,mode,0,0,1,0,len(body),0,0,0,0,len(path.encode())+1,0]
        result.append((path.encode()+b'\0',fields,body))
    add('sme-modules',stat.S_IFDIR|0o755)
    for p in sorted(tree.rglob('*')):
        if p.is_symlink(): continue
        dest='sme-modules/'+str(p.relative_to(tree))
        if p.is_dir(): add(dest,stat.S_IFDIR|0o755)
        elif p.is_file(): add(dest,stat.S_IFREG|0o644,p.read_bytes())
    add('sme-checksums',stat.S_IFREG|0o644,manifest.encode())
    result.append(items[-1]); encoded=encode(result); parse(encoded)
    return old[:z]+gzip.compress(encoded,mtime=0),token,len(files)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('original','modules_root','output'): p.add_argument(key,type=Path)
    a=p.parse_args(); result,token,count=repack(a.original.read_bytes(),a.modules_root)
    with a.output.open('xb') as f:f.write(result)
    print(json.dumps({'release':RELEASE,'module_tree_token':token,'module_files':count,'sha256':hashlib.sha256(result).hexdigest()},indent=2))
if __name__=='__main__':main()
