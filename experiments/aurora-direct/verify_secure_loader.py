#!/usr/bin/env python3
"""Reproduce secure Vulkan discovery in the disposable Linux build container."""
import json
import os
from pathlib import Path
import shutil
import subprocess

RUNTIME = Path('/work/gpu16-userspace/opt/m4rch-aurora-direct1')
PREFIX = Path('/opt/m4rch-aurora-direct1')
WORK = Path('/work/gpu16-loader-check')
REPORT = Path('/project/out/aurora-direct/gpu16/secure-loader-verification.json')


def main():
    if PREFIX.exists():
        assert PREFIX.resolve() == RUNTIME
    else:
        PREFIX.symlink_to(RUNTIME, target_is_directory=True)
    WORK.mkdir(exist_ok=True)
    source = WORK / 'probe.c'
    source.write_text(r'''
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <dlfcn.h>
#include <sys/auxv.h>
#include <vulkan/vulkan.h>
int main(void) {
    printf("AT_SECURE=%lu\n", getauxval(AT_SECURE));
    printf("override_visible=%d\n", secure_getenv("VK_DRIVER_FILES") != NULL);
    void *loader = dlopen("libvulkan.so.1", RTLD_NOW);
    if (!loader) { puts(dlerror()); return 2; }
    PFN_vkCreateInstance create = dlsym(loader, "vkCreateInstance");
    PFN_vkDestroyInstance destroy = dlsym(loader, "vkDestroyInstance");
    VkInstanceCreateInfo info = {.sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO};
    VkInstance instance;
    VkResult result = create(&info, NULL, &instance);
    printf("instance_result=%d\n", result);
    if (result == VK_SUCCESS) destroy(instance, NULL);
    dlclose(loader);
    return result == VK_SUCCESS ? 0 : 1;
}
''')
    probe = WORK / 'probe'
    subprocess.run(['cc', str(source), '-ldl', '-o', str(probe)], check=True)
    manifest = Path('/etc/vulkan/icd.d/aurora_gpu16_check.json')
    if manifest.exists():
        raise ValueError('Inspect existing test manifest first')
    env = {**os.environ, 'VK_DRIVER_FILES': '/nonexistent/intentionally-invalid-icd.json'}
    env.pop('VK_ICD_FILENAMES', None)
    env.pop('LD_LIBRARY_PATH', None)
    try:
        shutil.copyfile(PREFIX / 'share/vulkan/icd.d/asahi_icd.aarch64.json', manifest)
        normal = subprocess.run([str(probe)], env=env, text=True, capture_output=True)
        assert normal.returncode == 1 and 'AT_SECURE=0' in normal.stdout, normal.stdout + normal.stderr
        subprocess.run(['setcap', 'cap_net_bind_service=ep', str(probe)], check=True)
        secure = subprocess.run(['setpriv', '--reuid=65534', '--regid=65534', '--clear-groups', str(probe)],
                                env=env, text=True, capture_output=True)
        assert secure.returncode == 0 and 'AT_SECURE=1' in secure.stdout and 'override_visible=0' in secure.stdout, secure.stdout + secure.stderr
        REPORT.write_text(json.dumps({'normal_invalid_override': normal.stdout,
                                     'secure_trusted_system_discovery': secure.stdout,
                                     'private_driver_instance_created': True,
                                     'hardware_rendering_tested': False}, indent=2) + '\n')
        print('Secure Vulkan discovery passed: environment ignored, private driver instance created via trusted manifest')
    finally:
        manifest.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
