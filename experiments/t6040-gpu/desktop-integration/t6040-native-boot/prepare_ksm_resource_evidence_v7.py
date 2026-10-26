#!/usr/bin/env python3
"""Save static source closure for the native KSM resource's three address views.

Reads only matched private inputs. It neither executes native instructions nor
tests, maps, installs, publishes, or touches hardware. No instruction bytes are
exported into the numeric report.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

IMAGE_BASE = 0xfffffe0007004000


class Image:
    def __init__(self, path):
        self.path = path.resolve()
        self.data = self.path.read_bytes()
        self.segments = []
        pos = 32
        for _ in range(struct.unpack_from('<I', self.data, 16)[0]):
            command, size = struct.unpack_from('<II', self.data, pos)
            if command == 25:
                self.segments.append(struct.unpack_from('<QQQQ', self.data, pos + 24))
            pos += size

    def read(self, address, size):
        for start, _, fileoff, filebytes in self.segments:
            if start <= address and address + size <= start + filebytes:
                offset = fileoff + address - start
                return self.data[offset:offset + size]
        raise ValueError(f'Not file backed: {address:#x}+{size:#x}')

    def pin(self):
        return {'path': str(self.path), 'bytes': len(self.data),
                'sha256': hashlib.sha256(self.data).hexdigest()}

    def span(self, first, end, role):
        return {'first': hex(first), 'end_exclusive': hex(end), 'role': role,
                'sha256': hashlib.sha256(self.read(first, end - first)).hexdigest()}

    def slot(self, address_point, slot, expected):
        entry = address_point + slot
        raw, = struct.unpack('<Q', self.read(entry, 8))
        target = IMAGE_BASE + (raw & 0xffffffff)
        assert target == expected, (hex(entry), hex(target), hex(expected))
        return {'address_point': hex(address_point), 'slot': hex(slot),
                'entry': hex(entry), 'chained_pointer': hex(raw),
                'target': hex(target)}

    def gpu_address_leaf(self, address):
        # BTI C; LDR x0,[x0,#0x28]; RET. Pin the private input but export only
        # the interpreted object field and function extent.
        assert struct.unpack('<III', self.read(address, 12)) == (
            0xd503245f, 0xf9401400, 0xd65f03c0)
        return {'function': hex(address), 'object_field': '0x28',
                'bytes': 12, 'sha256': hashlib.sha256(self.read(address, 12)).hexdigest()}


def prepare(output):
    root = Path(__file__).resolve().parents[4]
    agx = Image(Path('/boot/GPUC003/private-apple/com.apple.AGXG16X'))
    iogpu = Image(root / 'out/private-apple/com.apple.iokit.IOGPUFamily.fileset-macho')
    kernel = Image(root / 'out/private-apple/kernelcache.decoded')
    assert agx.pin()['sha256'] == '3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e'
    assert iogpu.pin()['sha256'] == '4fd8fd76c166696856e6b2c7450714272aacd5af821f28894a46e7e533c8fbed'
    assert kernel.pin()['sha256'] == '6158e1c0d591240808e26ff1da050b2fa0ed3eb17c1779d2ddde3171b959536f'
    report = {
        'schema': 'm4rch.native-t6040-ksm-resource-v7.static.v1',
        'method': 'Static matched symbols, chained vtables, getter leaves and source dataflow; no new execution tests',
        'inputs': [agx.pin(), iogpu.pin(), kernel.pin()],
        'kernelcache_receipt': 'docs/evidence/2026-10-09-matched-kernelcache-retrieval.json',
        'native_owner': {'function': '0xfffffe00089ee398', 'queue_resource_field': '0x70',
                         'owner_store': '0xfffffe00089ee640', 'class': 'AGXInternalResource',
                         'backing_field': '0x48', 'backing_class': 'IOGPUSysMemory',
                         'backing_factory': '0xfffffe000a804b6c',
                         'backing_factory_symbol': 'IOGPUSysMemory::withOptions(IOGPU*, task*, IOGPUDevice*, IOGPUResource*, u32, u64)'},
        'size': {'native_u32_alignment_slice': ['0xfffffe00089ee420', '0xfffffe00089ee430'],
                 'expression': '(capacity * record_bytes + alignment - 1) & -alignment (u32 wrapping)',
                 'page_rounding_slice': ['0xfffffe00089ed490', '0xfffffe00089ed4a8'],
                 'page_rounding': '(requested_size + kernel_page_size - 1) & -kernel_page_size',
                 'record_bytes_queue_field': '0x10', 'capacity_queue_field': '0x14',
                 'initial_sequence_fields': ['0x90', '0x48', '0x50']},
        'views': [
            {'role': 'device GPU VA', 'queue_field': '0x80', 'resource_mapping_field': '0x58',
             'backing_field': '0x48', 'creation_virtual_slot': '0x150',
             'options': '0x0000000600000085', 'task_getter': '0xfffffe000a7f9f18',
             'task_getter_symbol': 'IOGPU::getGPUTask() const', 'accelerator_task_field': '0xd0',
             'creation_call': '0xfffffe00089ee5bc', 'mapping_store': '0xfffffe00089ee608',
             'mapping_task_field': '0x20', 'task_identity_check': '0xfffffe00089ee60c',
             'address_getter_slot': '0x158', 'address_call': '0xfffffe00089ee668',
             'queue_address_store': '0xfffffe00089ee66c'},
            {'role': 'firmware GPU VA', 'queue_field': '0x88', 'resource_mapping_field': '0x50',
             'backing_field': '0x48', 'creation_virtual_slot': '0x150',
             'options': '0x0000000800000084', 'resource_task_field': '0x18',
             'accelerator_task_field': '0x11920', 'task_binding_slice': ['0xfffffe00089ed45c', '0xfffffe00089ed46c'],
             'creation_call': '0xfffffe00089ee498', 'mapping_store': '0xfffffe00089ee4e4',
             'address_getter_slot': '0x158', 'address_call': '0xfffffe00089ee6ac',
             'queue_address_store': '0xfffffe00089ee6b0'},
            {'role': 'CPU virtual alias', 'queue_field': '0x78', 'resource_mapping_field': '0x60',
             'backing_field': '0x48', 'descriptor_getter': '0xfffffe000a805a30',
             'descriptor_getter_symbol': 'IOGPUSysMemory::getMemoryDescriptor() const',
             'descriptor_cpu_map_virtual_slot': '0x228', 'descriptor_cpu_map_call': '0xfffffe00089ee544',
             'mapping_store': '0xfffffe00089ee548', 'address_getter_slot': '0x138',
             'address_call': '0xfffffe00089ee6f0', 'queue_address_store': '0xfffffe00089ee6f4'}],
        'vtable_closure': [
            iogpu.slot(0xfffffe000846d890, 0x150, 0xfffffe000a7c3af0),
            iogpu.slot(0xfffffe000847a298, 0x150, 0xfffffe000a7c3af0),
            iogpu.slot(0xfffffe0008479d30, 0x158, 0xfffffe000a803200),
            agx.slot(0xfffffe0007eae398, 0x8e8, 0xfffffe000a7f83a0),
            agx.slot(0xfffffe0007eae398, 0x9b0, 0xfffffe0008967098),
            agx.slot(0xfffffe0007eae398, 0xa98, 0xfffffe00089d9b10),
            agx.slot(0xfffffe0007eb1e78, 0x158, 0xfffffe000a803200),
            agx.slot(0xfffffe0007eb5c68, 0x158, 0xfffffe000a803200),
            kernel.slot(0xfffffe0007e47f00, 0x138, 0xfffffe000bf9b88c)],
        'getters': {'gpu_virtual_address': iogpu.gpu_address_leaf(0xfffffe000a803200),
                    'cpu_virtual_address': kernel.gpu_address_leaf(0xfffffe000bf9b88c)},
        'mapping_construction': {
            'memory_create_slot_symbol': 'IOGPUMemory::createGPUMappingInTask(IOGPUTask*, u64)',
            'memory_create_wrapper': '0xfffffe000a7c3af0', 'memory_create_full': '0xfffffe000a7c3ba8',
            'accelerator_create_map_slot': '0x8e8', 'accelerator_create_map': '0xfffffe000a7f83a0',
            'mapping_init': '0xfffffe000a802e2c',
            'retained_backing_store': '0xfffffe000a802eb8', 'retained_backing_field': '0x18',
            'task_store': '0xfffffe000a802e94', 'task_field': '0x20',
            'selected_hal_new_map': '0xfffffe00089d9b10', 'hal_policy_field': '0xecd4',
            'hal_null_policy_class': 'AGXLegacyMemoryMap', 'hal_nonzero_policy_class': 'AGXSecureMemoryMap',
            'both_classes_inherit_gpu_address_getter': True},
        'lifetime': {'prepare_function': '0xfffffe00089ed740', 'complete_function': '0xfffffe00089ed7c0',
                     'mapping_fields': ['0x50', '0x58'], 'prepare_count_field': '0x38',
                     'mapping_prepare': '0xfffffe000a8032a8', 'mapping_complete': '0xfffffe000a8032b4',
                     'mapping_backing_field': '0x18',
                     'native_prepare_rollback': 'If second mapping prepare fails, native completes the first mapping'},
        'source_spans': [
            agx.span(0xfffffe00089ee398, 0xfffffe00089ee718, 'KSM resource initialization and three address views'),
            agx.span(0xfffffe00089ed408, 0xfffffe00089ed588, 'one backing owner and firmware task binding'),
            agx.span(0xfffffe00089ed740, 0xfffffe00089ed830, 'both GPU mapping lifetime operations'),
            iogpu.span(0xfffffe000a7c3af0, 0xfffffe000a7c3dc8, 'GPU mapping creation from one memory owner'),
            iogpu.span(0xfffffe000a7f83a0, 0xfffffe000a7f8478, 'mapping subclass factory and initializer'),
            iogpu.span(0xfffffe000a802e2c, 0xfffffe000a802f18, 'retained task and shared memory owner'),
            agx.span(0xfffffe00089d9b10, 0xfffffe00089d9b60, 'selected G16 mapping subclasses')],
        'conclusion': {'same_native_backing_for_device_firmware_cpu': True,
                       'config_pair_order': ['device GPU VA', 'firmware GPU VA'],
                       'owned_scheduler_pair_experiment_order_agrees': True,
                       'actual_linux_page_table_aliasing_proved': False,
                       'hardware_or_firmware_consumption_proved': False,
                       'hardware_trial': False, 'new_execution_tests': False},
    }
    report['script'] = {'path': str(Path(__file__).resolve()),
                        'sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report['conclusion'], indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    prepare(parser.parse_args().output)
