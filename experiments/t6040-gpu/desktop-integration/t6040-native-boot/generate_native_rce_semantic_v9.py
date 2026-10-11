from pathlib import Path
import re,json,hashlib,struct
ROOT=Path(__file__).resolve().parents[4]
KIT=ROOT/'experiments/t6040-gpu/desktop-integration/t6040-native-boot'
binary=Path('/boot/GPUC003/private-apple/com.apple.AGXG16X').read_bytes()
if hashlib.sha256(binary).hexdigest()!='3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e':raise ValueError('Native binary hash differs')
segments=[];cursor=32
for _ in range(struct.unpack_from('<I',binary,16)[0]):
 command,size=struct.unpack_from('<II',binary,cursor)
 if command==25:segments.append(struct.unpack_from('<QQQQ',binary,cursor+24))
 cursor+=size
def raw_word(address):
 for vm,_,off,n in segments:
  if vm<=address and address+4<=vm+n:return struct.unpack_from('<I',binary,off+address-vm)[0]
 raise ValueError('Instruction outside mapped source')
rows=[]
for l in (ROOT/'out/private-apple/agx-disassembly.txt').read_text().splitlines():
 m=re.match(r'([0-9a-f]{16}):\s+((?:[0-9a-f]{2} ){3}[0-9a-f]{2})\s+([a-z.]+)\s*(.*)',l)
 if m and (0xfffffe00089dd2c4<=int(m[1],16)<0xfffffe00089e2948):rows.append((int(m[1],16),int.from_bytes(bytes.fromhex(m[2]),'little'),m[3],m[4]))
def split(o):return re.findall(r'\[[^]]*\]!?|[^,\[\]]+',o.split(';')[0])
def reg(r):
 r=r.strip()
 if r in ('xzr','wzr'):return '0u64'
 if r=='sp':return 's.r[31]'
 return f'(s.r[{int(r[1:])}]'+ (' & 0xffff_ffffu64)' if r[0]=='w' else ')')
def value(r):
 r=r.strip()
 return str(int(r[1:],0)&((1<<64)-1))+'u64' if r.startswith('#') else reg(r)
def assign(r,e):
 r=r.strip()
 if r in ('wzr','xzr'):return ''
 idx=31 if r=='sp' else int(r[1:])
 return f's.r[{idx}] = ({e})'+(' & 0xffff_ffffu64' if r[0]=='w' else '')+';'
def shifted(parts,start):
 e=value(parts[start])
 if len(parts)>start+1:
  shift=parts[start+1].strip().split()
  op=shift[0]; n=int(shift[1][1:],0) if len(shift)>1 else 0
  if op in ('uxth','uxtw','sxtw'):
   if op=='sxtw':e=f'(({e} as u32 as i32 as i64) as u64)'
   else:e=f'({e}&{65535 if op=="uxth" else 4294967295}u64)'
   op='lsl'
  if op not in ('lsl','lsr'):raise ValueError(parts)
  e=f'({e}).wrapping_sh'+('l' if op=='lsl' else 'r')+f'({n})'
 return e
def memory(parts,j):
 p=parts[j].strip();m=re.match(r'\[([^,]+)(?:,\s*(#[^]]+))?\](!?)',p)
 if not m:raise ValueError(parts)
 base,imm,pre=m.groups();off=int(imm[1:],0) if imm else 0
 addr=f'({reg(base)}).wrapping_add({off & ((1<<64)-1)}u64)'
 before=assign(base,addr) if pre else ''
 if pre:addr=reg(base)
 after=assign(base,f'({reg(base)}).wrapping_add({int(parts[j+1].strip()[1:],0)}u64)') if len(parts)>j+1 else ''
 return before,addr,after
