from pathlib import Path
import subprocess,tempfile,sys
if len(sys.argv) != 2:
    raise SystemExit('Usage: test-asahi-pending-close.py PATH_TO_LIFETIME_RS')
source = Path(sys.argv[1])
s=source.read_text()
start=s.index('    pub(super) fn supersede_pending_close(')
openbrace=s.index('{',start)
depth=1;i=openbrace+1
while depth:
 if s[i]=='{': depth+=1
 elif s[i]=='}': depth-=1
 i+=1
func=s[start:i].replace('pub(super) fn','fn')
rust='''use std::sync::{Arc,Mutex as StdMutex};
type ARef<T> = Arc<T>;
mod gem { pub struct Object(pub u32); }
struct Lock<T>(StdMutex<T>); impl<T> Lock<T> { fn lock(&self)->std::sync::MutexGuard<'_,T>{self.0.lock().unwrap()} }
struct State { objects: Vec<ARef<gem::Object>> }
struct Lifetime { state: Lock<State> }
struct Vm { lifetime: Option<Arc<Lifetime>> }
impl Vm {
'''+func+'''\n}
fn main() {
 let a=Arc::new(gem::Object(1));let b=Arc::new(gem::Object(2)); let unrelated=Arc::new(gem::Object(1));
 let l=Arc::new(Lifetime{state:Lock(StdMutex::new(State{objects:vec![a.clone(),b.clone()]}))});let v=Vm{lifetime:Some(l.clone())};
 assert!(v.supersede_pending_close(&unrelated).is_none());
 let saved=v.supersede_pending_close(&a).unwrap();assert!(Arc::ptr_eq(&saved,&a));
 assert_eq!(l.state.lock().objects.len(),1);assert!(Arc::ptr_eq(&l.state.lock().objects[0],&b));
 assert!(v.supersede_pending_close(&a).is_none());assert_eq!(saved.0,1);
 assert!(Vm{lifetime:None}.supersede_pending_close(&b).is_none());
}
'''
with tempfile.TemporaryDirectory() as d:
 p=Path(d)/'test.rs';p.write_text(rust)
 subprocess.run(['rustc','--edition=2021',str(p),'-o',str(Path(d)/'test')],check=True)
 subprocess.run([str(Path(d)/'test')],check=True)
print('pending-close cancellation tests passed')
