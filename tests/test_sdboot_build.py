"""Cross-artifact and cache invalidation checks without a build or disk I/O."""
import copy
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, call, patch

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from sdboot import build


class BuildVolumeLockTests(unittest.TestCase):
    def test_concurrent_build_is_rejected_before_starting_another_vm(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(build, "PROJECT", Path(temporary)):
            def running(action, config):
                with self.assertRaisesRegex(ValueError, "Another SD-image build"):
                    build.builder("packages", {})
                return "finished"
            with patch.object(build, "_builder", side_effect=running) as invoked:
                self.assertEqual(build.builder("loader", {}), "finished")
                self.assertEqual(invoked.call_count, 1)
            # Completion releases the volume for the next independent VM.
            with patch.object(build, "_builder", return_value="next"):
                self.assertEqual(build.builder("packages", {}), "next")

    def test_failed_build_releases_volume_lock_for_a_retry(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(build, "PROJECT", Path(temporary)):
            with patch.object(build, "_builder", side_effect=ValueError("compile failed")), self.assertRaisesRegex(ValueError, "compile failed"):
                build.builder("loader", {})
            with patch.object(build, "_builder", return_value="retried"):
                self.assertEqual(build.builder("loader", {}), "retried")


class BuildConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.out = Path(self.temporary.name)
        self.config = {"root_uuid": "a0418040-b5b3-4ae8-9288-1c7c6dbda604", "username": "alice"}
        self.root = self.artifact("rootfs", "rootfs.ext4", b"packaged root", kernel_release="test-kernel")
        self.init = self.artifact("initramfs", "initramfs.cpio.gz", b"early userspace", kernel_release="test-kernel")
        self.loader = self.artifact("loader", "loader.bin", b"UEFI firmware", boot_protocol="uefi-arm64")
        self.boot = self.artifact("payload", "esp/initramfs-linux-m4rch.img", b"early userspace",
                                 kernel_release="test-kernel", required_loader_sha256=self.loader["files"]["loader.bin"]["sha256"])

    def artifact(self, manifest_name, filename, data, **extra):
        file = self.out / filename
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(data)
        manifest = {"config": copy.deepcopy(self.config), "files": {
            filename: {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}}, **extra}
        self.save(manifest_name, manifest)
        return manifest

    def save(self, name, manifest):
        (self.out / (name + "-manifest.json")).write_text(json.dumps(manifest))

    def test_matching_packaged_root_and_esp_can_compose(self):
        with patch.object(build.media, "_esp") as verify_esp:
            build.validate_compose(self.out, self.config)
        verify_esp.assert_called_once_with(self.out, self.config)

    def test_old_root_cannot_compose_with_a_different_packaged_kernel(self):
        self.root["kernel_release"] = "older-kernel"
        self.save("rootfs", self.root)
        with self.assertRaisesRegex(ValueError, "kernel releases differ"):
            build.validate_compose(self.out, self.config)

    def test_configuration_mismatch_stops_before_esp_validation(self):
        for name in ("rootfs", "initramfs", "payload"):
            original = json.loads((self.out / (name + "-manifest.json")).read_text())
            wrong = copy.deepcopy(original)
            wrong["config"]["username"] = "other"
            self.save(name, wrong)
            with self.subTest(manifest=name), patch.object(build.media, "_esp") as verified, \
                    self.assertRaisesRegex(ValueError, "configuration is stale"):
                build.validate_compose(self.out, self.config)
            verified.assert_not_called()
            self.save(name, original)

    def test_rebuilt_initramfs_without_esp_export_is_rejected(self):
        self.artifact("initramfs", "initramfs.cpio.gz", b"different early userspace", kernel_release="test-kernel")
        with self.assertRaisesRegex(ValueError, "ESP and generated initramfs differ"):
            build.validate_compose(self.out, self.config)

    def test_loader_manifest_must_match_payload_requirement(self):
        self.boot["required_loader_sha256"] = "a" * 64
        self.save("payload", self.boot)
        with self.assertRaisesRegex(ValueError, "different fixed loader"):
            build.validate_compose(self.out, self.config)

    def test_old_fit_loader_cannot_bind_a_new_uefi_card(self):
        self.loader.pop("boot_protocol")
        self.loader["kind"] = "j614s-sd-loader"
        self.save("loader", self.loader)
        for operation in (lambda: build.validate_compose(self.out, self.config),
                          lambda: build.payload(self.out, self.config, {}, self.out)):
            with self.assertRaisesRegex(ValueError, "make loader"):
                operation()

    def test_corrupted_artifact_is_rejected(self):
        for filename in ("rootfs.ext4", "initramfs.cpio.gz", "esp/initramfs-linux-m4rch.img", "loader.bin"):
            path = self.out / filename
            original = path.read_bytes()
            path.write_bytes(b"corrupted")
            with self.subTest(filename=filename), self.assertRaisesRegex(ValueError, "Artifact failed verification"):
                build.validate_compose(self.out, self.config)
            path.write_bytes(original)

    def test_payload_refuses_a_different_baseline_dt(self):
        directory = self.out / "hardware"
        (directory / "boot").mkdir(parents=True)
        (directory / "boot/t6040-j614s.dtb").write_bytes(b"changed baseline DT")
        self.loader.update(kind="j614s-sd-loader", inputs={"baseline_dtb": "a" * 64})
        self.save("loader", self.loader)
        with self.assertRaisesRegex(ValueError, "make loader and re-enrollment"):
            build.payload(self.out, self.config, {}, directory)


class LoaderCacheTests(unittest.TestCase):
    def test_inputs_change_for_every_consumed_recipe_and_pinned_input(self):
        sys.path.insert(0, str(PROJECT / "sdboot"))
        try:
            from loader import inputs
        finally:
            sys.path.pop(0)
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "sdboot").mkdir()
            (project / "lib").mkdir()
            (project / "kernel/boot").mkdir(parents=True)
            paths = ["sdboot/" + name for name in (
                "loader.py", "prepare_m1n1.py", "prepare_uboot.py", "sd_pcie.h", "sd_pci_handoff.h", "gl9755.h", "gl9755_pci.h", "gl9755_card.h", "archsd.c", "uboot.config", "uboot-noio.patch", "Containerfile")]
            paths += ["lib/boot.py", "kernel/boot/t6040-j614s.dtb"]
            for name in paths:
                (project / name).write_bytes(b"original input")
            lock = {key: {"revision": "original"} for key in ("m1n1", "wallace", "m1n1_pcie", "m1n1_smp")}
            lock["source_date_epoch"] = 1
            expected = inputs(project, lock, project / "kernel")
            self.assertEqual(inputs(project, lock, project / "kernel"), expected)
            for name in paths:
                path = project / name
                path.write_bytes(b"changed input")
                with self.subTest(path=name):
                    self.assertNotEqual(inputs(project, lock, project / "kernel"), expected)
                path.write_bytes(b"original input")
            for key in lock:
                changed = copy.deepcopy(lock)
                changed[key] = 2 if key == "source_date_epoch" else {"revision": "changed"}
                with self.subTest(source=key):
                    self.assertNotEqual(inputs(project, changed, project / "kernel"), expected)


class UpdateDispatchTests(unittest.TestCase):
    def test_boot_prepares_nvme_by_default_and_safe_requires_explicit_selection(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "sources.lock.json").write_text("{}")
            prepare = Mock()
            for action in ("boot", "boot-safe"):
                for flag in ([], ["--replace-pending"]):
                    with patch.object(build, "PROJECT", project), \
                            patch.object(build, "configuration", return_value={}), \
                            patch.object(build, "builder") as builder, \
                            patch.object(build, "identify_mac") as identify, \
                            patch.dict(sys.modules, {"enrollment": SimpleNamespace(prepare=prepare)}), \
                            patch.object(sys, "argv", ["build.py", action, *flag]):
                        build.main()
                    prepare.assert_called_once_with(project, project / "out/sdboot", replace_pending=bool(flag), nvme=action != "boot-safe")
                    builder.assert_not_called()
                    identify.assert_not_called()
                    prepare.reset_mock()

    def test_preparation_failure_does_not_fall_back_or_build_under_sudo(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "sources.lock.json").write_text("{}")
            prepare = Mock(side_effect=ValueError("Build the NVMe loader first"))
            with patch.object(build, "PROJECT", project), \
                    patch.object(build, "configuration", return_value={}), \
                    patch.object(build, "builder") as builder, \
                    patch.dict(sys.modules, {"enrollment": SimpleNamespace(prepare=prepare)}), \
                    patch.object(sys, "argv", ["build.py", "boot"]), \
                    self.assertRaisesRegex(ValueError, "Build the NVMe loader first"):
                build.main()
            prepare.assert_called_once_with(project, project / "out/sdboot", replace_pending=False, nvme=True)
            builder.assert_not_called()

    def test_image_and_loader_build_both_loader_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "sources.lock.json").write_text('{"source_date_epoch": 1}')
            loader = Mock()
            for action in ("image", "loader"):
                with self.subTest(action=action), patch.object(build, "PROJECT", project), \
                        patch.object(build, "configuration", return_value={}), \
                        patch.object(build.platform, "system", return_value="Linux"), \
                        patch.object(build.platform, "machine", return_value="aarch64"), \
                        patch.object(build, "kernel_directory", return_value=project / "kernel"), \
                        patch.object(build, "payload"), patch.object(build, "validate_compose"), \
                        patch.object(build.media, "compose"), \
                        patch.dict(sys.modules, {"loader": SimpleNamespace(build=loader),
                                                 "rootfs": SimpleNamespace(build=Mock()),
                                                 "grub": SimpleNamespace(build=Mock())}), \
                        patch.dict(os.environ, {}), \
                        patch.object(sys, "argv", ["build.py", action, "--inside"]):
                    build.main()
                self.assertEqual(loader.call_args_list, [
                    call(project, Path("/out/nvme-loader") if nvme else Path("/out"), {},
                         {"source_date_epoch": 1}, project / "kernel", nvme=nvme)
                    for nvme in (False, True)])
                loader.reset_mock()

    def test_posix_boot_wrapper_forwards_variant_and_pending_override(self):
        with tempfile.TemporaryDirectory() as temporary:
            python = Path(temporary) / "record-python"
            python.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
            python.chmod(0o755)
            for flag, action in ((None, "boot"), ("--safe", "boot-safe")):
                for replace in ("0", "1"):
                    result = subprocess.run(["sh", str(PROJECT / "scripts/setup-boot.sh"), *([flag] if flag else [])],
                                            text=True, capture_output=True,
                                            env=dict(os.environ, PYTHON=str(python), REPLACE_PENDING=replace), check=True)
                    self.assertEqual(result.stdout.splitlines(), [str(PROJECT / "sdboot/build.py"), action,
                                                                  *(["--replace-pending"] if replace == "1" else [])])

    def test_pending_override_rejects_other_actions_before_inspection(self):
        for args in (["flash"], ["boot-status"], ["boot", "--inside"],
                     ["boot-safe", "--inside"]):
            with self.subTest(args=args), \
                    patch.object(build, "configuration") as config, \
                    patch.object(sys, "argv", ["build.py", *args, "--replace-pending"]), \
                    contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as stopped:
                build.main()
            self.assertEqual(stopped.exception.code, 2)
            config.assert_not_called()

    def test_retired_actions_are_rejected_before_configuration_or_disk_access(self):
        for action in ("rootfs", "payload", "compose", "loader-nvme", "boot-nvme",
                       "grub", "grub-smoke", "repair-grub", "update"):
            with self.subTest(action=action), \
                    patch.object(build, "configuration") as config, \
                    patch.object(sys, "argv", ["build.py", action]), \
                    contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as stopped:
                build.main()
            self.assertEqual(stopped.exception.code, 2)
            config.assert_not_called()

    def test_mac_image_prefetches_stub_before_starting_builder(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "sources.lock.json").write_text("{}")
            operations = Mock()
            firmware, stub, builder = Mock(), Mock(), Mock()
            operations.attach_mock(firmware, "firmware")
            operations.attach_mock(stub, "stub")
            operations.attach_mock(builder, "builder")
            with patch.object(build, "PROJECT", project), \
                    patch.object(build, "configuration", return_value={}), \
                    patch.object(build, "identify_mac"), \
                    patch.object(build.platform, "system", return_value="Darwin"), \
                    patch.object(build, "builder", builder), \
                    patch.dict(sys.modules, {"firmware": SimpleNamespace(prepare=firmware),
                                             "stub_payload": SimpleNamespace(prepare=stub)}), \
                    patch.object(sys, "argv", ["build.py", "image"]):
                build.main()
            self.assertEqual(operations.mock_calls, [
                call.firmware(project / "cache", project / "cache/firmware", None),
                call.stub(project / "cache", project / "out/stub"),
                call.builder("kernel", {}), call.builder("image", {})])

    def test_linux_image_does_not_prepare_mac_stub(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "sources.lock.json").write_text("{}")
            stub, builder = Mock(), Mock()
            with patch.object(build, "PROJECT", project), \
                    patch.object(build, "configuration", return_value={}), \
                    patch.object(build, "identify_mac"), \
                    patch.object(build.platform, "system", return_value="Linux"), \
                    patch.object(build, "builder", builder), \
                    patch.dict(sys.modules, {"firmware": SimpleNamespace(prepare=Mock()),
                                             "stub_payload": SimpleNamespace(prepare=stub)}), \
                    patch.object(sys, "argv", ["build.py", "image", "--model", "Mac16,8"]):
                build.main()
            stub.assert_not_called()
            self.assertEqual(builder.call_args_list, [call("kernel", {}), call("image", {})])

    def test_flash_can_prepare_a_card_before_internal_enrollment(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "sources.lock.json").write_text("{}")
            gate, flash = Mock(), Mock()
            with patch.object(build, "PROJECT", project), \
                    patch.object(build, "configuration", return_value={}), \
                    patch.object(build, "verify_manifest") as manifest, \
                    patch.object(build.media, "flash", flash), \
                    patch.object(sys, "argv", ["build.py", "flash", "--disk", "/dev/disk99"]):
                build.main()
            gate.assert_not_called()
            manifest.assert_not_called()
            flash.assert_called_once_with(project / "out/sdboot", {}, "/dev/disk99")


if __name__ == "__main__":
    unittest.main()
