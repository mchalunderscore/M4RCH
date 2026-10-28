#!/usr/bin/env python3
"""Experimental EDID for J614s, used only by the opt-in HDR diagnostic."""
import math
from pathlib import Path

edid = bytearray(256)
edid[:8] = bytes.fromhex('00 ff ff ff ff ff ff 00')
# Synthetic M4R identity, no serial. The color primaries are nominal Display P3,
# not a measurement of this unit. Timings do not replace the DCP mode catalog.
manufacturer = (13 << 10) | (4 << 5) | 18
edid[8:10] = manufacturer.to_bytes(2, 'big')
edid[10:12] = (0x614).to_bytes(2, 'little')
edid[16:25] = bytes([1, 34, 1, 4, 0xb5, 30, 20, 120, 0x02])
primaries = (0.680, 0.320, 0.265, 0.690, 0.150, 0.060, 0.3127, 0.3290)
p = [round(x * 1024) for x in primaries]
edid[25] = ((p[0]&3)<<6)|((p[1]&3)<<4)|((p[2]&3)<<2)|(p[3]&3)
edid[26] = ((p[4]&3)<<6)|((p[5]&3)<<4)|((p[6]&3)<<2)|(p[7]&3)
edid[27:35] = bytes(x >> 2 for x in p)
edid[35:38] = b'\x20\0\0'
edid[38:54] = b'\x01\x01' * 8
# The firmware's 60 Hz timing, 3024x1964, htotal 3104, vtotal 2160.
d = bytearray(18); d[0:2] = round(3104*2160*60/10000).to_bytes(2,'little')
h, hb, v, vb = 3024, 80, 1964, 196
d[2:8] = bytes([h&255,hb&255,((h>>8)<<4)|(hb>>8),v&255,vb&255,((v>>8)<<4)|(vb>>8)])
# H front 8, width 32, V front 38, width 8; preserve total blanking.
d[8:12] = bytes([8,32,((38&15)<<4)|8,((38>>4)&3)<<2])
d[12:15] = bytes([302&255,196&255,((302>>8)<<4)|(196>>8)])
d[17]=0x1a
edid[54:72]=d
edid[72:90]=bytes.fromhex('00 00 00 fc 00') + b'J614s HDR lab'  # 13 characters
edid[90:108]=bytes.fromhex('00 00 00 10 00')+bytes(13)
edid[108:126]=bytes.fromhex('00 00 00 10 00')+bytes(13)
edid[126]=1; edid[127]=(-sum(edid[:127]))&255
# CTA-861: BT.2020 RGB, PQ and static metadata type 1. HDR luminance is
# deliberately capped to 600 nits while the physical backlight stays <= 600.
cta=edid[128:]
cta[:4]=bytes([2,3,18,0x80])
cta[4:8]=bytes.fromhex('e3 05 80 00')
cta[8:15]=bytes([0xe6,0x06,0x05,0x01,int(32*math.log2(600/50)),int(32*math.log2(600/50)),0])
cta[15:18]=bytes.fromhex('e2 00 40')
cta[127]=(-sum(cta[:127]))&255
edid[128:]=cta
assert len(edid)==256 and sum(edid[:128])%256==sum(edid[128:])%256==0
Path(__file__).with_name('j614s-test-edid.bin').write_bytes(edid)
