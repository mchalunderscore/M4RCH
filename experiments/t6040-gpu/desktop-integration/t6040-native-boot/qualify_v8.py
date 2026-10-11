#!/usr/bin/env python3
"""Compose frozen v7 queue proofs and complete v8 power output agreement."""
import argparse
import json
from pathlib import Path
from stage_v4 import pin

KIT = Path(__file__).resolve().parent
ROOT = KIT.parents[3]


def checked(path):
    value = json.loads(path.read_text())
    for row in value['inputs']:
        if pin(row['path']) != row:
            raise ValueError('Qualified input changed: ' + row['path'])
    return value


def qualify(staging):
    receipt = staging / 'stage-receipt.json'
    stage = json.loads(receipt.read_text())
    if stage['schema'] != 'm4rch.gravity-native-t6040-components.stage.v8':
        raise ValueError('Native v8 stage required')
    for row in stage['inputs'] + stage['source_files']:
        if pin(row['path']) != row:
            raise ValueError('Stage input changed: ' + row['path'])
    v7 = ROOT / 'out/gpu-gravity-normal-boot-v7'
    prior_path = v7 / 'qualification-v1/qualification.json'
    prior = checked(prior_path)
    assert prior['complete'] and prior['joined_queue_owner_run'] == 0
    power_path = ROOT / 'out/gpu-gravity-native-complete-power-v8-qualification-v2/qualification.json'
    power = checked(power_path)
    assert power['whole_outputs_agree']
    source = staging / 'source/linux/drivers/gpu/drm/asahi'
    base = v7 / 'source/linux/drivers/gpu/drm/asahi'
    changed = []
    for row in stage['source_files']:
        relative = Path(row['path']).relative_to(source)
        if Path(row['path']).read_bytes() != (base / relative).read_bytes():
            changed.append(str(relative))
    assert sorted(changed) == sorted(['g16.rs','g16_platform.rs','g16_power.rs','g16_t6040_power.rs'])
    assert (source / 'g16_t6040_power.rs').read_bytes() == (KIT / 'g16_t6040_power_complete_v7.rs').read_bytes()
    text = (source / 'g16.rs').read_text()
    assert text.index('!crate::g16_t6040_power::POWER_COMPLETE') < text.index('let asc = KBox::pin_init')
    assert text.count('PERF_STATE_MAP_REG_OFFSETS[0]') == 1
    assert text.count('PERF_STATE_MAP_REG_OFFSETS[1]') == 1
    assert text.index('firmware_space.write(0xffff_fc20_0011_0000, &native_aonptd)?;') < text.index('session.publish(pdev)?')
    component = (source / 'g16_t6040_power.rs').read_text()
    assert 'POWER_COMPLETE: bool = true;' in component
    assert 'BUNDLE_COMPLETE: bool = false;' in (source / 'g16_t6040_bundle.rs').read_text()
    output = staging / 'qualification-v1'
    output.mkdir(exist_ok=False)
    report = dict(schema='m4rch.gravity-native-t6040-components.qualification.v8',
        inputs=[pin(receipt),pin(__file__),pin(KIT/'stage_v4.py'),pin(prior_path),pin(power_path)]
            + stage['inputs'] + stage['source_files'] + prior['inputs'] + power['inputs'],
        complete=True, scope='Frozen unchanged queue ownership proof composition, complete power output agreement, and source integration continuity; module build separate',
        changed_source_files=changed, joined_queue_owner_compile=prior['joined_queue_owner_compile'],
        joined_queue_owner_run=prior['joined_queue_owner_run'],
        composed_without_repeating_native_codec_tests=True,
        complete_power_whole_outputs_agree=True, power_complete=True,
        region_c_complete=False, bundle_complete=False, normal_startup_enabled=False,
        hardware_actions=[], triangle_trial_ready=False)
    (output / 'qualification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'complete':True,'power_complete':True,'triangle_trial_ready':False}))

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('staging', type=Path)
    qualify(parser.parse_args().staging.resolve())
