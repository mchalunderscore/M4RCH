import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
from smoke import signed_package_fixture

spec = importlib.util.spec_from_file_location("pacman_probe", ROOT / "tests/fixtures/pacman-download.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)



class SmokeTests(unittest.TestCase):


    def test_signed_offline_fixture_rejects_changed_package_or_signature(self):
        for changed in (None, "default-cursors-3-1-any.pkg.tar.xz", "default-cursors-3-1-any.pkg.tar.xz.sig"):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as temporary:
                work = Path(temporary)
                names = ["default-cursors-3-1-any.pkg.tar.xz", "default-cursors-3-1-any.pkg.tar.xz.sig"]
                entries = []
                for name in names:
                    content = name.encode()
                    (work / name).write_bytes(content)
                    entries.append({"filename": name, "sha256": hashlib.sha256(content).hexdigest()})
                lock = work / "lock.json"
                lock.write_text(json.dumps({"files": entries}))
                if changed:
                    (work / changed).write_bytes(b"changed")
                    with self.assertRaisesRegex(ValueError, "failed verification"):
                        signed_package_fixture(lock, work)
                else:
                    self.assertEqual(signed_package_fixture(lock, work), [work / name for name in names])

    def test_signed_offline_fixture_requires_unique_signature(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            lock = work / "lock.json"
            package = {"filename": "default-cursors-3-1-any.pkg.tar.xz", "sha256": "unused"}
            signature = dict(package, filename=package["filename"] + ".sig")
            for entries in ([package], [package, signature, signature]):
                lock.write_text(json.dumps({"files": entries}))
                with self.assertRaisesRegex(ValueError, "signature is missing or ambiguous"):
                    signed_package_fixture(lock, work)

    def test_guest_requires_real_sandbox_and_trusted_signatures(self):
        config = "[options]\nDownloadUser = alpm\n#DisableSandboxFilesystem\n"
        required = "PackageRequired\nPackageTrustedOnly\n"
        probe.validate_configuration(config, required, "alpm\n")
        for directive in ("DisableSandbox", "DisableSandboxFilesystem", "DisableSandboxSyscalls"):
            with self.subTest(directive=directive), self.assertRaisesRegex(ValueError, "default sandbox"):
                probe.validate_configuration(config + directive + "\n", required, "alpm\n")
        for level in ("PackageOptional\nPackageTrustedOnly", "PackageRequired\nPackageTrustAll", "PackageNever"):
            with self.subTest(level=level), self.assertRaisesRegex(ValueError, "trusted signatures"):
                probe.validate_configuration(config, level, "alpm\n")
        with self.assertRaisesRegex(ValueError, "unprivileged"):
            probe.validate_configuration(config, required, "root\n")

    def test_sync_fixture_keeps_paths_and_security_but_never_remote_repositories(self):
        options = ("[options]\nRootDir = /\nDBPath = /var/lib/pacman/\n"
                   "DownloadUser = alpm\nSigLevel = PackageRequired DatabaseOptional\n"
                   "LocalFileSigLevel = PackageOptional\nArchitecture = aarch64\n")
        resolved = options + "[core]\nServer = https://example.invalid/core\n[extra]\n"
        actual = probe.sync_configuration(resolved, 12345)
        self.assertEqual(actual, options + "[arch-m4-smoke]\nServer = http://127.0.0.1:12345\n")
        self.assertNotIn("DisableSandbox", actual)
        with self.assertRaisesRegex(ValueError, "no options"):
            probe.sync_configuration("[core]\nServer = https://example.invalid/core\n", 12345)


if __name__ == "__main__":
    unittest.main()
