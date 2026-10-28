#!/usr/bin/env python3
"""Test actual Mesa rejection-capture functions with a mock ioctl, without a GPU."""
from pathlib import Path
import argparse
import importlib.util
import os
import stat
import struct
import subprocess
import tempfile


def function(source, name, return_type):
    start = source.index('\n' + name + '(') + 1
    opening = source.index('{', start)
    depth, end = 1, opening + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return 'static ' + return_type + '\n' + source[start:end] + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mesa', type=Path)
    args = parser.parse_args()
    decoder_path = Path(__file__).with_name('read-submit-capture.py')
    spec = importlib.util.spec_from_file_location('capture_decoder', decoder_path)
    decoder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(decoder)
    mesa = args.mesa.resolve()
    source = (mesa/'src/asahi/lib/agx_device.c').read_text()
    code = r'''
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
#include "asahi_drm.h"
#define p_atomic_cmpxchg(p, a, b) __sync_val_compare_and_swap(p, a, b)
struct agx_device { int fd; };
struct agx_submit_virt { int unused; };
static int mock_errno;
static int drmIoctl(int fd, unsigned long request, void *data) {
    (void)data; assert(fd == 42 && request == DRM_IOCTL_ASAHI_SUBMIT);
    errno = mock_errno;
    return mock_errno ? -1 : 0;
}
'''
    for name, type_ in [('agx_write_failure_data', 'bool'),
                        ('agx_capture_submit_failure', 'void'), ('agx_submit', 'int')]:
        code += function(source, name, type_)
    code += r'''
int main(int argc, char **argv) {
    assert(argc == 2);
    if (!strcmp(argv[1], "collision")) {
        const char *state = getenv("XDG_STATE_HOME");
        assert(mkdir(state, 0700) == 0);
        char path[PATH_MAX];
        assert(snprintf(path, sizeof(path), "%s/asahi-submit-%ld-fd42-q7-0.bin",
                        state, (long)getpid()) < (int)sizeof(path));
        int existing = open(path, O_CREAT | O_EXCL | O_WRONLY, 0600);
        assert(existing >= 0 && write(existing, "old", 3) == 3);
        assert(close(existing) == 0);
    }
    struct agx_device dev = {.fd = 42};
    struct drm_asahi_cmd_header command = {.cmd_type = DRM_ASAHI_CMD_RENDER,
        .size = 0, .vdm_barrier = 0xffff, .cdm_barrier = 0xffff};
    struct drm_asahi_submit submit = {.queue_id = 7,
        .cmdbuf = (uintptr_t)&command, .cmdbuf_size = sizeof(command),
        .in_sync_count = 2, .out_sync_count = 3};
    assert(agx_submit(&dev, &submit, NULL) == 0);
    mock_errno = EIO;
    assert(agx_submit(&dev, &submit, NULL) == -1 && errno == EIO);
    if (!strcmp(argv[1], "oversize")) submit.cmdbuf_size = 1024 * 1024 + 1;
    if (!strcmp(argv[1], "malformed")) command.size = 0xffff;
    mock_errno = EINVAL;
    assert(agx_submit(&dev, &submit, NULL) == -1 && errno == EINVAL);
    command.cmd_type = DRM_ASAHI_CMD_COMPUTE;
    assert(agx_submit(&dev, &submit, NULL) == -1 && errno == EINVAL);
    return 0;
}
'''
    with tempfile.TemporaryDirectory() as directory:
        base = Path(directory)
        (base/'test.c').write_text(code)
        subprocess.run(['cc', '-std=gnu11', '-Wall', '-Werror',
                        '-I'+str(mesa/'include/drm-uapi'), str(base/'test.c'),
                        '-o', str(base/'test')], check=True)
        for case in ['normal', 'malformed', 'oversize', 'missing-parent', 'collision']:
            state = base/case if case != 'missing-parent' else base/case/'child'
            result = subprocess.run([str(base/'test'), case],
                                    env=dict(os.environ, XDG_STATE_HOME=str(state)),
                                    capture_output=True, text=True)
            assert result.returncode == 0, result.stderr
            files = list(state.glob('*.bin'))
            if case in ['oversize', 'missing-parent']:
                assert not files
                continue
            if case == 'collision':
                assert len(files) == 2, files
                sentinel = next(path for path in files if path.name.endswith('-0.bin'))
                assert sentinel.read_bytes() == b'old'
                files.remove(sentinel)
                assert files[0].name.endswith('-1.bin')
            assert len(files) == 1, files
            data = files[0].read_bytes()
            header = struct.unpack('<12I', data[:48])
            assert header[0:3] == (0x46584741, 1, 48)
            assert header[4:] == (42, 7, 22, 0, 8, 2, 3, 0), header
            assert len(data) == 56
            decoded = decoder.decode(data)
            assert decoded['queue'] == 7 and decoded['commands'][0]['name'] == 'render'
            assert ('parse_error' in decoded) == (case == 'malformed')
            # Only the first rejected command survives the second call.
            kind, size, vdm, cdm = struct.unpack('<4H', data[48:])
            assert kind == 0 and size == (65535 if case == 'malformed' else 0)
            assert (vdm, cdm) == (65535, 65535)
            assert stat.S_IMODE(files[0].stat().st_mode) == 0o600
            assert stat.S_IMODE(state.stat().st_mode) == 0o700
    print('PASS: original ioctl result/errno, exact first payload, bounds, malformed headers, name collisions and private files')


if __name__ == '__main__':
    main()
