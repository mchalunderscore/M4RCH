#!/usr/bin/env python3
"""Build GL.host extensions against installed Freedesktop SDKs in the build VM."""
from pathlib import Path
import json
import importlib.util
import os
import re
import shutil
import subprocess
import tarfile

PROJECT = Path('/project')
OUT = PROJECT / 'out/candidate-20261026'
WORK = Path('/work/flatpak-mesa')
PREFIX = '/usr/lib/aarch64-linux-gnu/GL/host'


def run(*args, **kwargs):
    subprocess.run([str(a) for a in args], check=True, **kwargs)


def main():
    pin = json.loads((OUT / 'mesa-pin.json').read_text())['commit']
    WORK.mkdir(exist_ok=True)
    (WORK / 'tmp').mkdir(exist_ok=True)
    python_modules = WORK / 'python'
    python_modules.mkdir(exist_ok=True)
    for name in ('yaml', 'mako', 'markupsafe', 'ply', 'packaging', 'jinja2'):
        spec = importlib.util.find_spec(name)
        if spec and spec.submodule_search_locations:
            shutil.copytree(next(iter(spec.submodule_search_locations)), python_modules / name,
                            dirs_exist_ok=True, ignore=shutil.ignore_patterns('*.so', '__pycache__'))
    source = WORK / ('mesa-' + pin)
    if not source.exists():
        with tarfile.open(OUT / 'mesa-source.tar.gz') as archive:
            archive.extractall(WORK, filter='data')
    extensions = OUT / 'flatpak-extensions'
    licenses = OUT / 'flatpak-licenses'
    licenses.mkdir(exist_ok=True)
    shutil.copy2(source / 'docs/license.rst', licenses / 'Mesa.rst')
    translator_pin = json.loads((OUT / 'spirv-pin.json').read_text())['commit']
    translator = WORK / ('SPIRV-LLVM-Translator-' + translator_pin)
    if not translator.exists():
        with tarfile.open(OUT / 'spirv-translator.tar.gz') as archive:
            archive.extractall(WORK, filter='data')
    dependency_sources = {}
    for name in ('SPIRV-Headers', 'SPIRV-Tools'):
        revision = json.loads((OUT / (name + '-pin.json')).read_text())['commit']
        dependency_sources[name] = WORK / (name + '-' + revision)
        if not dependency_sources[name].exists():
            with tarfile.open(OUT / (name + '.tar.gz')) as archive:
                archive.extractall(WORK, filter='data')
    for branch in ('25.08', '26.08'):
        sdk = Path('/root/.local/share/flatpak/runtime/org.freedesktop.Sdk/aarch64') / branch / 'active/files'
        assert sdk.is_dir(), sdk
        llvm = Path('/root/.local/share/flatpak/runtime/org.freedesktop.Sdk.Extension.llvm22/aarch64') / branch / 'active/files'
        assert llvm.is_dir(), llvm
        shutil.copytree(llvm / 'share/licenses', licenses / 'llvm', dirs_exist_ok=True)
        # The builder cannot mount a fresh procfs. Bind its existing read-only
        # root and SDK /usr; all compilation still uses the SDK's compiler/ABI.
        sandbox = ['bwrap', '--unshare-user', '--ro-bind', '/', '/',
                   '--dev-bind', '/dev', '/dev', '--ro-bind', '/proc', '/proc',
                   '--ro-bind', str(sdk), '/usr', '--bind', '/work', '/work',
                   '--tmpfs', '/usr/lib/sdk',
                   '--ro-bind', str(llvm), '/usr/lib/sdk/llvm22',
                   '--bind', '/project', '/project', '--clearenv',
                   '--setenv', 'PATH', '/usr/lib/sdk/llvm22/bin:/usr/bin', '--setenv', 'HOME', '/work',
                   '--setenv', 'LD_LIBRARY_PATH', '/usr/lib/sdk/llvm22/lib:/usr/lib/aarch64-linux-gnu:/usr/lib',
                   '--setenv', 'PKG_CONFIG_PATH', '/usr/lib/sdk/llvm22/lib/pkgconfig',
                   '--setenv', 'PYTHONPATH', str(python_modules),
                   '--setenv', 'TMPDIR', str(WORK / 'tmp'),
                   '--setenv', 'CCACHE_DISABLE', '1',
                   '--setenv', 'LC_ALL', 'C.UTF-8', '--chdir', str(source)]
        build = WORK / ('build-' + branch)
        tools = WORK / ('tools-' + branch)
        translator_build = WORK / ('translator-' + branch)
        run(*sandbox, 'cmake', '-G', 'Ninja', '-S', translator, '-B', translator_build,
            '-DLLVM_DIR=/usr/lib/sdk/llvm22/lib/cmake/llvm',
            '-DLLVM_EXTERNAL_SPIRV_HEADERS_SOURCE_DIR=' + str(dependency_sources['SPIRV-Headers']),
            '-DLLVM_SPIRV_INCLUDE_TESTS=OFF', '-DBUILD_SHARED_LIBS=ON',
            '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_INSTALL_PREFIX=' + str(tools))
        run(*sandbox, 'cmake', '--build', translator_build, '-j6')
        run(*sandbox, 'cmake', '--install', translator_build)
        spirv_build = WORK / ('spirv-tools-' + branch)
        run(*sandbox, 'cmake', '-G', 'Ninja', '-S', dependency_sources['SPIRV-Tools'], '-B', spirv_build,
            '-DSPIRV-Headers_SOURCE_DIR=' + str(dependency_sources['SPIRV-Headers']),
            '-DSPIRV_SKIP_TESTS=ON', '-DSPIRV_SKIP_EXECUTABLES=ON',
            '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_INSTALL_PREFIX=' + str(tools))
        run(*sandbox, 'cmake', '--build', spirv_build, '-j6')
        run(*sandbox, 'cmake', '--install', spirv_build)
        sandbox += ['--setenv', 'PKG_CONFIG_PATH', str(tools / 'lib/pkgconfig') +
                    ':/usr/lib/sdk/llvm22/lib/pkgconfig', '--setenv', 'LD_LIBRARY_PATH',
                    str(tools / 'lib') + ':/usr/lib/sdk/llvm22/lib:/usr/lib/aarch64-linux-gnu:/usr/lib']
        args = ['meson', 'setup', '--prefix=' + PREFIX, '--libdir=lib',
                '--buildtype=release', '-Dgallium-drivers=asahi,zink',
                '-Dvulkan-drivers=asahi', '-Dplatforms=x11,wayland',
                '-Dglx=dri', '-Dglvnd=enabled', '-Degl=enabled', '-Dgbm=enabled',
                '-Dllvm=enabled', '-Dvideo-codecs=[]', '-Dgallium-va=disabled',
                '-Dfreedreno-kmds=[]', '-Dtools=[]', str(build), str(source)]
        if (build / 'meson-private/coredata.dat').exists():
            args.insert(2, '--reconfigure')
        run(*sandbox, *args)
        run(*sandbox, 'ninja', '-C', build, '-j6')
        dest = WORK / ('install-' + branch)
        if dest.exists():
            shutil.rmtree(dest)
        run(*sandbox, 'env', 'DESTDIR=' + str(dest), 'ninja', '-C', build, 'install')
        installed = dest / PREFIX.lstrip('/')
        extension = extensions / 'org.freedesktop.Platform.GL.host/aarch64' / branch
        if extension.exists():
            shutil.rmtree(extension)
        extension.mkdir(parents=True)
        # GL.host is an unmanaged extension: its branch directory itself is
        # mounted as the payload, unlike an OSTree deployment's files/ child.
        shutil.copytree(installed, extension, dirs_exist_ok=True, symlinks=True)
        files = extension
        for name in ('vulkan', 'glvnd', 'egl'):
            if (files / 'share' / name).exists():
                shutil.move(str(files / 'share' / name), files / name)
        (extension / 'metadata').write_text(
            '[Runtime]\nname=org.freedesktop.Platform.GL.host\n'
            f'runtime=org.freedesktop.Platform/aarch64/{branch}\n'
            f'sdk=org.freedesktop.Sdk/aarch64/{branch}\n\n'
            '[ExtensionOf]\n'
            f'ref=runtime/org.freedesktop.Platform/aarch64/{branch}\n')
        platform = Path('/root/.local/share/flatpak/runtime/org.freedesktop.Platform/aarch64') / branch / 'active/files'
        platform_libs = (platform / 'lib/aarch64-linux-gnu', platform / 'lib')
        dependency_path = str(files / 'lib') + ':' + str(tools / 'lib') + \
            ':/usr/lib/sdk/llvm22/lib:/usr/lib/aarch64-linux-gnu:/usr/lib'
        # Bundle SDK toolchain runtime libraries absent from the Platform.
        # Keep the Platform's libc, loader and ordinary ABI libraries in use.
        checked = set()
        while True:
            pending = [p for p in (files / 'lib').glob('*.so*')
                       if p.is_file() and p.resolve() not in checked]
            if not pending:
                break
            for obj in pending:
                checked.add(obj.resolve())
                listing = subprocess.check_output(sandbox + ['env', 'LD_LIBRARY_PATH=' + dependency_path,
                                                  'ldd', str(obj)], text=True)
                if 'not found' in listing:
                    raise RuntimeError(listing)
                for name, path in re.findall(r'(\S+) => (/\S+)', listing):
                    if (files / 'lib' / name).exists() or any((p / name).exists() for p in platform_libs):
                        continue
                    if path.startswith('/usr/lib/sdk/llvm22/'):
                        origin = llvm / path.removeprefix('/usr/lib/sdk/llvm22/')
                    elif path.startswith('/usr/'):
                        origin = sdk / path.removeprefix('/usr/')
                    else:
                        origin = Path(path)
                    shutil.copyfile(origin.resolve(), files / 'lib' / name)
        # Eager loading checks the extension against its own SDK dependencies.
        run(*sandbox, 'env', 'LD_LIBRARY_PATH=' + str(files / 'lib') +
            ':/usr/lib/aarch64-linux-gnu:/usr/lib', 'python3', '-c',
            'import ctypes,sys; [ctypes.CDLL(p) for p in sys.argv[1:]]',
            *(files / 'lib' / name for name in
              ('libEGL_mesa.so.0', 'libGLX_mesa.so.0', 'libgbm.so.1', 'libvulkan_asahi.so')))
    with tarfile.open(OUT / 'flatpak-extensions.tar.gz', 'w:gz') as archive:
        archive.add(extensions, arcname='extension')
        archive.add(licenses, arcname='licenses')


if __name__ == '__main__':
    main()
