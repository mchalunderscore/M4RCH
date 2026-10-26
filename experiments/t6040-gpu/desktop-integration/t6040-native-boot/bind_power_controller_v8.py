#!/usr/bin/env python3
"""Bind native controller predecessors in offline RAM; never touch GPU hardware."""
import argparse
import importlib.util
import json
from pathlib import Path
import qualify_power_v7 as q
from prepare_power_complete_v7 import FullNative


def bind_controller_predecessors(native):
    """Bind the raw sample period before the actual selected controller runs.

    edac is milliseconds from gpu-power-sample-period, distinct from edb0's
    gpu-pwr-sample-period-aic-clks. Firmware tags use the selected J614 geometry
    (two GPU clusters, one auxiliary SoC die), not perf voltage table counts.
    """
    period = native.properties['gpu-power-sample-period']
    if len(period) != 4 or int.from_bytes(period, 'little') == 0:
        raise ValueError('invalid raw GPU sample period')
    native.put32(q.ACC + 0xedac, int.from_bytes(period, 'little'))
    native.put32(q.ACC + 0x4e4, 2)
    native.put32(q.ACC + 0x4ec, 1)


def main(output):
    output.mkdir(parents=True, exist_ok=False)
    saved=json.loads((q.ROOT/'out/gpu-gravity-normal-boot-v6-source-evidence/native-power.json').read_text())
    adt=next(Path(r['path']) for r in saved['source_pins'] if r['path'].endswith('/boot.adt'))
    parser_path=q.ROOT/'experiments/t6040-gpu/adt.py'
    spec=importlib.util.spec_from_file_location('controller_adt',parser_path)
    parser=importlib.util.module_from_spec(spec);spec.loader.exec_module(parser)
    n=FullNative(parser.parse(adt.read_bytes())['/device-tree/arm-io/sgx'],20000,24,(bytes(8),bytes(48)))
    n.put64(q.ACC+0x5b0,q.FW)
    n.put64(q.FW+0x960,q.FW+0x20000)
    n.put64(q.FW+0xc38,q.FW+0x30000)
    n.put64(q.FW+0xc30,0xfffffc2000110000)
    n.put64(q.FW+0x3a8,0xfffffc20003c3180)
    n.ram.mem_write(q.HARDWARE,bytes(0x2718))
    bind_controller_predecessors(n)
    for entry,owner in [(0x89ea270,q.ACC),(0x89e9678,q.ACC),(0x89cf0ec,q.FW),(0x89cad50,q.FW)]:
        n.execute(entry,owner=owner)
    fixtures=[]
    for name,address,size in [('power',q.POWER,0x6578),('hardware',q.HARDWARE,0x2718),('region-c',q.REGION,0xe58),('aonptd',q.FW+0x30000,0xe4)]:
        p=output/(name+'.bin');p.write_bytes(bytes(n.ram.mem_read(address,size)));fixtures.append(q.pin(p))
    draft=q.ROOT/'out/gpu-gravity-full-power-draft-comparison-v1/power.bin'
    a=draft.read_bytes();b=(output/'power.bin').read_bytes()
    mismatch=[dict(offset=hex(i),draft_u32=int.from_bytes(a[i:i+4],'little'),native_u32=int.from_bytes(b[i:i+4],'little')) for i in range(0,len(a)-3,4) if a[i:i+4]!=b[i:i+4]]
    report=dict(schema='m4rch.native-power-controller-provider.v8',inputs=[q.pin(__file__),q.pin(q.AGX),q.pin(adt),q.pin(parser_path),q.pin(q.KIT/'qualify_power_v7.py'),q.pin(q.KIT/'prepare_power_complete_v7.py'),q.pin(draft)],
        native_sustained_controller_returned=True,sustained_call_site='0x89637d4',sustained_selected_target='0x8960a28',native_full_setup_returned=True,native_full_power_returned=True,
        providers=dict(sample_period_ms=8,accelerator_sample_period_offset='0xedac',gpu_clusters=2,auxiliary_soc_die_count=1,maximum_power_mw=20000,ticks=24,support26_gpu='0xfffffc20003c3180',optional_aon_dictionary='absent'),
        entrypoints=['0x89ea270','0x89e9678','0x89cf0ec','0x89cad50'],calls=n.calls,fixtures=fixtures,power_mismatches=mismatch,
        tags_source=dict(entry='0x89e92fc',gpu_tag_table='0x712dff0',gpu_tags_dest='power+0x6320',aux_tag='0x72305452'),
        limitations=['Secondary frequency CPU owner remains independent fixture','Native sustained defaults must not be replaced with draft constants to manufacture agreement'],hardware_actions=[],triangle_trial_ready=False)
    (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(report=str(output/'report.json'),power_mismatches=mismatch)))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);main(p.parse_args().output.resolve())
