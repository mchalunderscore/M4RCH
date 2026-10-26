#!/usr/bin/env python3
"""Add persistent handoff evidence to the existing integrated DCP runtime."""
import argparse,json,shutil,subprocess
from pathlib import Path
KIT=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
r=a.root;o=a.output
script=r/'aurora-runtime.sh';s=script.read_text();anchor="echo 'AUDP001 J614s internal-panel DCP + accelerated desktop candidate; speakers excluded'"
assert s.count(anchor)==1
s=s.replace(anchor,'''echo 'AUDP001 r4 handoff-corrected integrated DCP candidate; speakers excluded'
echo 'DCP004: persistent loader/bridge admission evidence:'
for property in m4rch,dcp-summary m4rch,dcp-identity m4rch,dcp-observed-uuid m4rch,dcp-dart-0 m4rch,dcp-dart-1 m4rch,dcp-dart-2 m4rch,dcp-bridge-summary; do
    path=/sys/firmware/devicetree/base/chosen/$property
    if [ -r "$path" ]; then
        printf '%s: ' "$property"
        tr -d '\\000' <"$path"
        printf '\\n'
    fi
done''');script.write_text(s)
shutil.copyfile(KIT/'collect-display.sh',r/'collect-display.sh')
profile=json.loads((r/'gpu16-profile.json').read_text());profile.update({'revision':4,
 'kernel_release':'7.3.0-m4rch-dcp003','loader_revision':'DCP004',
 'changes':['T8110 TTBR address-field mask matches production driver','persistent loader/bridge refusal stages and live data','reduced atomic DRM log noise'],
 'native_boot_tested':False,'prior_native_result':'r3 used simpledrm; no native DCP takeover occurred'})
(r/'gpu16-profile.json').write_text(json.dumps(profile,indent=2)+'\n')
(o/'runtime-profile.json').write_text(json.dumps(profile,indent=2)+'\n')
for f in [script,r/'collect-display.sh',r/'init']:subprocess.run(['/bin/sh','-n',str(f)],check=True)
print('Prepared revision-4 integrated runtime with persistent pre-Linux evidence')
