#!/usr/bin/env python3
"""Check FEX socket exposure without launching Steam or a VM."""
from pathlib import Path
import os, socket, subprocess, tempfile
root=Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory() as directory:
    base=Path(directory)
    path=base/f'{os.getuid()}.FEXServer.Socket'
    with socket.socket(socket.AF_UNIX) as server:
        server.bind(str(path))
        source=(root/'packages/steam-m4rch/steam-fex.sh').read_text()
        source=source.replace('exec /bin/bash /usr/lib/steam/bin_steam.sh "$@"', 'printf "%s" "${PRESSURE_VESSEL_FILESYSTEMS_RW:-}"')
        script=base/'bootstrap.sh'; script.write_text(source)
        env=dict(os.environ,XDG_RUNTIME_DIR=str(base))
        env.pop('FEX_SERVERSOCKETPATH',None)
        for initial,expected in [('',str(path)),('/games','/games:'+str(path)),(str(path),str(path))]:
            env['PRESSURE_VESSEL_FILESYSTEMS_RW']=initial
            assert subprocess.check_output(['/bin/bash',str(script)],env=env,text=True)==expected
        env['FEX_SERVERSOCKETPATH']=str(path)
        assert subprocess.check_output(['/bin/bash',str(script)],env=env,text=True)==str(path)
    env['PRESSURE_VESSEL_FILESYSTEMS_RW']='/games'
    path.unlink()
    assert subprocess.check_output(['/bin/bash',str(script)],env=env,text=True)=='/games'
print('PASS: runtime socket, explicit socket, existing mounts, duplicate and absent socket')
