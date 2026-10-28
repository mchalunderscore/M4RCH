#!/usr/bin/env python3
"""Round-trip real launcher arguments through a mock muvm and its POSIX shell."""
from pathlib import Path
import json
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def main():
    with tempfile.TemporaryDirectory() as directory:
        base = Path(directory)
        capture = base/'arguments.json'
        receiver = base/'valve-launcher'
        receiver.write_text("""#!/bin/bash
exec /usr/bin/python3 -c 'import json,os,sys; open(os.environ["STEAM_TEST_CAPTURE"],"w").write(json.dumps(sys.argv[1:]))' "$@"
""")
        receiver.chmod(0o755)
        mock = base/'muvm'
        mock.write_text('''#!/usr/bin/python3
import subprocess,sys
args=sys.argv[1:]
assert "-h" not in args and "--help" not in args, args
args=args[args.index("FEXBash")+1:]
sys.exit(subprocess.call(["/bin/sh",*args]))
''')
        mock.chmod(0o755)
        source = (ROOT/'packages/steam-m4rch/steam-x86').read_text()
        target = '/usr/lib/steam/steam-fex.sh'
        assert source.count(target) == 1, 'Expected one x86 guest launcher'
        source = source.replace(target, str(receiver))
        # This test targets argv transport, not the independent privilege guard.
        if os.geteuid() == 0:
            source = source.replace('if (( EUID == 0 )); then', 'if false; then')
        wrapper = base/'steam'
        wrapper.write_text(source)
        arguments = ['-h', '--help', '-applaunch', '4000', '', 'two words',
                     "apostrophe'", '"quoted"', '$(touch SHOULD_NOT_EXIST)',
                     '`touch SHOULD_NOT_EXIST`', 'line\nbreak', 'Zażółć']
        subprocess.run(['/bin/bash', str(wrapper), *arguments], cwd=base,
                       env=dict(os.environ, HOME=str(base), PATH=str(base)+':'+os.environ['PATH'],
                                STEAM_TEST_CAPTURE=str(capture)), check=True)
        assert json.loads(capture.read_text()) == arguments
        assert not (base/'SHOULD_NOT_EXIST').exists()
        subprocess.run(['/bin/bash', str(wrapper)], cwd=base,
                       env=dict(os.environ, HOME=str(base), PATH=str(base)+':'+os.environ['PATH'],
                                STEAM_TEST_CAPTURE=str(capture)), check=True)
        assert json.loads(capture.read_text()) == []
    print('PASS: Steam help/game flags, empty args, quotes, unicode and shell metacharacters')


if __name__ == '__main__':
    main()
