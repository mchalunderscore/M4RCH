import ast
from pathlib import Path
import unittest
class ABIResults(unittest.TestCase):
 def setUp(self):
  source=(Path(__file__).resolve().parents[1]/'experiments/t6040-sme/abi-run.py').read_text();tree=ast.parse(source)
  function=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='classify');ns={};exec(compile(ast.Module(body=[function],type_ignores=[]),'classify','exec'),ns);self.classify=ns['classify']
 def test_signal_four_is_not_kselftest_skip(self):
  self.assertEqual(self.classify(-4,''),'fail');self.assertEqual(self.classify(4,'SKIP'),'skip')
 def test_tap_failure_overrides_zero_exit(self):
  self.assertEqual(self.classify(0,'TAP version 13\nnot ok 1 broken\n'),'fail')
 def test_zero_exit_with_all_tests_skipped_is_not_coverage(self):
  self.assertEqual(self.classify(0,'ok 1 # SKIP unavailable\nok 2 # SKIP absent'),'skip')
 def test_success_and_timeout(self):
  self.assertEqual(self.classify(0,'ok 1 restored'),'pass');self.assertEqual(self.classify(124,''),'fail')
