"""Exercise the actual patched match predicate and preserve the idle sequence."""
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
import sys

PROJECT = Path(__file__).resolve().parents[1]

class IdleOptin(unittest.TestCase):
    def test_gate_and_unchanged_deep_path(self):
        cc = shutil.which('cc')
        if not cc:
            self.skipTest('C compiler unavailable')
        sys.path.insert(0, str(PROJECT / 'lib'))
        from hardware_profile import IDLE_OPTIN
        base = PROJECT / 'tests/fixtures/cpuidle-apple-base.c'
        self.assertEqual(hashlib.sha256(base.read_bytes()).hexdigest(), IDLE_OPTIN['base_source_sha256'])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / IDLE_OPTIN['source']
            source.parent.mkdir(parents=True)
            shutil.copyfile(base, source)
            subprocess.run(['git', 'apply', '--whitespace=error-all', str(PROJECT / IDLE_OPTIN['path'])], cwd=root, check=True, capture_output=True)
            patched = source.read_text()
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), IDLE_OPTIN['result_source_sha256'])
            for text in (base.read_text(), patched):
                sequence = text[text.index('asm('):text.index('static int __init apple_cpuidle_init')]
                if text == base.read_text():
                    original = sequence
                else:
                    self.assertEqual(sequence, original)
            match = re.search(r'if \(!\((.*?)\)\)\n\t\treturn 0;', patched, re.S)
            self.assertIsNotNone(match)
            program = '''#include <stdbool.h>
#include <string.h>
#include <assert.h>
static bool experimental_t6040_idle;
static const char *soc, *board;
static bool of_machine_is_compatible(const char *s) {
 return !strcmp(s, soc) || !strcmp(s, board);
}
static bool allowed(void) { return (''' + match[1] + '''); }
int main(void) {
 soc="apple,t6040"; board="apple,j614s";
 assert(!allowed()); experimental_t6040_idle=true; assert(allowed());
 board="apple,j616s"; assert(!allowed());
 board="apple,j614s"; soc="apple,t6041"; assert(!allowed());
 soc="apple,t6031"; experimental_t6040_idle=false; assert(allowed());
 soc="apple,unknown"; assert(!allowed());
}
'''
            (root/'gate.c').write_text(program)
            subprocess.run([cc,'-std=c11','-Wall','-Wextra','-Werror',str(root/'gate.c'),'-o',str(root/'gate')], check=True, capture_output=True)
            subprocess.run([str(root/'gate')],check=True)
            self.assertIn('bool, 0400)', patched)
            self.assertIn('static bool experimental_t6040_idle;', patched)
            self.assertIn('retention unqualified', patched)

if __name__ == '__main__':
    unittest.main()
