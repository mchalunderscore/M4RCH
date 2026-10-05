from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import call, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from common import manifest_files, verify_manifest, write_json
from image import install_packages, newc, root_workspace


class ImageTests(unittest.TestCase):
    def test_manifest_rejects_changed_image_and_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "image").write_bytes(b"original")
            path = root / "manifest.json"
            write_json(path, {"files": manifest_files(root, ["image"])})
            verify_manifest(path)
            (root / "image").write_bytes(b"tampered")
            with self.assertRaises(ValueError):
                verify_manifest(path)
            write_json(path, {"files": {"../outside": {"bytes": 0, "sha256": ""}}})
            with self.assertRaises(ValueError):
                verify_manifest(path)

    def test_cpio_preserves_symlinks_without_reading_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "bin").mkdir()
            (root / "bin/init").write_bytes(b"#!/bin/sh\n")
            (root / "bin/init").chmod(0o755)
            (root / "external").symlink_to("/does/not/exist")
            data = newc(root, 123456)
            self.assertEqual(data, newc(root, 123456))
            offset, entries = 0, {}
            while True:
                self.assertEqual(data[offset:offset + 6], b"070701")
                fields = [int(data[offset + 6 + 8*i:offset + 14 + 8*i], 16) for i in range(13)]
                offset += 110
                name = data[offset:offset + fields[11] - 1].decode()
                offset = (offset + fields[11] + 3) & ~3
                payload = data[offset:offset + fields[6]]
                offset = (offset + fields[6] + 3) & ~3
                if name == "TRAILER!!!":
                    break
                self.assertEqual(fields[2:4], [0, 0])
                self.assertEqual(fields[5], 123456)
                entries[name] = (fields[1], payload)
            self.assertTrue(stat.S_ISLNK(entries["./external"][0]))
            self.assertEqual(entries["./external"][1], b"/does/not/exist")
            self.assertEqual(entries["./bin/init"][0] & 0o777, 0o755)


class ImageCleanupTests(unittest.TestCase):
    def test_package_failure_still_unmounts_proc_and_root(self):
        failure = RuntimeError("package transaction failed")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch("image.run"), \
                    patch("image._install_packages", side_effect=failure), \
                    patch("image.stop_chroot_processes") as stop, \
                    patch("image.unmount_chroot") as unmount:
                with self.assertRaises(RuntimeError) as caught:
                    install_packages(root, {})
                self.assertIs(caught.exception, failure)
                stop.assert_called_once_with(root)
                self.assertEqual(unmount.call_args_list, [call(root / "proc"), call(root)])

    def test_gpg_shutdown_failure_still_unmounts_proc_and_root(self):
        failure = RuntimeError("gpgconf shutdown failed")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch("image.run", side_effect=[None, None, failure]), \
                    patch("image._install_packages"), \
                    patch("image.stop_chroot_processes"), \
                    patch("image.unmount_chroot") as unmount:
                with self.assertRaises(RuntimeError) as caught:
                    install_packages(root, {})
                self.assertIs(caught.exception, failure)
                self.assertEqual(unmount.call_args_list, [call(root / "proc"), call(root)])

    def test_proc_unmount_failure_still_attempts_root_unmount(self):
        failure = RuntimeError("proc mount remained busy")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch("image.run"), \
                    patch("image._install_packages"), \
                    patch("image.stop_chroot_processes"), \
                    patch("image.unmount_chroot", side_effect=[failure, None]) as unmount:
                with self.assertRaises(RuntimeError) as caught:
                    install_packages(root, {})
                self.assertIs(caught.exception, failure)
                self.assertEqual(unmount.call_args_list, [call(root / "proc"), call(root)])

    def test_mounted_workspace_is_retained_on_failure(self):
        for relative_mount in ("", "/root", "/root/proc"):
            with self.subTest(mount=relative_mount), tempfile.TemporaryDirectory() as tmp:
                workspace = Path(tmp) / "image-fixture"
                workspace.mkdir()
                marker = workspace / "retain-me"
                marker.write_bytes(b"mounted filesystem contents")
                mountinfo = f"40 31 0:7 / {workspace}{relative_mount} rw - tmpfs tmpfs rw\n"
                failure = RuntimeError("build failed")
                with patch("image.tempfile.mkdtemp", return_value=str(workspace)), \
                        patch("image.Path.read_text", return_value=mountinfo):
                    with self.assertRaises(RuntimeError) as caught:
                        with root_workspace() as result:
                            self.assertEqual(result, workspace)
                            raise failure
                    self.assertIs(caught.exception, failure)
                self.assertEqual(marker.read_bytes(), b"mounted filesystem contents")

    def test_unknown_mount_state_retains_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "image-fixture"
            workspace.mkdir()
            with patch("image.tempfile.mkdtemp", return_value=str(workspace)), \
                    patch("image.Path.read_text", side_effect=OSError("mountinfo unavailable")):
                with root_workspace():
                    pass
            self.assertTrue(workspace.is_dir())

    def test_unmounted_workspace_is_removed_even_with_similar_mount_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "image-fixture"
            workspace.mkdir()
            mountinfo = f"40 31 0:7 / {workspace}-other/root rw - tmpfs tmpfs rw\n"
            with patch("image.tempfile.mkdtemp", return_value=str(workspace)), \
                    patch("image.Path.read_text", return_value=mountinfo):
                with root_workspace():
                    pass
            self.assertFalse(workspace.exists())


if __name__ == "__main__":
    unittest.main()
