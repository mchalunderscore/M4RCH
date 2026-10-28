#!/usr/bin/env python3
"""Check argument forwarding through the current native Steam launcher."""
from pathlib import Path
import json
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def main():
    with tempfile.TemporaryDirectory() as directory:
        base = Path(directory)
        root = base / 'steam-root'
        binary = root / 'steamrtarm64/steam'
        binary.parent.mkdir(parents=True)
        binary.write_text('#!/bin/sh\nexit 0\n')
        binary.chmod(0o755)
        userpages = base / 'userpages'
        userpages.write_text('#!/bin/sh\nprintf "%s\\n" "${TEST_PAGE_SIZE:-4096}"\n')
        userpages.chmod(0o755)
        receiver = base / 'launch-loop'
        receiver.write_text('''#!/usr/bin/python3
import json, os, sys
with open(os.environ['STEAM_TEST_CAPTURE'], 'w') as f:
    json.dump(sys.argv[1:], f)
''')
        receiver.chmod(0o755)
        source = (ROOT / 'packages/steam-m4rch/steam').read_text()
        for old, new in [('/usr/libexec/aurora/userpages', str(userpages)),
                         ('/usr/lib/steam/steam-native4k-launch-loop.sh', str(receiver))]:
            assert source.count(old) == 1
            source = source.replace(old, new)
        if os.geteuid() == 0:
            source = source.replace('if (( EUID == 0 )); then', 'if false; then')
        wrapper = base / 'steam'
        wrapper.write_text(source)
        capture = base / 'arguments.json'
        env = dict(os.environ, HOME=str(base), AURORA_STEAM_ROOT=str(root),
                   STEAM_TEST_CAPTURE=str(capture))
        args = ['--help', '-applaunch', '4000', '', 'two words', "apostrophe'",
                '$(touch SHOULD_NOT_EXIST)', '`touch SHOULD_NOT_EXIST`', 'line\nbreak', 'Zażółć']
        subprocess.run(['/bin/bash', str(wrapper), *args], cwd=base, env=env, check=True)
        assert json.loads(capture.read_text()) == ['-noverifyfiles', *args]
        assert not (base / 'SHOULD_NOT_EXIST').exists()
        wrong_page = dict(env, TEST_PAGE_SIZE='16384')
        result = subprocess.run(['/bin/bash', str(wrapper)], cwd=base, env=wrong_page, capture_output=True)
        assert result.returncode != 0 and b'4 KiB' in result.stderr
        binary.unlink()
        result = subprocess.run(['/bin/bash', str(wrapper)], cwd=base, env=env, capture_output=True)
        assert result.returncode != 0 and b'not installed' in result.stderr
    print('PASS: native Steam argument forwarding, page-size guard and missing-client guard')


if __name__ == '__main__':
    main()
