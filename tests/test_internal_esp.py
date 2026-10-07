import importlib.util
from pathlib import Path
import struct
import io
from unittest.mock import patch
import sys
import unittest
PROJECT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT/'lib'))
spec=importlib.util.spec_from_file_location('internal_esp',PROJECT/'scripts/internal-esp.py')
esp=importlib.util.module_from_spec(spec);spec.loader.exec_module(esp)

class InternalESPTests(unittest.TestCase):
    def image(self):
        blob=bytearray(512);blob[:2]=b'MZ';struct.pack_into('<I',blob,60,128)
        blob[128:132]=b'PE\0\0';struct.pack_into('<H',blob,132,0xaa64)
        struct.pack_into('<H',blob,152,0x20b);blob[400:409]=b'969C-748A'
        return bytes(blob)
    def test_retarget_unsigned_arm64(self):
        blob=self.image();result=esp.retarget_efi(blob,'969C-748A','A123-B456')
        self.assertEqual(len(result),len(blob));self.assertIn(b'A123-B456',result)
        self.assertNotIn(b'969C-748A',result)
        self.assertNotEqual(struct.unpack_from('<I',result,216)[0],0)
    def test_reject_signed_or_ambiguous(self):
        blob=bytearray(self.image());struct.pack_into('<II',blob,296,20,10)
        with self.assertRaises(ValueError):esp.retarget_efi(bytes(blob),'969C-748A','A123-B456')
        with self.assertRaises(ValueError):esp.retarget_efi(self.image()+b'969C-748A','969C-748A','A123-B456')
    def test_real_grub_retarget(self):
        path=Path('/Volumes/ARCHBOOT/EFI/BOOT/BOOTAA64.EFI')
        if not path.exists():self.skipTest('SD EFI not mounted')
        result=esp.retarget_efi(path.read_bytes(),'969C-748A','A123-B456')
        self.assertEqual(result.count(b'A123-B456'),1)
    def test_internal_bridge_no_sd_path(self):
        bridge=(PROJECT/'sdboot/archnvme.c').read_text()
        self.assertNotIn('pci_init()',bridge);self.assertNotIn('"mmc"',bridge)
        self.assertIn(esp.ESP_UUID,bridge)

    def test_mounted_esp_is_unmounted_for_read_and_restored(self):
        value = dict(DeviceIdentifier='disk0s3', DeviceNode='/dev/disk0s3',
                     DiskUUID=esp.ESP_UUID, ParentWholeDisk='disk0', Size=1024**3,
                     Mounted=True, MountPoint='/Volumes/M4RCHESP')
        fresh = {**value, 'Mounted':False, 'MountPoint':''}
        calls=[]
        def opened(*args):
            self.assertEqual(calls[-1][1], 'unmount')
            return io.BytesIO(bytes(4096))
        with patch.object(esp.m,'run',side_effect=lambda *args: calls.append(args)), \
             patch.object(esp.m,'info',return_value=fresh), patch('builtins.open',side_effect=opened):
            self.assertEqual(esp.read_fat_sector(value),bytes(4096))
        self.assertEqual([args[1] for args in calls],['unmount','mount'])

    def test_esp_read_failure_restores_mount(self):
        value = dict(DeviceIdentifier='disk0s3', DeviceNode='/dev/disk0s3',
                     DiskUUID=esp.ESP_UUID, ParentWholeDisk='disk0', Size=1024**3,
                     Mounted=True, MountPoint='/Volumes/M4RCHESP')
        fresh = {**value, 'Mounted':False, 'MountPoint':''}
        with patch.object(esp.m,'run') as run, patch.object(esp.m,'info',return_value=fresh), \
             patch('builtins.open',side_effect=OSError('read failed')):
            with self.assertRaises(OSError):esp.read_fat_sector(value)
        self.assertEqual(run.call_args_list[-1].args,('/usr/sbin/diskutil','mount','disk0s3'))

    def test_esp_remount_race_stops_before_read(self):
        value = dict(DeviceIdentifier='disk0s3', DeviceNode='/dev/disk0s3',
                     DiskUUID=esp.ESP_UUID, ParentWholeDisk='disk0', Size=1024**3,
                     Mounted=True, MountPoint='/Volumes/M4RCHESP')
        with patch.object(esp.m,'run'), patch.object(esp.m,'info',return_value=value), \
             patch('builtins.open') as opened:
            with self.assertRaises(ValueError):esp.read_fat_sector(value)
        opened.assert_not_called()

    def test_internal_shutdown_trace_preserves_checked_operations(self):
        import tempfile
        sys.path.insert(0,str(PROJECT/'sdboot'))
        import loader
        from test_nvme_handoff import NvmeHandoffTests
        with tempfile.TemporaryDirectory() as temporary:
            tree=Path(temporary)
            before=NvmeHandoffTests().patched(tree)
            loader.trace_nvme_handoff(tree)
            after=(tree/'src/nvme.c').read_text()
            # Removing only breadcrumb lines must recover the exact guarded
            # driver: tracing cannot bypass shutdown or DMA ownership checks.
            stripped='\n'.join(line for line in after.split('\n') if 'printf("M4RCH ANS handoff:' not in line)
            self.assertEqual(stripped,before)
            self.assertIn('M4RCH ANS handoff: delete I/O SQ',after)

    def test_actual_bounded_shutdown_completes_or_times_out(self):
        import shutil
        import subprocess
        import tempfile
        if not shutil.which('cc'):self.skipTest('Host C compiler unavailable')
        sys.path.insert(0,str(PROJECT/'sdboot'))
        import loader
        from test_nvme_handoff import NvmeHandoffTests,function
        with tempfile.TemporaryDirectory() as temporary:
            tree=Path(temporary)
            NvmeHandoffTests().patched(tree)
            loader.bounded_nvme_shutdown(tree)
            source=(tree/'src/nvme.c').read_text()
            body=function(source,'static bool nvme_ctrl_shutdown(void)')
            self.assertIn('rtkit_recv_one(nvme_rtkit, &message)',body)
            rtkit=(tree/'src/rtkit.c').read_text()
            self.assertIn('while (budget && asc_recv(rtk->asc, &asc_msg))',rtkit)
            self.assertIn('return rtkit_recv_limit(rtk, msg, 1);',rtkit)
            self.assertIn('return rtkit_recv_limit(rtk, msg, ~0u);',rtkit)
            self.assertIn('NVME_CSTS_SHST_DONE',body)
            fixture=(PROJECT/'tests/fixtures/nvme-shutdown-poll.c').read_text()
            model=tree/'model.c';model.write_text(fixture.replace('/* ACTUAL_SHUTDOWN */',body))
            binary=tree/'model'
            compiled=subprocess.run(['cc','-Wall','-Wextra','-Werror',str(model),'-o',str(binary)],capture_output=True)
            self.assertEqual(compiled.returncode,0,compiled.stderr.decode())
            subprocess.run([str(binary)],check=True,capture_output=True,timeout=10)

    def test_actual_rtkit_receive_yields_after_one_message(self):
        import re
        import shutil
        import subprocess
        import tempfile
        if not shutil.which('cc'):self.skipTest('Host C compiler unavailable')
        import loader
        from test_nvme_handoff import NvmeHandoffTests,function
        with tempfile.TemporaryDirectory() as temporary:
            tree=Path(temporary)
            NvmeHandoffTests().patched(tree)
            loader.bounded_nvme_shutdown(tree)
            source=(tree/'src/rtkit.c').read_text()
            functions='\n'.join(function(source, signature) for signature in (
                'static int rtkit_recv_limit(', 'int rtkit_recv_one(', 'int rtkit_recv('))
            # Supply endpoint/message constants and handler stubs; compile the
            # actual receive loop, including invalid-endpoint continue paths.
            constants=sorted(set(re.findall(r'\b(?:RTKIT_EP_|MGMT_MSG_|MSG_)[A-Z0-9_]+',functions)))
            constants=[name for name in constants if name not in ('MSG_SYSLOG_INIT_COUNT','MSG_SYSLOG_INIT_ENTRYSIZE','MSG_SYSLOG_LOG_INDEX')]
            preamble=(PROJECT/'tests/fixtures/rtkit-receive-budget.c').read_text()
            enumeration='enum { '+', '.join(name+'='+str((i+1) if name.startswith('RTKIT_EP_') else (256+i)) for i,name in enumerate(constants))+' };'
            model=tree/'receive.c'
            model.write_text(preamble.replace('/* CONSTANTS */',enumeration).replace('/* ACTUAL_RECEIVE */',functions))
            binary=tree/'receive'
            compiled=subprocess.run(['cc','-Wall','-Wextra','-Werror',str(model),'-o',str(binary)],capture_output=True)
            self.assertEqual(compiled.returncode,0,compiled.stderr.decode())
            subprocess.run([str(binary)],check=True,capture_output=True,timeout=10)

    def test_nvme_control_dt_keeps_flat_node_offsets(self):
        import ast
        import re
        import shutil
        import subprocess
        import tempfile
        if not shutil.which('cc'):self.skipTest('Host C compiler unavailable')
        libfdt=PROJECT/'cache/sdboot-src/scripts/dtc/libfdt'
        if not (libfdt/'fdt.c').exists():self.skipTest('Cached libfdt unavailable')
        syntax=ast.parse((PROJECT/'sdboot/prepare_nvme_uboot.py').read_text())
        body=next(node.value for node in ast.walk(syntax) if isinstance(node,ast.Constant)
                  and isinstance(node.value,str) and 'fdt32_t reg[]' in node.value)
        reg=re.search(r'fdt32_t reg\[\] = .*?};',body,re.S).group(0)
        fixture=(PROJECT/'tests/fixtures/nvme-dt-offsets.c').read_text().replace('/* ACTUAL_REG */',reg)
        with tempfile.TemporaryDirectory() as temporary:
            tree=Path(temporary);model=tree/'model.c';model.write_text(fixture)
            binary=tree/'model'
            sources=[libfdt/name for name in ('fdt.c','fdt_ro.c','fdt_rw.c','fdt_sw.c','fdt_wip.c','fdt_strerror.c','fdt_empty_tree.c','fdt_addresses.c')]
            result=subprocess.run(['cc','-I'+str(libfdt),str(model),*[str(path) for path in sources],'-o',str(binary)],capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr.decode())
            subprocess.run([str(binary)],check=True,capture_output=True,timeout=10)

    def test_packaged_ans_power_ancestry_is_mapped(self):
        from prepare_nvme_uboot import validate_power_map
        import prepare_nvme_uboot as preparation
        dtb=PROJECT/'out/sdboot/internal-loader/loader/baseline.dtb'
        if not dtb.exists():self.skipTest('Packaged baseline unavailable')
        self.assertEqual(validate_power_map(dtb),{0x502280000,0x502800000})
        # Reproduce the incorrect second aperture which stopped at block 3.
        with patch.object(preparation,'PMGR_WINDOWS',(0x502280000,0x5022c0000)):
            with self.assertRaisesRegex(ValueError,'0x502800000'):
                validate_power_map(dtb)
