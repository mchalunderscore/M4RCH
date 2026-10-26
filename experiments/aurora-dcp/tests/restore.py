#!/usr/bin/env python3
"""Exercise restoration across every old/new pair without touching the real ESP."""
import hashlib
import importlib.util
import json
from pathlib import Path
import plistlib
import sys
import tempfile

KIT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('candidate_restore',KIT/'restore.py')
module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
sha=lambda data:hashlib.sha256(data).hexdigest()

with tempfile.TemporaryDirectory(prefix='aurora-dcp-restore-') as directory:
    esp=Path(directory); (esp/'AUDP001').mkdir(); (esp/'grub').mkdir()
    module.subprocess.check_output=lambda args:plistlib.dumps({'DiskUUID':'5FDB35C6-3A66-416D-8358-6555FD99FCC5','MountPoint':str(esp)})
    original_run=module.subprocess.run
    module.subprocess.run=lambda args,**kwargs:None if args==['sync'] else original_run(args,**kwargs)
    recipe={}
    for name,label in [('boot.bin','previous.boot.bin'),('grub/grub.cfg','previous.grub.cfg')]:
        native=('native '+name).encode(); old=('r1 '+name).encode(); new=('r2 '+name).encode()
        (esp/'AUDP001'/label).write_bytes(native)
        recipe[name]={'backup':label,'before_sha256':sha(native),'candidate_sha256':sha(new),'previous_candidate_sha256':[sha(old)]}
    (esp/'AUDP001/rollback.json').write_text(json.dumps(recipe))
    sys.argv=['restore.py','--esp',str(esp)]
    for boot,grub in [('r1','r1'),('r2','r2'),('r1','r2'),('r2','r1')]:
        (esp/'boot.bin').write_bytes((boot+' boot.bin').encode())
        (esp/'grub/grub.cfg').write_bytes((grub+' grub/grub.cfg').encode())
        module.main()
        for name,item in recipe.items(): assert module.sha(esp/name)==item['before_sha256']
    (esp/'boot.bin').write_bytes(b'unknown later loader')
    before={name:(esp/name).read_bytes() for name in recipe}
    try: module.main()
    except AssertionError: pass
    else: raise AssertionError('Unknown current loader was accepted')
    assert all((esp/name).read_bytes()==data for name,data in before.items())
    (esp/'boot.bin').write_bytes(b'r2 boot.bin')
    (esp/'AUDP001/previous.grub.cfg').write_bytes(b'corrupt backup')
    before={name:(esp/name).read_bytes() for name in recipe}
    try: module.main()
    except AssertionError: pass
    else: raise AssertionError('Corrupt backup was accepted')
    assert all((esp/name).read_bytes()==data for name,data in before.items())
print('Restore PASS: four refresh transition states; unknown current files and corrupt backups rejected before writes')
