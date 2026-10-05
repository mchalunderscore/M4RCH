"""Check the standalone kit users copy to the FAT ESP, without native writes."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from sdboot.cpu_tools import publish


class CpuToolsTests(unittest.TestCase):
    def test_publish_is_repeatable_and_checksums_cover_the_kit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "project/sdboot"
            source.mkdir(parents=True)
            (source / "cpu_benchmark.py").write_text("print('benchmark fixture')\n")
            (source / "peripheral_policy.py").write_text("print('report fixture')\n")
            (source / "native_lab.py").write_text("print('lab fixture')\n")
            (source.parent / "HANDOVER.md").write_text("work handover fixture\nkit=/boot/cpu-tools-ID\n")
            (source.parent / "docs").mkdir()
            (source.parent / "docs/native-agent-instructions.md").write_text("native handoff fixture\n")
            (source.parent / "docs/native-agent-followup.md").write_text("native follow-up fixture\n")
            destination = publish(source.parent, root / "out")
            self.assertEqual(publish(source.parent, root / "out"), destination)
            self.assertEqual((destination / "instructions.md").read_text(), "native handoff fixture\n")
            self.assertEqual((destination / "native-agent-followup.md").read_text(), "native follow-up fixture\n")
            self.assertEqual((destination / "HANDOVER.md").read_text(), "work handover fixture\nkit=/boot/" + destination.name + "\n")
            for line in (destination / "SHA256SUMS").read_text().splitlines():
                digest, name = line.split("  ", 1)
                self.assertEqual(hashlib.sha256((destination / name).read_bytes()).hexdigest(), digest)
            subprocess.run(["sh", "-n", str(destination / "run.sh")], check=True)
            subprocess.run(["sh", "-n", str(destination / "collect.sh")], check=True)
            (source.parent / "HANDOVER.md").write_bytes((destination / "HANDOVER.md").read_bytes())
            self.assertEqual(publish(source.parent, root / "out"), destination)
            original = destination
            port_map = root / "out/macos-port-map.json"
            port_map.write_text(json.dumps({"schema": 1, "model": "Mac16,8", "nodes": []}))
            mapped = publish(source.parent, root / "out")
            self.assertNotEqual(mapped, original)
            self.assertEqual((mapped / port_map.name).read_bytes(), port_map.read_bytes())
            self.assertIn("  macos-port-map.json\n", (mapped / "SHA256SUMS").read_text())
            port_map.write_text(json.dumps({"schema": 1, "model": "Mac16,9"}))
            with self.assertRaisesRegex(ValueError, "different target"):
                publish(source.parent, root / "out")
            port_map.unlink()
            port_map.symlink_to(source / "cpu_benchmark.py")
            with self.assertRaisesRegex(ValueError, "regular file"):
                publish(source.parent, root / "out")
            port_map.unlink()
            (source / "cpu_benchmark.py").write_text("print('new fixture')\n")
            self.assertNotEqual(publish(source.parent, root / "out"), original)
            self.assertEqual((original / "m4rch-cpu-benchmark").read_text(), "print('benchmark fixture')\n")

    def test_tampered_or_symlinked_kit_is_not_silently_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "project/sdboot"
            source.mkdir(parents=True)
            for name in ("cpu_benchmark.py", "peripheral_policy.py", "native_lab.py"):
                (source / name).write_text("original\n")
            (source.parent / "HANDOVER.md").write_text("work handover fixture\n")
            (source.parent / "docs").mkdir()
            (source.parent / "docs/native-agent-instructions.md").write_text("native handoff fixture\n")
            (source.parent / "docs/native-agent-followup.md").write_text("native follow-up fixture\n")
            kit = publish(source.parent, root / "out")
            (kit / "m4rch-cpu-benchmark").write_text("tampered\n")
            with self.assertRaisesRegex(ValueError, "changed"):
                publish(source.parent, root / "out")
            (kit / "m4rch-cpu-benchmark").unlink()
            (kit / "m4rch-cpu-benchmark").symlink_to(source / "cpu_benchmark.py")
            with self.assertRaisesRegex(ValueError, "changed"):
                publish(source.parent, root / "out")
            self.assertEqual((source / "cpu_benchmark.py").read_text(), "original\n")


if __name__ == "__main__":
    unittest.main()
