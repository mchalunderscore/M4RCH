#!/usr/bin/env python3
"""Execute full native ARM setup/power returns with explicit offline providers.

Extends the bounded saved lifecycle execution. It does not qualify the new
complete Rust producer or supply hardware/fuse results.
"""
import argparse
import importlib.util
import json
from pathlib import Path

import qualify_power_v7 as q


class FullNative(q.Native):
    def hook(self, ram, address, size, data):
        mnemonic, operands = self.instructions.get(address, ('', ''))
        if mnemonic == 'bl' and '0xfffffe000bf57650' in operands:
            # Native optional AON registry lookup. This experiment explicitly
            # supplies no dictionary; execute the native absent-service branch.
            self.calls.append(dict(kind='optional_aon_registry_lookup', result=0))
            self.setx(0, 0)
            ram.reg_write(q.reg.UC_ARM64_REG_PC, address + 4)
            return
        super().hook(ram, address, size, data)


def prepare(output):
    output.mkdir(parents=True, exist_ok=False)
    saved_path = q.ROOT / 'out/gpu-gravity-normal-boot-v6-source-evidence/native-power.json'
    saved = json.loads(saved_path.read_text())
    adt = next(Path(row['path']) for row in saved['source_pins'] if row['path'].endswith('/boot.adt'))
    parser_path = q.ROOT / 'experiments/t6040-gpu/adt.py'
    spec = importlib.util.spec_from_file_location('full_power_adt', parser_path)
    parser = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parser)
    node = parser.parse(adt.read_bytes())['/device-tree/arm-io/sgx']
    native = FullNative(node, 20000, 24, (bytes(8), bytes(48)))
    # Actual pointer roles, distinct RAM views. This links the accelerator's
    # firmware owner and gives the native full routine its statusB/AON owners.
    native.put64(q.ACC + 0x5b0, q.FW)
    native.put32(q.ACC + 0x4ec, 1)
    native.put64(q.FW + 0x960, q.FW + 0x20000)
    native.put64(q.FW + 0xc38, q.FW + 0x30000)
    native.put64(q.FW + 0xc30, 0xfffffc2000110000)
    native.ram.mem_write(q.HARDWARE, bytes(0x2718))
    native.execute(0x89ea270, owner=q.ACC)
    native.execute(0x89e9678, owner=q.ACC)
    native.execute(0x89cf0ec)
    native.execute(0x89cad50)
    fixtures = []
    for name, address, size in [('power', q.POWER, 0x6578),
                                ('hardware', q.HARDWARE, 0x2718),
                                ('region-c', q.REGION, 0xe58),
                                ('aonptd', q.FW + 0x30000, 0xe4)]:
        path = output / (name + '.bin')
        path.write_bytes(bytes(native.ram.mem_read(address, size)))
        fixtures.append(q.pin(path))
    spans = []
    for name, start, end in [('arm_setup', 0x89cf0ec, 0x89d0dd8),
                              ('arm_power', 0x89cad50, 0x89cd124)]:
        import hashlib
        raw = native.read_source(start, end-start)
        spans.append(dict(name=name, start=hex(start), end_exclusive=hex(end),
                          bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
    report = dict(schema='m4rch.native-t6040-full-arm-power-execution.v7',
        inputs=[q.pin(q.AGX), q.pin(__file__), q.pin(q.KIT / 'qualify_power_v7.py'),
                q.pin(adt), q.pin(parser_path)], source_spans=spans,
        full_arm_setup_returned=True, full_arm_power_returned=True,
        fixtures=fixtures, calls=native.calls,
        explicit_providers=dict(maximum_power_mw=20000, native_ticks=24,
            optional_aon_dictionary='absent', auxiliary_soc_die_count=1,
            controller_leakage_arrays='fresh zero RAM',
            secondary_frequencies='existing independent RAM fixture'),
        qualification='Full native control flow and normal returns only; not complete Rust output agreement.',
        complete_rust_producer_qualified=False, hardware_actions=[], triangle_trial_ready=False,
        remaining=['Bind actual primary/secondary performance and voltage input owners',
                   'Compare complete Rust power/hardware/RegionC/AON outputs against native RAM',
                   'Integrate one startup configuration-register read and owned GPU aliases'])
    (output / 'source-execution.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ['full_arm_setup_returned', 'full_arm_power_returned', 'triangle_trial_ready']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    prepare(parser.parse_args().output.resolve())
