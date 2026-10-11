//! Native command envelope fields from matched Apple numeric producers.
//! Caller first supplies native register-generator bytes and real owned input
//! descriptors. This never adapts donor commands or manufactures descriptors.
pub const DESCRIPTOR_BYTES:usize=0x1800;
pub const TA_BYTES:usize=0x9c0;
pub const FRAGMENT_BYTES:usize=0x2240;
fn get32(x:&[u8],o:usize)->u32{u32::from_le_bytes(x[o..o+4].try_into().unwrap())}
fn get64(x:&[u8],o:usize)->u64{u64::from_le_bytes(x[o..o+8].try_into().unwrap())}
fn put32(x:&mut[u8],o:usize,v:u32){x[o..o+4].copy_from_slice(&v.to_le_bytes());}
fn put64(x:&mut[u8],o:usize,v:u64){x[o..o+8].copy_from_slice(&v.to_le_bytes());}
fn cp(out:&mut[u8],d:usize,input:&[u8],s:usize,n:usize){out[d..d+n].copy_from_slice(&input[s..s+n]);}
pub struct TaBindings<'a>{pub context:&'a[u8],pub stack:&'a[u8],pub serial:u64,pub firmware_translations:[u64;3],pub completion_firmware:u64,pub x26:u64,pub w21:u32,pub w22:u32,pub accelerator_mode:u32,pub aperture_flags:u8}
pub fn tiling(command:&mut[u8],descriptor:&mut[u8],b:&TaBindings<'_>)->Option<()> {
 if command.len()!=TA_BYTES||descriptor.len()!=DESCRIPTOR_BYTES||b.context.len()!=0x600||b.stack.len()!=0x100||get32(descriptor,0x1388)>16{return None;}
 let c=b.context;let d=&mut*descriptor;let o=command;
 put32(o,0,0);put64(o,4,b.serial);
 for (dst,src,n) in [(0xc,0x1274,4),(0x8d6,0x1270,4),(0x48,0x127c,4),(0x18,0x1218,4),(0x1c,0x1258,4)]{cp(o,dst,d,src,n);}
 o[0x94d]=c[0x278];for(i,v)in b.firmware_translations.iter().enumerate(){put64(o,0x20+i*8,*v);}
 for(dst,src,n)in[(0x10,0x188,8),(0x780,0x1150,8),(0x788,0x1170,8),(0x79c,0x14d8,8),(0x7b6,0x1000,8),(0x7be,0x1008,8),(0x7d6,0x1090,8),(0x86e,0x86c,12),(0x91e,0x13d8,8),(0x926,0x13e0,8)]{cp(o,dst,d,src,n);}
 put32(o,0x7a4,u32::from(c[0x4e0]&1));let epoch=get64(d,0x14e8);put64(o,0x7a8,epoch&((1<<40)-1));o[0x7b0]=(epoch>>40)as u8;o[0x7b1]=o[0x7b0];
 o[0x7de..0x7f6].fill(0);o[0x7b2..0x7b6].fill(0);put32(o,0x86a,u32::from(d[0x868]&1));o[0x87a..0x88a].fill(0);cp(o,0x90e,c,0x3c8,16);
 put64(o,0x945,b.completion_firmware.wrapping_add(u64::from(get32(d,0x1430))));for(dst,src)in[(0x934,0x1408),(0x93d,0x1438),(0x8fe,0x878)]{cp(o,dst,d,src,8);}
 o[0x93c]=c[0x434]&1;put32(o,0x892,u32::from(c[0x13c]&1));put32(o,0x89a,u32::from(c[0x13f]&1));
 let mut branch=0;if b.accelerator_mode!=0&&(c[0x5c0]==1||c[0x5c0]==2)&&get32(d,0x1130)!=3{if b.accelerator_mode==3{branch=1;}else if b.accelerator_mode==1{branch=u32::from((c[0x13f]&1)^1);}}
 put32(o,0x89e,branch);o[0x8a2..0x8a6].fill(0);o[0x8f6..0x8fe].fill(0);cp(o,0x8a6,b.stack,0x40,8);put64(o,0x8ae,b.x26);put32(o,0x8b6,b.w21);put32(o,0x8ba,b.w22);cp(o,0x8be,b.stack,0x5c,4);cp(o,0x8c2,b.stack,0x50,4);
 for(dst,src,n)in[(0x8c6,0xe30,8),(0x8ce,0xe10,8),(0x866,0x1130,4)]{cp(o,dst,d,src,n);}
 let count=get32(d,0x1388);let mut flags=o[0x98e]&0xf2;if count!=0||c[0x390..0x3b0].iter().any(|v|*v!=0){flags|=1|((b.aperture_flags&3)<<2);cp(o,0x96e,d,0x1390,32);}o[0x98e]=flags;put64(d,0x13b0,0);put64(d,0x13b8,0xffffffff);
 if count!=0{let qid=get32(d,0x1274);for j in 0..count as usize{let address=get64(d,0x1288+j*16);let length=get32(d,0x1290+j*16);let dsid=d[0x1294+j*16];let size=u16::from_le_bytes(d[0x1296+j*16..0x1298+j*16].try_into().unwrap());let start=(u64::from(dsid)<<47)|(u64::from(qid)<<41)|(address>>7)|(1<<55);let end=(address>>7).wrapping_add(u64::from(length))|((1u64<<size.min(4))<<42)|(1<<41);put64(o,0x660+j*16,start);put64(o,0x668+j*16,end);}
 put64(d,0x13b0,get64(o,0x760).wrapping_add(0x600));put32(d,0x13b8,0);put32(d,0x13bc,count);}
 Some(())
}
const FRAGMENT_BODY:&[(usize,usize,usize)]=&[(64, 2208, 8), (72, 2232, 8), (80, 2248, 4), (84, 2256, 4), (88, 2240, 4), (112, 2280, 8), (120, 2296, 4), (7456, 1200, 8), (7472, 1208, 8), (7488, 1216, 8), (7504, 1248, 8), (7512, 1256, 8), (7520, 1264, 8), (7528, 1272, 8), (7536, 1280, 8), (7544, 1288, 8), (7552, 1296, 8), (7560, 1304, 8), (7568, 1312, 8), (7576, 1320, 8), (7584, 1328, 8), (7592, 1336, 8), (7600, 1344, 8), (7608, 1352, 8), (7616, 1360, 8), (7624, 1368, 8), (7632, 1376, 8), (7640, 1384, 8), (7648, 1392, 8), (7656, 1400, 8), (7664, 1408, 8), (7672, 1416, 8), (7680, 1424, 8), (7688, 1432, 8), (7696, 1440, 8), (7704, 1448, 8), (7712, 1456, 8), (7720, 1464, 8), (7728, 1472, 8), (7736, 1480, 8), (7744, 1488, 8), (7752, 1496, 8), (7760, 1504, 8), (7768, 1512, 8), (7776, 1520, 8), (7784, 1528, 8), (7792, 1536, 8), (7800, 1544, 8), (7808, 1552, 8), (7816, 1560, 8), (7824, 1568, 8), (7832, 1576, 8), (7840, 1584, 8), (7848, 1592, 8), (7856, 1600, 8), (7864, 1608, 8), (7872, 1616, 8), (7880, 1640, 8), (7888, 1736, 8), (7896, 1792, 8), (7976, 1704, 8), (7904, 1648, 16), (7920, 1784, 8), (7928, 1664, 8), (7936, 1752, 8), (7944, 1832, 8), (7984, 1728, 8), (7968, 1824, 8), (8008, 1872, 16), (8040, 1936, 8), (8048, 1944, 4), (8052, 1888, 16), (8080, 1956, 4), (8084, 1920, 16), (8104, 1960, 8), (8112, 1184, 4), (7992, 1856, 16), (8128, 1968, 8), (8136, 1984, 4), (8144, 1632, 8) ];
pub struct FragmentBindings<'a>{pub source:&'a[u8],pub frame:&'a[u8],pub stack:&'a[u8],pub context:&'a[u8],pub serial:u64,pub counter:u32,pub w21:u32,pub w22:u32,pub firmware_translations:[u64;3],pub completion_firmware:u64,pub epochs:[u64;2],pub capacity:u16,pub initial:u64,pub aperture_flags:u8}
pub fn fragment(command:&mut[u8],descriptor:&mut[u8],b:&FragmentBindings<'_>)->Option<()> {
 if command.len()!=FRAGMENT_BYTES||descriptor.len()!=DESCRIPTOR_BYTES||b.source.len()!=0x400||b.frame.len()!=24||b.stack.len()!=0x100||b.context.len()!=0x600||get32(descriptor,0xa70)>16||!(1..=256).contains(&b.capacity){return None;}
 let o=command;let d=&mut*descriptor;let c=b.context;put32(o,0,1);put64(o,4,b.serial);cp(o,0xc,d,0x144,4);o[0x21e7]=d[0x148];cp(o,0x2170,d,0x140,4);put32(o,0x2174,u32::from(d[0x960]==2));cp(o,0x2178,b.frame,0,24);put32(o,0x2100,u32::from(d[0x897]&1));put32(o,0x20f8,0);
 for(dst,src,n)in FRAGMENT_BODY{cp(o,*dst,d,*src,*n);}for(dst,src,n)in[(0x60,0x2f0,16),(0x1f10,0xa0,16),(0x1f88,0x1b4,8)]{cp(o,dst,b.source,src,n);}o[0x1fdc..0x20f0].fill(0);put32(o,0x1fd8,0);put32(o,0x20f0,0);
 put32(o,0x20fc,u32::from(d[0x88c]&1));cp(o,0x2208,d,0xc40,4);put32(o,0x2104,u32::from(d[0x868]&1));for(dst,src,n)in[(0x2108,0x86c,12),(0x21a8,0xab0,16),(0x21b8,0xac0,8),(0x21c0,0xac8,8),(0x21ce,0xb70,8),(0x2198,0x878,8),(0x21a0,0x880,8)]{cp(o,dst,d,src,n);}o[0x2114..0x2124].fill(0);let payload=b.counter as u8;o[0x90]=payload;o[0x220c]=d[0xc44];cp(o,0x2140,b.stack,0x50,8);cp(o,0x2148,b.stack,0x40,8);put32(o,0x2150,b.w21);put32(o,0x2154,b.w22);cp(o,0x2158,b.stack,0x4c,4);cp(o,0x215c,b.stack,0x48,4);
 o[0x21d6]=d[0xb9c]&1;cp(o,0x21d7,d,0xba0,8);if get64(d,0xb70)!=0{put64(o,0x21df,b.completion_firmware.wrapping_add(u64::from(get32(d,0xb98))));}cp(o,0x20,d,0x188,8);for(i,v)in b.firmware_translations.iter().enumerate(){put64(o,0x28+i*8,*v);}
 let event=get32(d,0x210);let epoch=b.epochs[(event>>31)as usize];let capacity=u64::from(b.capacity);let combined=((epoch<<24)|u64::from(event>>8)).wrapping_sub(1);let quotient=combined/capacity;let remainder=combined%capacity;let sum=(b.initial&255)+(remainder&255);let high=((b.initial>>8).wrapping_add(quotient).wrapping_add(sum/capacity))&0xffffffff;let timestamp=(high<<8)|((sum%capacity)&255)|(u64::from(payload)<<40);
 put64(d,0x178,timestamp);put64(o,0x2160,timestamp);put64(o,0x2190,0);for(i,v)in[c[0x2a5]&1,c[0x2a6]&1,d[0x88f]&1,d[0x893]&1].iter().enumerate(){put32(o,0x2124+i*4,u32::from(*v));}put32(o,0x2138,u32::from(d[0x895]&1));cp(o,0x2168,d,0x100,8);
 let count=get32(d,0xa70);let mut flags=o[0x222d]&0xf2;if count!=0||c[0x490..0x4b0].iter().any(|v|*v!=0){flags|=1|((b.aperture_flags&3)<<2);cp(o,0x220d,d,0xa78,32);}o[0x222d]=flags;o[0x222e..0x2232].fill(0);
 put64(d,0xa98,0);put64(d,0xaa0,0xffffffff);let qid=get32(d,0x144);
 for j in 0..count as usize{let address=get64(d,0x970+j*16);let length=get32(d,0x978+j*16);let dsid=d[0x97c+j*16];let size=u16::from_le_bytes(d[0x97e+j*16..0x980+j*16].try_into().unwrap());let start=(u64::from(dsid)<<47)|(u64::from(qid)<<41)|(address>>7)|(1<<55);let end=(address>>7).wrapping_add(u64::from(length))|((1u64<<size.min(4))<<42)|(1<<41);put64(o,0x6a0+j*16,start);put64(o,0x6a8+j*16,end);}
 if count!=0{put64(d,0xa98,get64(o,0x7a0).wrapping_add(0x600));put32(d,0xaa0,0);put32(d,0xaa4,count);}Some(())
}
