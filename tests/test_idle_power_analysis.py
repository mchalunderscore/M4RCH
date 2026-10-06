import importlib.util
from pathlib import Path
import unittest
P=Path(__file__).resolve().parents[1]/'experiments/t6040-idle/power/analyse.py'
s=importlib.util.spec_from_file_location('analysis',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Analysis(unittest.TestCase):
 def test_discharge_conversion_and_charging_exclusion(self):
  value='POWER_SUPPLY_TYPE=Battery\nPOWER_SUPPLY_STATUS=Discharging\nPOWER_SUPPLY_CURRENT_NOW=-1000000\nPOWER_SUPPLY_VOLTAGE_NOW=12000000'
  self.assertEqual(m.battery_watts({'/battery/uevent':value})[0]['watts'],12)
  self.assertEqual(m.battery_watts({'/battery/uevent':value.replace('Discharging','Charging')}),[])
 def test_busy_fraction_excludes_duplicate_guest_counters(self):
  a={'/proc/stat':'cpu 0 0 0 0 0 0 0 0 0 0'};b={'/proc/stat':'cpu 20 0 0 80 0 0 0 0 20 0'}
  self.assertEqual(m.busy_fraction(a,b),0.2)
 def test_missing_telemetry_does_not_become_zero_power(self):
  samples=[{'monotonic':t,'raw':{}} for t in (1,11)]
  self.assertEqual(m.summarise({'enabled':True,'samples':samples})['discharging_battery_estimates'],{})
