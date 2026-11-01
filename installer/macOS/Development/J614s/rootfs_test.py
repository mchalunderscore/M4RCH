import stat
import unittest

import rootfs_audit


def newc(name, content=b"", mode=stat.S_IFREG | 0o644):
    name = name.encode() + b"\0"
    fields = [0, mode, 0, 0, 1, 0, len(content), 0, 0, 0, 0, len(name), 0]
    data = b"070701" + b"".join(f"{field:08x}".encode() for field in fields) + name
    data += b"\0" * (-len(data) % 4)
    data += content
    data += b"\0" * (-len(data) % 4)
    return data


class RootfsAuditTests(unittest.TestCase):
    def test_dependency_closure_follows_recursive_dependencies(self):
        deps = "kernel/a.ko: kernel/b.ko\nkernel/b.ko: kernel/c.ko\nkernel/c.ko:\n"
        self.assertEqual(
            rootfs_audit.module_closure(deps, ("kernel/a.ko",)),
            ["kernel/a.ko", "kernel/b.ko", "kernel/c.ko"],
        )
        with self.assertRaises(ValueError):
            rootfs_audit.module_closure(deps, ("kernel/missing.ko",))

    def test_cpio_bounds_and_duplicates(self):
        valid = newc("init", b"hello") + newc("TRAILER!!!")
        entries, _ = rootfs_audit.cpio_entries(valid)
        self.assertEqual(entries["init"][1], b"hello")
        with self.assertRaises(ValueError):
            rootfs_audit.cpio_entries(valid[:-120])
        with self.assertRaises(ValueError):
            rootfs_audit.cpio_entries(newc("init") + newc("init") + newc("TRAILER!!!"))


if __name__ == "__main__":
    unittest.main()
