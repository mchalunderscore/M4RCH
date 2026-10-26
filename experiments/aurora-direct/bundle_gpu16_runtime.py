#!/usr/bin/env python3
"""Bundle the pinned Mesa runtime and ELF dependencies inside native Linux."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile

PROJECT = Path('/project')
OUT = PROJECT / 'out/aurora-direct/gpu16'
PREFIX = Path('/work/mesa-direct-install/opt/m4rch-aurora-direct1')
DEST = Path('/work/gpu16-userspace/opt/m4rch-aurora-direct1')


def main():
    # This is a generated cache; copying over existing symlinks is not repeatable.
    if DEST.exists():
        shutil.rmtree(DEST)
    DEST.mkdir(parents=True, exist_ok=True)
    shutil.copytree(PREFIX, DEST, dirs_exist_ok=True, symlinks=True)
    (DEST / 'bin').mkdir(exist_ok=True)
    for name in ['vulkaninfo', 'vkcube', 'vkcube-wayland', 'eglinfo', 'glxinfo']:
        path = shutil.which(name)
        if path:
            # Debian mesa-utils may dispatch through a wrapper into /usr/lib.
            source = Path(path).resolve()
            if source.read_bytes()[:4] != b'\x7fELF':
                candidates = list(Path('/usr/lib').glob('**/' + name))
                source = next((p for p in candidates if p.is_file() and p.read_bytes()[:4] == b'\x7fELF'), source)
            if source.read_bytes()[:4] != b'\x7fELF':
                raise ValueError('Diagnostic is not a standalone ELF: ' + name)
            shutil.copyfile(source, DEST / 'bin' / name)
            (DEST / 'bin' / name).chmod(0o755)
    fallback = DEST / 'runtime-libs'
    fallback.mkdir(exist_ok=True)
    exclude = re.compile(r'^(?:ld-linux.*|lib(?:c|m|pthread|dl|rt|resolv|util|anl)\.so\..*)$')
    dependencies = {}
    objects = list((DEST / 'bin').glob('*')) + list((DEST / 'lib/aarch64-linux-gnu').glob('*.so*'))
    for obj in objects:
        if not obj.is_file() or obj.read_bytes()[:4] != b'\x7fELF':
            continue
        output = subprocess.check_output(['ldd', str(obj)], text=True,
                                         env={**os.environ, 'LD_LIBRARY_PATH': str(DEST / 'lib/aarch64-linux-gnu')})
        if 'not found' in output:
            raise ValueError('Unresolved build dependency: ' + str(obj))
        for soname, source in re.findall(r'^\s*(\S+) => (/\S+)', output, re.M):
            if exclude.match(soname) or str(DEST) in source:
                continue
            target = fallback / soname
            shutil.copyfile(Path(source).resolve(), target)
            dependencies[soname] = {'source': source, 'sha256': hashlib.sha256(target.read_bytes()).hexdigest(), 'bytes': target.stat().st_size}
    (OUT / 'runtime-dependencies.json').write_text(json.dumps(dependencies, indent=2) + '\n')
    # Plasma starts KWin through the user manager, which may discard LD_LIBRARY_PATH.
    # Each ELF, including dlopen-loaded GBM/DRI plugins, must resolve its own imports.
    library = DEST / 'lib/aarch64-linux-gnu'
    objects = sorted({p.resolve() for p in DEST.rglob('*') if p.is_file()
                      and p.open('rb').read(4) == b'\x7fELF'})
    for obj in objects:
        if not obj.is_relative_to(DEST):
            raise ValueError('ELF symlink escapes runtime: ' + str(obj))
        paths = [] if obj.parent == fallback else ['$ORIGIN']
        paths += ['$ORIGIN/' + os.path.relpath(library, obj.parent), '/usr/lib', '/lib',
                  '$ORIGIN/' + os.path.relpath(fallback, obj.parent)]
        subprocess.run(['patchelf', '--set-rpath', ':'.join(dict.fromkeys(paths)), str(obj)], check=True)
    # GLVND must load this Mesa even in clients without the shell wrapper.
    vendor = DEST / 'share/glvnd/egl_vendor.d/50_mesa.json'
    data = json.loads(vendor.read_text())
    data['ICD']['library_path'] = '/opt/m4rch-aurora-direct1/lib/aarch64-linux-gnu/libEGL_mesa.so.0'
    vendor.write_text(json.dumps(data, indent=2) + '\n')
    clean_env = {k: v for k, v in os.environ.items() if k not in ('LD_LIBRARY_PATH', 'LD_PRELOAD')}
    verification = {}
    for obj in objects:
        result = subprocess.run(['ldd', str(obj)], text=True, capture_output=True, env=clean_env)
        if result.returncode or 'not found' in result.stdout or '/work/mesa-direct-install/' in result.stdout:
            raise ValueError('Runtime loader failure: ' + str(obj) + '\n' + result.stdout + result.stderr)
        verification[str(obj.relative_to(DEST))] = result.stdout
    plugins = [library / 'gbm/dri_gbm.so', library / 'libEGL_mesa.so.0', library / 'libvulkan_asahi.so']
    for plugin in plugins:
        subprocess.run(['python3', '-c', 'import ctypes,sys; ctypes.CDLL(sys.argv[1])', str(plugin)],
                       check=True, env=clean_env)
    for soname, info in dependencies.items():
        path = fallback / soname
        info.update(sha256=hashlib.sha256(path.read_bytes()).hexdigest(), bytes=path.stat().st_size)
    (OUT / 'runtime-dependencies.json').write_text(json.dumps(dependencies, indent=2) + '\n')
    (OUT / 'runtime-loader-verification.json').write_text(json.dumps({
        'ld_library_path_unset': True, 'objects': verification,
        'dlopen_verified': [str(p.relative_to(DEST)) for p in plugins], 'hardware_rendering_tested': False}, indent=2) + '\n')
    with tarfile.open(OUT / 'mesa.tar.gz', 'w:gz') as archive:
        archive.add(DEST, arcname='opt/m4rch-aurora-direct1')
    print('Bundled', len(dependencies), 'fallback libraries and', len(list((DEST / 'bin').iterdir())), 'diagnostics')


if __name__ == '__main__':
    main()
