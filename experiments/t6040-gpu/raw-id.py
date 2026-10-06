#!/usr/bin/env python3
"""Offline interpretation of captured IDs; no register access or firmware gates.
Variant/revision fields follow pinned Asahi regs.rs. Counts use its G14X rule
and are a cross-check against ADT, not a qualified G16 execution layout.
"""
import argparse,json
REV={0:'A0',1:'A1',16:'B0',17:'B1',32:'C0',33:'C1'}
def decode(version,counts1,counts2,clusters):
 for word in [version,counts1,counts2,clusters]:
  if not isinstance(word,int) or not 0<=word<=0xffffffff:raise ValueError('Invalid raw u32')
 if version in [0,0xffffffff]:raise ValueError('Invalid ID register')
 generation=(version>>24)&255;variant=(version>>16)&255;revision=(version>>8)&255
 if generation!=10 or variant!=3 or revision not in REV:raise ValueError('Not a qualified captured T6040 ID family')
 slots=counts1&255;per_die=(counts1>>8)&255;dies=(counts1>>16)&15
 if slots!=10 or per_die!=2 or dies!=1:raise ValueError('Topology differs from captured J614s metadata')
 return {'raw_generation_code':generation,'variant_field':'S','revision_field':REV[revision],
         'counts_rule_cross_check':{'slots_per_cluster':slots,'clusters_per_die':per_die,'dies':dies,'total_slots':slots*per_die*dies},
         'active_core_masks':'ADT 0x3db/0x3db; not read by this four-register probe',
         'qualification':'Variant/revision interpretation and ADT-consistent topology cross-check only. Generic Asahi decoder still rejects generation10. No G16 firmware/queue/active-mask layout qualification.'}
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('words',nargs=4,type=lambda s:int(s,0));a=p.parse_args();print(json.dumps(decode(*a.words),indent=2))
