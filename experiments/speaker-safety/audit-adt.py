#!/usr/bin/env python3
"""Inspect only J614 speaker metadata in a saved ADT; never access hardware."""
import importlib.util, json, struct, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('m4rch_adt', ROOT/'experiments/speaker-safety/adt.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
source = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT/'out/external-investigation/private/current.adt'
tree = module.parse(source.read_bytes())
amp = tree['/device-tree/arm-io/i2c1/audio-speaker']
audio = tree['/device-tree/product/audio']
phandles = {}
for path, props in tree.items():
    raw = props.get('AAPL,phandle', b'')
    if len(raw) == 4:
        number = struct.unpack('<I', raw)[0]
        if number in phandles: raise ValueError('duplicate phandle')
        phandles[number] = (path, props)
config = amp['speaker-config']
if len(config) != 24: raise ValueError('expected six four-byte speaker configurations')
rows = []
for i, key in enumerate(['AAPL,phandle']+[f'speaker{i}' for i in range(1,6)]):
    path, props = phandles[struct.unpack('<I', amp[key])[0]]
    if b'sn012776' not in props.get('compatible', b''): raise ValueError('unexpected amp type')
    rx,gain,m1n1_vs,m1n1_is = config[i*4:i*4+4]
    rows.append({'index':i,'adt_path':path,'i2c_address':struct.unpack_from('<I',props['reg'])[0],
                 'rx_slot':rx,'amp_gain_raw':gain,'raw_sense_slot_3':m1n1_vs,'raw_sense_slot_4':m1n1_is})
x = audio['speaker-thiele-small']
if len(x) != 4 + 6*22 + 2: raise ValueError('unexpected speaker calibration structure')
calibration = []
for i in range(6):
    _, resistance, temp, _, _, _, name = struct.unpack('<IHHIIH4s', x[4+i*22:4+(i+1)*22])
    calibration.append({'index':i,'name_fourcc':name[::-1].decode('ascii'),
                        'r_mohm_per_m1n1':resistance,'temperature_raw':temp})
print(json.dumps({'source':'saved J614s ADT; no live hardware access',
                  'speakers':rows,'thiele_small_records':calibration,
                  'speaker_config_interpretation':'m1n1 labels bytes 3/4 vsense/isense; Aurora J616 DTS assigns corresponding slots imon/vmon; polarity requires reconciliation',
                  'speaker_protection_adt':struct.unpack('<I',amp['speaker-protection'])[0],
                  'reset_raw':amp['function-reset'].hex(),'interrupts_raw':amp['interrupts'].hex(),
                  'idle_mask_rows_raw':amp['amp-tx-zd-config'][:16].hex(),
                  'limitations':['Calibrated resistance does not establish speakersafetyd thermal model', 'Slot polarity and mapping require independent validation']},indent=2))
