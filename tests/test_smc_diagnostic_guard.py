import importlib.util
from pathlib import Path
import struct
import unittest

p=Path(__file__).resolve().parents[1]/'experiments/smc-readonly/verify.py'
spec=importlib.util.spec_from_file_location('smc_guard',p)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class KernelNotesGuardTests(unittest.TestCase):
    def note(self,name,kind,desc):
        return struct.pack('<III',len(name),len(desc),kind)+name+b'\0'*((-len(name))%4)+desc+b'\0'*((-len(desc))%4)

    def test_locates_build_id_after_other_kernel_notes(self):
        notes=self.note(b'Linux\0',0,b'abc')+self.note(b'GNU\0',3,bytes(range(20)))
        self.assertEqual(module.build_id(notes),bytes(range(20)).hex())

    def test_rejects_missing_or_truncated_build_id(self):
        for data in (b'',self.note(b'GNU\0',2,b'a'),self.note(b'GNU\0',3,b'abcdefgh')[:-2]):
            with self.assertRaises(ValueError):module.build_id(data)


cp=Path(__file__).resolve().parents[1]/'experiments/smc-readonly/capture.py'
cs=importlib.util.spec_from_file_location('smc_capture',cp)
capture=importlib.util.module_from_spec(cs);cs.loader.exec_module(capture)


class SMCRecordTests(unittest.TestCase):
    def records(self):
        return '\n'.join(f'{i+1} {key} info=0 size={size} '
                         f'type={"75693820" if size==1 else "666c7420"} '
                         f'flags=85 read={size} raw={"00"*size}'
                         for i,(key,size) in enumerate(capture.KEY_SIZES.items()))

    def test_accepts_exact_reads_including_valid_zero_floats(self):
        capture.validate_records(self.records())

    def test_rejects_individual_errors_short_reads_and_missing_records(self):
        raw=self.records()
        variants=[raw.replace('info=0','info=-5',1),
                  raw.replace('read=4','read=-5',1),
                  raw.replace('read=4','read=3',1),
                  raw.replace('raw=00000000','raw=000000',1),
                  raw.replace('type=666c7420','type=75693820',1),
                  raw+'\n'+raw.splitlines()[0],
                  '\n'.join(raw.splitlines()[1:]),
                  raw.replace('2 Te0S','0 Te0S'),raw+'\nbad']
        for value in variants:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):capture.validate_records(value)

    def test_accepts_both_actual_native_captures(self):
        import json
        root=Path(__file__).resolve().parents[1]/'out/native-returns/20261005-round5/main'
        if not root.exists():self.skipTest('Private native captures unavailable')
        for folder in ('smc-baseline','smc-optimized'):
            for line in (root/folder/'samples.jsonl').read_text().splitlines():
                capture.validate_records(json.loads(line)['raw'])


class BoundedSMCArguments(unittest.TestCase):
    def test_existing_short_capture_and_explicit_long_capture(self):
        self.assertEqual(capture.parse_args(['new']).samples,30)
        self.assertEqual(capture.parse_args(['new','--samples','720']).samples,720)

    def test_arbitrary_or_unbounded_sample_counts_are_refused(self):
        import contextlib,io
        for n in ('0','-1','999999','31'):
            with self.subTest(samples=n):
                with contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit):capture.parse_args(['new','--samples',n])
