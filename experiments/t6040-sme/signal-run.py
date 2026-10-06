#!/usr/bin/env python3
"""Distinguish SSVE SIGILL from a streaming signal-return mismatch."""
import importlib.util,importlib.machinery,json,os,re,resource,shutil,signal,subprocess,tempfile,time
from pathlib import Path
KIT=Path(__file__).resolve().parent
loader=importlib.machinery.SourceFileLoader('guard',str(KIT/'GUARD.PY')); spec=importlib.util.spec_from_loader('guard',loader);guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)

def exercise(binary,cpu,path):
    with path.open('wb') as log:
        p=subprocess.Popen(['taskset','-c',str(cpu),str(binary)],stdout=log,stderr=subprocess.STDOUT)
        try:
            end=time.monotonic()+3
            while p.poll() is None and time.monotonic()<end:
                if path.stat().st_size and 'PID:' in path.read_text():p.send_signal(signal.SIGUSR1)
                time.sleep(.025)
        finally:
            if p.poll() is None:p.send_signal(signal.SIGTERM)
            try:p.wait(timeout=5)
            except subprocess.TimeoutExpired:p.kill();p.wait()
    text=path.read_text();match=re.search(r'no error, iterations=(\d+), signals=(\d+)',text)
    return {'binary':binary.name,'cpu':cpu,'returncode':p.returncode,'signal':-p.returncode if p.returncode<0 else None,'iterations':int(match[1]) if match else 0,'signals':int(match[2]) if match else 0,'passed':p.returncode==0 and bool(match) and int(match[1])>0 and int(match[2])>0}

def main():
    guard.verify();resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    out=Path(tempfile.mkdtemp(prefix='m4rch-sme-signals-',dir='/var/tmp'));bins=out/'bin';bins.mkdir()
    for name in ('SSVORIG','SSVNEON','SSVSTRM','PROBE'):
        shutil.copyfile(KIT/name,bins/name);(bins/name).chmod(0o700)
    results=[];success=False;original_switch=guard.PARAM.read_text().strip()
    try:
        guard.PARAM.write_text('0\n')
        caps=json.loads(subprocess.check_output([str(bins/'PROBE')]))
        (out/'probe.json').write_text(json.dumps(caps,indent=2))
        if not caps['sme'] or caps['sme_vl_bytes']<16:raise ValueError('SME unavailable')
        if caps['hwcap']&(1<<22):raise ValueError('Ordinary SVE exposed: this SME-only diagnostic is inappropriate')
        original=exercise(bins/'SSVORIG',4,out/'original-cpu4.log');results.append(original)
        # Explicit negative subprocess status distinguishes SIGILL from exit(4).
        if original['returncode']!=-signal.SIGILL:raise ValueError('Original did not reproduce SIGILL; inspect instead of assuming the cause')
        for enabled in (False,True):
            guard.PARAM.write_text('1\n' if enabled else '0\n')
            phase=out/('idle-on' if enabled else 'idle-off');phase.mkdir()
            before=guard.PROGRESS.read_text();(phase/'before.txt').write_text(before)
            for cpu in (4,5,0,1,2,3,6,7,8,9,10,11):
                for name in ('SSVNEON','SSVSTRM'):
                    row=exercise(bins/name,cpu,phase/f'{name}-cpu{cpu}.log');row['idle_enabled']=enabled;results.append(row)
                    if not row['passed']:raise ValueError(f'Signal integrity failure: {row}')
            after=guard.PROGRESS.read_text();(phase/'after.txt').write_text(after)
            if enabled:
                a,b=guard.progress(before),guard.progress(after)
                if any(b[c]<=a[c] for c in range(12)):raise ValueError('Missing WFI returns')
        success=True
    finally:
        if not success:guard.PARAM.write_text(('1' if original_switch in ('Y','1') else '0')+'\n')
        (out/'result.json').write_text(json.dumps({'passed':success,'workers':results},indent=2))
        with (out/'journal.txt').open('w') as f:subprocess.run(['journalctl','-b','-k','--no-pager'],stdout=f)
        subprocess.run(['chown','-R',os.environ.get('SUDO_UID','0')+':'+os.environ.get('SUDO_GID','0'),str(out)])
        print('Evidence:',out)
if __name__=='__main__':main()
