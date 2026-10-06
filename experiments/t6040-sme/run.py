#!/usr/bin/env python3
"""HWCAP-gated upstream SME state tests on every T6040 core."""
import hashlib,json,os,re,shutil,signal,struct,subprocess,tempfile,time
from pathlib import Path
KIT=Path(__file__).resolve().parent
PARAM=Path('/sys/module/cpuidle_apple/parameters/saved_wfi')
if not PARAM.exists():PARAM=PARAM.with_name('experimental_t6040_idle_continuous')
PROGRESS=PARAM.with_name('saved_wfi_progress' if PARAM.name=='saved_wfi' else 'experimental_t6040_idle_continuous_progress')

def build_id():
    data=Path('/sys/kernel/notes').read_bytes(); offset=0
    while offset+12<=len(data):
        n,d,t=struct.unpack_from('<III',data,offset);offset+=12
        name=data[offset:offset+n];offset+=(n+3)&~3
        desc=data[offset:offset+d];offset+=(d+3)&~3
        if name==b'GNU\0' and t==3:return desc.hex()
    raise ValueError('Missing build ID')

def verify():
    receipt=json.loads((KIT/'BUILD.JSN').read_text())
    if os.geteuid()!=0:raise ValueError('Run with sudo')
    if os.uname().release!=receipt['release'] or build_id()!=receipt['build_id']:raise ValueError('Wrong running kernel')
    compatible=Path('/proc/device-tree/compatible').read_bytes().split(b'\0')
    if b'apple,j614s' not in compatible:raise ValueError('Wrong board')
    for line in (KIT/'SUMS.TXT').read_text().splitlines():
        digest,name=line.split('  ',1)
        if '/' in name or name in ('.','..'):raise ValueError('Unsafe manifest')
        if hashlib.sha256((KIT/name).read_bytes()).hexdigest()!=digest:raise ValueError('Kit checksum mismatch: '+name)
    return receipt

def progress(text):
    values={int(c):int(n) for c,n in re.findall(r"cpu(\d+) attempts=\d+ completed=(\d+)",text)}
    if set(values)!=set(range(12)):raise ValueError("Incomplete idle progress")
    return values

def test(binary,cpu,output):
    procs=[]; handles=[]
    try:
        for i in range(2):
            path=output/f'{binary.name}-cpu{cpu}-{i}.log';f=path.open('wb');handles.append(f)
            procs.append(subprocess.Popen(['taskset','-c',str(cpu),str(binary)],stdout=f,stderr=subprocess.STDOUT))
        time.sleep(3)
    finally:
        for p in procs:
            if p.poll() is None:p.send_signal(signal.SIGTERM)
        for p in procs:
            try:p.wait(timeout=5)
            except subprocess.TimeoutExpired:p.kill();p.wait()
        for f in handles:f.close()
    for i,p in enumerate(procs):
        text=(output/f'{binary.name}-cpu{cpu}-{i}.log').read_text()
        match=re.search(r'no error, iterations=(\d+)',text)
        if p.returncode!=0 or not match or int(match[1])<1:raise ValueError(f'{binary.name} failed on CPU{cpu}: {text}')

def main():
    receipt=verify()
    output=Path(tempfile.mkdtemp(prefix='m4rch-sme-',dir='/var/tmp'))
    binaries=output/'bin';binaries.mkdir()
    for name in ('PROBE','ZAORIG','ZTORIG','SSVE','ZASLEEP','ZTSLEEP'):
        shutil.copyfile(KIT/name,binaries/name);(binaries/name).chmod(0o700)
    subprocess.run(['journalctl','-b','-k','--no-pager'],stdout=(output/'journal-before.txt').open('w'),check=True)
    started=time.strftime('%Y-%m-%d %H:%M:%S')
    original=PARAM.read_text().strip()
    result={'receipt':receipt,'output':str(output),'passed':False,'phases':[]}
    try:
        PARAM.write_text('0\n')
        for cpu in range(12):
            probe=json.loads(subprocess.check_output(['taskset','-c',str(cpu),str(binaries/'PROBE')]))
            (output/f'probe-cpu{cpu}.json').write_text(json.dumps(probe,indent=2))
            if not probe['sme'] or probe['sme_vl_bytes']<16:raise ValueError(f'SME unavailable on CPU{cpu}; no SME instruction tests attempted')
        for enabled in (False,True):
            PARAM.write_text('1\n' if enabled else '0\n')
            phase=output/('idle-on' if enabled else 'idle-off');phase.mkdir()
            before=PROGRESS.read_text()
            (phase/'progress-before.txt').write_text(before)
            for cpu in (4,5,0,1,2,3,6,7,8,9,10,11):
                caps=json.loads((output/f'probe-cpu{cpu}.json').read_text())
                names=['ZASLEEP' if enabled else 'ZAORIG']
                if caps['sme2']:names.append('ZTSLEEP' if enabled else 'ZTORIG')
                if not enabled:names.append('SSVE')
                for name in names:test(binaries/name,cpu,phase)
            after=PROGRESS.read_text()
            (phase/'progress-after.txt').write_text(after)
            if enabled:
                a,b=progress(before),progress(after)
                if any(b[c]<=a[c] for c in range(12)):raise ValueError('No saved-WFI returns on one or more cores')
            result['phases'].append(str(phase))
        journal=subprocess.check_output(['journalctl','-b','-k','--since',started,'--no-pager'],text=True)
        (output/'journal-delta.txt').write_text(journal)
        if re.search(r'(?i)Oops:|BUG:|Call trace:|undefined instruction|kernel panic',journal):raise ValueError('New kernel fault; inspect journal')
        result['passed']=True
    except BaseException as e:
        PARAM.write_text(('1' if original in ('Y','1') else '0')+'\n');result['error']=str(e);raise
    finally:
        (output/'result.json').write_text(json.dumps(result,indent=2));print('Evidence:',output,flush=True)
        subprocess.run(['chown','-R',os.environ.get('SUDO_UID','0')+':'+os.environ.get('SUDO_GID','0'),str(output)],check=False)
if __name__=='__main__':main()
