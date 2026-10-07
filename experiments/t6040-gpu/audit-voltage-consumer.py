#!/usr/bin/env python3
"""Qualify the captured G16S profile-A voltage consumer, offline only."""
import argparse
import json
import struct
from pathlib import Path
from firmware_text_contract import qualify

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('text', type=Path)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
data = a.text.read_bytes()
contract = qualify(data)
# x19 receives main from root+18; main+0 is hardware. x8 starts0 and
# remains unwritten before the loop; x9 starts140c. Each loop increments
# x8 by4 and x9 by40(hex), exiting when x8==40(hex):16 rows.
checks = {0x2f2bc:0xd2800008,0x2f2c8:0xa9402933,
          0x2f4e4:0x52828189,0x2f4f8:0x14000006,
          0x2f4fc:0x91001108,0x2f504:0x91010129,
          0x2f508:0xf101011f,0x2f50c:0x54000640,
          0x2f510:0xf940026d,0x2f518:0xb94fc9ae,
          0x2f534:0xf940026f,0x2f538:0x8b0901ef,
          0x2f53c:0xd11011ef,0x2f540:0xb94001ef,
          0x2f54c:0xf940026f,0x2f550:0x8b0901ef,
          0x2f554:0xb85fc1ef,
          0x2f55c:0xf940026f,0x2f560:0x8b0901ef,
          0x2f564:0xd11001ef,0x2f568:0xb94001ef,
          0x2f570:0xf940026f,0x2f574:0xb86969ef,
          0x2f5bc:0x34fffa0e,0x2f5d0:0x17ffffcb}
for pc, expected in checks.items():
    if struct.unpack_from('<I',data,pc)[0] != expected:
        raise ValueError(f'instruction mismatch at{pc:x}')
report = dict(text_contract=contract,instruction_checks={hex(k):hex(v) for k,v in checks.items()},
              profile_a=dict(rows_read=16,row_stride=0x40,
                             core_columns=[0x1008,0x100c],sram_columns=[0x1408,0x140c],
                             frequency_base=0xfc8,frequency_stride=4,
                             core_storage_bytes=0x400,sram_storage_bytes=0x400),
              qualification='Manually reviewed bounded parser loop with hash-pinned firmware instructions. It reads profile-A columns0/1 across16 slots even when a frequency is zero. This establishes storage access, not16 active voltage groups. Current ADT decodes11 groups; mapping these to profile A/B remains unqualified. Profile-B semantics and firmware acceptance are not established by this loop.')
a.output.write_text(json.dumps(report,indent=2)+'\n')
print('Profile-A consumer:16 slots,40-hex stride, separate core/SRAM columns0/1 confirmed.')
