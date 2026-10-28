#!/usr/bin/env python3
"""Produce a lossless PQ/BT.2020 grayscale ramp for visual inspection."""
from array import array
from pathlib import Path
import subprocess, sys, tempfile
W,H=960,540
nits=[0.01,1,10,50,100,200,400,600]
def pq(n):
 m1=2610/16384; m2=2523/32; c1=3424/4096; c2=2413/128; c3=2392/128
 p=(n/10000)**m1
 return round(1023*((c1+c2*p)/(1+c3*p))**m2)
row=array('H',[pq(nits[x//(W//len(nits))]) for x in range(W)])
chroma=array('H',[512])*(W*H)
if sys.byteorder!='little': row.byteswap(); chroma.byteswap()
frame=row.tobytes()*H+chroma.tobytes()*2
out=Path(__file__).with_name('j614s-pq-ramp.mkv')
temp=Path(tempfile.gettempdir())/'m4rch-pq-raw.mkv'
cmd=['ffmpeg','-loglevel','error','-y','-f','rawvideo','-pixel_format','yuv444p10le','-video_size',f'{W}x{H}', '-framerate','1','-color_range','pc','-colorspace','bt2020nc','-color_primaries','bt2020','-color_trc','smpte2084','-i','pipe:0','-frames:v','1','-c:v','ffv1','-level','3','-color_range','pc','-colorspace','bt2020nc','-color_primaries','bt2020','-color_trc','smpte2084',str(temp)]
subprocess.run(cmd,input=frame,check=True)
subprocess.run(['ffmpeg','-v','error','-y','-i',str(temp),'-c:v','copy','-color_range','pc','-colorspace','bt2020nc','-color_primaries','bt2020','-color_trc','smpte2084',str(out)],check=True)
temp.unlink()
webm = Path(__file__).with_name('j614s-pq-ramp.webm')
subprocess.run(['ffmpeg','-v','error','-y','-i',str(out),'-vf','format=yuv420p10le','-c:v','libvpx-vp9','-lossless','1','-frames:v','1','-color_range','pc','-colorspace','bt2020nc','-color_primaries','bt2020','-color_trc','smpte2084',str(webm)],check=True)
print('left to right nits:',nits,'; 10-bit PQ codes:',[pq(x) for x in nits])
