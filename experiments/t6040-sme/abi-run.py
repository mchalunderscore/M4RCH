#!/usr/bin/env python3
"""Run exact upstream SME/TPIDR2 ABI tests against the guarded native kernel."""
import argparse,importlib.util,importlib.machinery,json,os,resource,shutil,subprocess,tempfile
from pathlib import Path
KIT=Path(__file__).resolve().parent
loader=importlib.machinery.SourceFileLoader('guard',str(KIT/'GUARD.PY')); s=importlib.util.spec_from_loader('guard',loader);guard=importlib.util.module_from_spec(s);s.loader.exec_module(guard)
TESTS=('TPIDRABI','TPIDRRES','TPIDRFRM','SMEVL','SMENOSM','SMENSTR','SMEZA','SMEBADVL')
def classify(status,text):
    if status==4:return 'skip'
    tap=[line for line in text.splitlines() if line.startswith('ok ')]
    if status==0 and tap and all('# SKIP' in line.upper() for line in tap):return 'skip'
    if status!=0 or '\nnot ok' in '\n'+text:return 'fail'
    return 'pass'
def main():
    p=argparse.ArgumentParser();p.add_argument('--with-idle',action='store_true',help='Only after the focused SSVE signal diagnosis passes');a=p.parse_args()
    guard.verify();resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    out=Path(tempfile.mkdtemp(prefix='m4rch-sme-abi-',dir='/var/tmp'));bins=out/'bin';bins.mkdir()
    for name in (*TESTS,'PROBE'):
        shutil.copyfile(KIT/name,bins/name);(bins/name).chmod(0o700)
    rows=[];passed=False;original=guard.PARAM.read_text().strip()
    try:
        caps=json.loads(subprocess.check_output([str(bins/'PROBE')]))
        (out/'probe.json').write_text(json.dumps(caps,indent=2))
        if not caps['sme'] or caps['sme_vl_bytes']<16:raise ValueError('SME not exposed')
        for enabled in ([False,True] if a.with_idle else [False]):
            guard.PARAM.write_text('1\n' if enabled else '0\n');phase=out/('idle-on' if enabled else 'idle-off');phase.mkdir()
            before=guard.PROGRESS.read_text();(phase/'before.txt').write_text(before)
            for cpu in range(12):
                for name in TESTS if cpu in (4,5) else TESTS[:3]:
                    with (phase/f'{name}-cpu{cpu}.log').open('w') as f:
                        try:run=subprocess.run(['taskset','-c',str(cpu),str(bins/name)],stdout=f,stderr=subprocess.STDOUT,timeout=20);status=run.returncode
                        except subprocess.TimeoutExpired:status=124
                    text=(phase/f'{name}-cpu{cpu}.log').read_text();result=classify(status,text)
                    rows.append({'test':name,'cpu':cpu,'idle_enabled':enabled,'status':status,'result':result})
                    if result=='fail':raise ValueError(f'{name} CPU{cpu} failed ({status}); inspect log')
                    if result=='skip' and name.startswith('TPIDR'):raise ValueError('Required TPIDR2 coverage skipped')
            after=guard.PROGRESS.read_text();(phase/'after.txt').write_text(after)
            if enabled:
                b,c=guard.progress(before),guard.progress(after)
                if any(c[n]<=b[n] for n in range(12)):raise ValueError('Missing all-core saved-WFI returns')
        passed=True
    finally:
        guard.PARAM.write_text(('1' if original in ('Y','1') else '0')+'\n')
        (out/'result.json').write_text(json.dumps({'passed':passed,'skipped_tests_are_not_coverage':True,'rows':rows,'with_idle':a.with_idle},indent=2))
        with (out/'journal.txt').open('w') as f:subprocess.run(['journalctl','-b','-k','--no-pager'],stdout=f)
        subprocess.run(['chown','-R',os.environ.get('SUDO_UID','0')+':'+os.environ.get('SUDO_GID','0'),str(out)])
        print('Evidence:',out)
if __name__=='__main__':main()
