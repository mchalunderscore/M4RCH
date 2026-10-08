#!/usr/bin/env python3
"""Sweep copied native client flag combinations through the complete 3D recipe."""
import argparse,hashlib,json,struct,sys
from pathlib import Path
from private_render_setup import copy_payload
p=argparse.ArgumentParser(description=__doc__);p.add_argument('macho',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
checker=Path(__file__).with_name('trace-private-3d-field-registers.py');ns={'__file__':str(checker)};old=sys.argv;sys.argv=[str(checker),str(a.macho),str(a.output)]
try:exec(compile(checker.read_text().split('baseline=run(initial);observations=[]')[0],str(checker),'exec'),ns)
finally:sys.argv=old
base=bytearray(0x1800);base[:0x1000]=ns['initial'];source_offsets=[0x7d8,0x7d9,0x7da,0x7db,0x7dc,0x7dd,0x7de];fixtures=[];values={}
for mask in range(128):
 payload=bytearray(0x900)
 for i,o in enumerate(source_offsets):payload[o]=(mask>>i)&1
 desc=bytearray(copy_payload(base,payload))
 # Restore only non-client fixtures required by the full generator harness.
 for off,v in [(0x190,ns['O']),(0x918,ns['O']),(0xb90,ns['ns']['R1'])]:struct.pack_into('<Q',desc,off,v)
 result=ns['run'](desc);key=(0x16068,0,0);value=result[0][key];values[hex(value)]=values.get(hex(value),0)+1
 fixtures.append({'mask':mask,'enabled_payload_offsets':[hex(o) for i,o in enumerate(source_offsets) if mask>>i&1],'tile_state':hex(value),'phase_counts':[len(x) for x in result],'primary_has160b8':(0x160b8,0,0) in result[0]})
# Derive independent single-toggle differences from the all-clear baseline;
# report overlaps/interactions rather than assert an OR model without evidence.
baseval=int(fixtures[0]['tile_state'],0);single=[]
for i,o in enumerate(source_offsets):
 v=int(fixtures[1<<i]['tile_state'],0);single.append({'payload_byte_offset':hex(o),'xor_from_clear':hex(v^baseval),'clear_bits':hex(baseval&~v),'set_bits':hex(v&~baseval)})
report={'private_binary_sha256':ns['ns']['sha'],'cases':128,'source_offsets':[hex(o) for o in source_offsets],'fixtures':fixtures,'unique_tile_states':values,'single_toggles':single,'donor_low_default_matches':[f['mask'] for f in fixtures if int(f['tile_state'],0)&0xffffffff==0x3717f],'qualification':'Full native 3D generator consumes source flags through the independently qualified payload-copy model in emulator RAM. All128 combinations of seven boolean input bytes; other payload fields zero and provider objects synthetic. Flags labeled by input offset, not unproven semantic names. Counts include conditional/SPM backing entries, not exported phase0 count. No live hardware, descriptor validity or correct flags for a triangle established. Single-toggle differences are observations, not an exhaustive bitfield specification.'}
a.output.write_text(json.dumps(report,indent=2)+'\n');print('128 native flag combinations:',len(values),'tile-state values;',report['single_toggles'],'donor default matches',report['donor_low_default_matches'])