out=[];unsupported={}
for pc,word,n,o in rows:
 if raw_word(pc)!=word:raise ValueError('Disassembly differs from pinned native source')
 p=[x.strip() for x in split(o) if x.strip()];a=[]
 try:
  if n in ('pacibsp','pacda','autda','xpacd','hint'):pass
  elif n in ('ret','retab'):a=['next=s.r[30];']
  elif n in ('add','sub','and','orr','eor','bic','subs'):
   x,y=value(p[1]),shifted(p,2);op={'add':'wrapping_add','sub':'wrapping_sub','subs':'wrapping_sub'}.get(n)
   e=f'({x}).{op}({y})' if op else {'and':f'{x}&{y}','orr':f'{x}|{y}','eor':f'{x}^{y}','bic':f'{x}&!({y})'}[n]
   if n=='subs':a.append(f's.compare({x},{y},{32 if p[0][0]=="w" else 64},false);')
   a.append(assign(p[0],e))
  elif n in ('mov','movk'):
   if n=='mov':a.append(assign(p[0],value(p[1])))
   else:
    sh=int(p[2].split('#')[1],0) if len(p)>2 else 0
    a.append(assign(p[0],f'({reg(p[0])}&!({65535<<sh}u64))|({value(p[1])}<<{sh})'))
  elif n in ('cmp','cmn','tst'):
   x,y=value(p[0]),shifted(p,1)
   a.append(f's.logic({x}&{y},{32 if p[0][0]=="w" else 64});' if n=='tst' else f's.compare({x},{y},{32 if p[0][0]=="w" else 64},{str(n=="cmn").lower()});')
  elif n=='adrp':
   imm=((word>>5)&0x7ffff)<<2|((word>>29)&3)
   if imm&(1<<20):imm-=1<<21
   a.append(assign(p[0],str(((pc&~4095)+(imm<<12))&((1<<64)-1))+'u64'))
  elif n in ('ldr','ldrb','ldrh','ldur','str','strb','strh','stur','ldp','stp'):
   pair=n in ('ldp','stp');j=2 if pair else 1;b,addr,after=memory(p,j)
   size=1 if n.endswith('b') else 2 if n.endswith('h') else 4 if p[0][0]=='w' else 8
   a += [b,f'let address={addr};']
   for k in range(2 if pair else 1):
    ad=f'address.wrapping_add({k*size})'
    a.append(assign(p[k],f'ram.load({ad},{size})?') if n.startswith('ld') else f'ram.store({ad},{size},{value(p[k])})?;')
   a.append(after)
  elif n in ('lsl','lsr'):a.append(assign(p[0],f'({value(p[1])}).wrapping_sh'+('l' if n=='lsl' else 'r')+f'({int(p[2][1:],0)})'))
  elif n in ('bfi','bfxil','ubfiz'):
   l,w=int(p[2][1:],0),int(p[3][1:],0);mask=(1<<w)-1
   if n=='bfi':e=f'({reg(p[0])}&!({mask<<l}u64))|(({reg(p[1])}&{mask}u64)<<{l})'
   elif n=='bfxil':e=f'({reg(p[0])}&!({mask}u64))|(({reg(p[1])}>>{l})&{mask}u64)'
   else:e=f'({reg(p[1])}&{mask}u64)<<{l}'
   a.append(assign(p[0],e))
  elif n=='csel':a.append(assign(p[0],f'if s.condition("{p[3]}") {{ {value(p[1])} }} else {{ {value(p[2])} }}'))
  elif n=='cset':a.append(assign(p[0],f'u64::from(s.condition("{p[1]}"))'))
  elif n in ('b','bl') or n.startswith('b.'):
   imm=word&0x3ffffff if n in ('b','bl') else (word>>5)&0x7ffff
   bits=26 if n in ('b','bl') else 19
   if imm&(1<<(bits-1)):imm-=1<<bits
   target=(pc+imm*4)&((1<<64)-1)
   if n=='bl':a.append(f's.r[30]={pc+4}u64;')
   code=f'next={target}u64;'
   a.append(f'if s.condition("{n[2:]}") {{ {code} }}' if n.startswith('b.') else code)
  elif n in ('cbz','cbnz','tbz','tbnz'):
   imm=(word>>5)&(0x7ffff if n.startswith('cb') else 0x3fff);bits=19 if n.startswith('cb') else 14
   if imm&(1<<(bits-1)):imm-=1<<bits
   expr=value(p[0]) if n.startswith('cb') else f'({value(p[0])}&(1u64<<{int(p[1][1:],0)}))'
   a.append(f'if {expr} '+('==' if n in ('cbz','tbz') else '!=')+f' 0 {{ next={(pc+imm*4)&((1<<64)-1)}u64; }}')
  elif n=='blraa':a += [f's.r[30]={pc+4}u64;',f'next={value(p[0])};']
  elif n=='brk':a.append('return Err(Error::Trap);')
  else:raise ValueError(n)
  out.append(f'{pc}u64 => {{ '+''.join(a)+' },')
 except Exception as e:unsupported.setdefault(n,[]).append((hex(pc),o,str(e)))
print('instructions',len(rows),'unsupported',json.dumps({k:v[:3] for k,v in unsupported.items()},indent=2))
if unsupported:raise SystemExit(1)
header='''// Private, locally generated semantic producer. Do not redistribute Apple source.
#![allow(unused_parens)]
#[derive(Debug, PartialEq)] pub enum Error { Unmapped, Trap, Budget, Unknown(u64) }
pub trait Ram { fn load(&mut self,a:u64,n:usize)->Result<u64,Error>; fn store(&mut self,a:u64,n:usize,v:u64)->Result<(),Error>; }
pub struct State { pub r:[u64;32], pub pc:u64, n:bool,z:bool,c:bool,v:bool }
impl State {
 pub fn new(pc:u64)->Self { Self{r:[0;32],pc,n:false,z:false,c:false,v:false} }
 fn logic(&mut self,x:u64,b:u32){let mask=if b==32 {0xffff_ffff}else{u64::MAX};self.z=x&mask==0;self.n=x&(1u64<<(b-1))!=0;self.c=false;self.v=false;}
 fn compare(&mut self,a:u64,b:u64,bits:u32,add:bool){let mask=if bits==32 {0xffff_ffff}else{u64::MAX};let a=a&mask;let b=b&mask;let result=if add{a.wrapping_add(b)}else{a.wrapping_sub(b)}&mask;self.z=result==0;let sign=1u64<<(bits-1);self.n=result&sign!=0;self.c=if add{(a as u128+b as u128)>(mask as u128)}else{a>=b};self.v=if add{(!(a^b)&(a^result)&sign)!=0}else{((a^b)&(a^result)&sign)!=0};}
 fn condition(&self,c:&str)->bool{match c{"eq"=>self.z,"ne"=>!self.z,"lo"=>!self.c,"hi"=>self.c&&!self.z,"ls"=>!self.c||self.z,"gt"=>!self.z&&self.n==self.v,_=>false}}
}
pub fn produce<R:Ram>(ram:&mut R,s:&mut State,stop:u64,mapped:u64)->Result<(),Error>{
 for _ in 0..200000 {if s.pc==stop{return Ok(())} let mut next=s.pc.wrapping_add(4);
 match s.pc {
 0xfffffe00089e7fe4=>{s.r[0]=1;next=s.r[30];},
 0xfffffe00089e7fd8=>{s.r[0]=2;next=s.r[30];},
 0x231000=>{s.r[0]=mapped;next=s.r[30];},
'''
# Range includes getter? no.
text=header+'\n'.join(out)+'\n _=>return Err(Error::Unknown(s.pc)), } s.pc=next; } Err(Error::Budget) }\n'
dest=ROOT/'out/private-apple/native-rce-semantic-v9.rs';dest.write_text(text)

print(dest)
