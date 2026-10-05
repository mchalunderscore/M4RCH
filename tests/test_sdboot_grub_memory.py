"""Run GRUB's real EFI allocation/filtering code against high-only firmware RAM.

The release archive is optional for ordinary offline tests. Set
GRUB_SOURCE_ARCHIVE to a verified grub-2.16.tar.xz, or cache it at
cache/grub/grub-2.16.tar.xz. Both builds use the same upstream functions; the second
applies the package's actual ARM64 memory-limit patch to the upstream header.
"""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest


PROJECT = Path(__file__).resolve().parents[1]
ARCHIVE_NAME = "grub-2.16.tar.xz"
ARCHIVE_SHA256 = "f0db0104927df0b9a48bc41b735c702936190d17eb2d73d3018fa77474a0cabe"
PAGE_SIZE = 4096
MAP_PAGES = 6  # Two MEMORY_MAP_SIZE (0x3000) buffers in mm_add_regions.
HIGH_BASE = 0x1000000000
HIGH_SIZE = 0x600000000
OLD_LIMIT = 0xFFFFFFFF
NEW_LIMIT = 0xFFFFFFFFFFFF


def extract_function(source, signature):
    start = source.index(signature)
    end = source.index("{", start) + 1
    depth = 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


PREAMBLE = r'''
#include <assert.h>
#include <inttypes.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "include/grub/arm64/efi/memory.h"

typedef uint64_t grub_efi_physical_address_t;
typedef uint64_t grub_efi_uint64_t;
typedef uint64_t grub_efi_uintn_t;
typedef uint64_t grub_efi_status_t;
typedef uintptr_t grub_addr_t;
typedef int grub_efi_allocate_type_t;
typedef int grub_efi_memory_type_t;
enum { GRUB_EFI_ALLOCATE_ANY_PAGES, GRUB_EFI_ALLOCATE_MAX_ADDRESS,
       GRUB_EFI_ALLOCATE_ADDRESS };
enum { GRUB_EFI_SUCCESS = 0, GRUB_EFI_LOADER_DATA = 2,
       GRUB_EFI_CONVENTIONAL_MEMORY = 7 };
enum { GRUB_ERR_NONE, GRUB_ERR_OUT_OF_MEMORY, GRUB_ERR_BAD_ARGUMENT };
#define GRUB_EFI_OUT_OF_RESOURCES (UINT64_C(0x8000000000000000) | 9)
#define N_(message) (message)
#define PRIxGRUB_UINT64_T PRIx64
#define grub_snprintf snprintf
#define grub_printf printf
#define grub_memcpy memcpy
#define NEXT_MEMORY_DESCRIPTOR(desc, size) \
    ((grub_efi_memory_descriptor_t *)((char *)(desc) + (size)))
#define BYTES_TO_PAGES(bytes) (((bytes) + 0xfff) >> 12)
#define BYTES_TO_PAGES_DOWN(bytes) ((bytes) >> 12)
#define PAGES_TO_BYTES(pages) ((pages) << 12)

typedef struct {
    uint32_t type, pad;
    uint64_t physical_start, virtual_start, num_pages, attribute;
} grub_efi_memory_descriptor_t;
typedef struct {
    grub_efi_status_t (*allocate_pages)(grub_efi_allocate_type_t,
        grub_efi_memory_type_t, grub_efi_uintn_t,
        grub_efi_physical_address_t *);
    grub_efi_status_t (*allocate_pool)(grub_efi_memory_type_t,
        grub_efi_uintn_t, void **);
    grub_efi_status_t (*free_pages)(grub_efi_physical_address_t,
        grub_efi_uintn_t);
} grub_efi_boot_services_t;
struct mock_system_table { grub_efi_boot_services_t *boot_services; };
static struct mock_system_table *grub_efi_system_table;
static int grub_errno;
static int grub_error(int error, const char *format, ...)
{
    (void)format;
    grub_errno = error;
    return error;
}

/* Same accounting object used by the extracted grub_efi_store_alloc(). */
struct efi_allocation {
    grub_efi_physical_address_t address;
    grub_efi_uint64_t pages;
    struct efi_allocation *next;
};
static struct efi_allocation *efi_allocated_memory;

/* The firmware advertises one contiguous conventional-memory range. It has
 * no allocatable addresses below that range, just as on this Apple machine.
 * Return numeric physical addresses; the allocator must not dereference them.
 */
static uint64_t ram_base, ram_size, allocated_address, allocated_pages;
static unsigned calls, stored, free_calls;
static uint64_t bounds[4];
static grub_efi_status_t firmware_allocate(grub_efi_allocate_type_t type,
    grub_efi_memory_type_t memory_type, grub_efi_uintn_t pages,
    grub_efi_physical_address_t *address)
{
    uint64_t end = ram_base + ram_size, bytes, candidate;
    assert(memory_type == GRUB_EFI_LOADER_DATA);
    assert(calls < sizeof(bounds) / sizeof(bounds[0]));
    bounds[calls++] = *address;
    assert(pages && pages <= UINT64_MAX / 4096);
    bytes = pages * 4096;
    if (type == GRUB_EFI_ALLOCATE_MAX_ADDRESS) {
        /* UEFI's maximum address is inclusive. Avoid wrap at UINT64_MAX. */
        if (*address < end - 1)
            end = *address + 1;
        if (end <= ram_base || bytes > end - ram_base)
            return GRUB_EFI_OUT_OF_RESOURCES;
        candidate = (end - bytes) & ~UINT64_C(4095);
    } else {
        assert(type == GRUB_EFI_ALLOCATE_ADDRESS);
        candidate = *address;
    }
    if (allocated_pages || bytes > ram_size || candidate < ram_base ||
        candidate > ram_base + ram_size - bytes)
        return GRUB_EFI_OUT_OF_RESOURCES;
    allocated_address = *address = candidate;
    allocated_pages = pages;
    return GRUB_EFI_SUCCESS;
}
static grub_efi_status_t firmware_pool(grub_efi_memory_type_t type,
    grub_efi_uintn_t bytes, void **result)
{
    static struct efi_allocation record;
    assert(type == GRUB_EFI_LOADER_DATA && bytes == sizeof(record));
    assert(!stored++);
    *result = &record;
    return GRUB_EFI_SUCCESS;
}
static grub_efi_status_t firmware_free(grub_efi_physical_address_t address,
    grub_efi_uintn_t pages)
{
    assert(address == allocated_address && pages == allocated_pages);
    ++free_calls;
    allocated_pages = 0;
    return GRUB_EFI_SUCCESS;
}
'''


MAIN = r'''
int main(int argc, char **argv)
{
    grub_efi_boot_services_t services = {
        firmware_allocate, firmware_pool, firmware_free
    };
    struct mock_system_table table = { &services };
    void *result;
    assert(argc == 2);
    grub_efi_system_table = &table;
    ram_base = UINT64_C(0x1000000000);
    ram_size = UINT64_C(0x600000000);

    if (!strcmp(argv[1], "filter")) {
        grub_efi_memory_descriptor_t input[] = {
            { .type = 0, .physical_start = UINT64_C(0x100000),
              .num_pages = 0x100 },
            { .type = GRUB_EFI_CONVENTIONAL_MEMORY,
              .physical_start = UINT64_C(0x40000000), .num_pages = 0x4000 },
            { .type = GRUB_EFI_CONVENTIONAL_MEMORY,
              .physical_start = UINT64_C(0x1000000000), .num_pages = 0x600000 },
            { .type = GRUB_EFI_CONVENTIONAL_MEMORY,
              .physical_start = UINT64_C(0x1000000000000), .num_pages = 0x100 },
            { .type = GRUB_EFI_CONVENTIONAL_MEMORY,
              .physical_start = UINT64_C(0x1000000000), .num_pages = 0 }
        }, output[5] = {0};
        grub_efi_memory_descriptor_t *end = filter_memory_map(input, output,
            sizeof(input[0]), input + sizeof(input) / sizeof(input[0]));
        printf("count=%zu low=%" PRIu64 " high=%" PRIu64 " pages=%" PRIu64 "\n",
            (size_t)(end - output), output[0].physical_start,
            output[1].physical_start, output[1].num_pages);
        return 0;
    }
    if (!strcmp(argv[1], "low")) {
        ram_base = UINT64_C(0x40000000);
        ram_size = UINT64_C(0x40000000);
    } else if (!strcmp(argv[1], "exhaust")) {
        ram_size = 4096; /* Real insufficient space, despite a high bound. */
    } else {
        assert(!strcmp(argv[1], "high") || !strcmp(argv[1], "fixed"));
    }

    if (!strcmp(argv[1], "fixed"))
        result = grub_efi_allocate_pages_real(ram_base, 6,
            GRUB_EFI_ALLOCATE_ADDRESS, GRUB_EFI_LOADER_DATA);
    else
        result = grub_efi_allocate_any_pages(6);

    if (result) {
        assert(efi_allocated_memory && efi_allocated_memory->pages == 6);
        assert(efi_allocated_memory->address == (uintptr_t)result);
        assert(!efi_allocated_memory->next);
    } else {
        assert(!efi_allocated_memory);
    }
    printf("address=%" PRIuPTR " error=%d calls=%u bound0=%" PRIu64
           " bound1=%" PRIu64 " stored=%u freed=%u pages=%" PRIu64 "\n",
           (uintptr_t)result, grub_errno, calls, bounds[0], bounds[1],
           stored, free_calls, allocated_pages);
    return 0;
}
'''


class GrubHighMemoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cc = shutil.which("cc")
        if not cc:
            raise unittest.SkipTest("C compiler unavailable")
        archive = Path(os.environ.get("GRUB_SOURCE_ARCHIVE",
                                      PROJECT / "cache/grub" / ARCHIVE_NAME))
        if not archive.is_file():
            raise unittest.SkipTest(f"Pinned GRUB source archive unavailable: {archive}")
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        if digest != ARCHIVE_SHA256:
            raise AssertionError(f"Pinned GRUB source SHA256 mismatch: {digest}")
        patch = PROJECT / "packages/grub-m4rch/0005-arm64-restore-high-memory.patch"
        cls.temporary = tempfile.TemporaryDirectory(prefix="arch-m4-grub-memory-")
        cls.addClassCleanup(cls.temporary.cleanup)
        work = Path(cls.temporary.name)
        with tarfile.open(archive) as source_tar:
            source = source_tar.extractfile("grub-2.16/grub-core/kern/efi/mm.c").read().decode()
            header = source_tar.extractfile("grub-2.16/include/grub/arm64/efi/memory.h").read()
        # Exercise the unmodified allocator entry points and descriptor filter.
        signatures = ("static void\ngrub_efi_store_alloc (",
                      "void *\ngrub_efi_allocate_pages_real (",
                      "void *\ngrub_efi_allocate_any_pages (",
                      "static grub_efi_memory_descriptor_t *\nfilter_memory_map (")
        actual_functions = "\n\n".join(extract_function(source, name) for name in signatures)
        cls.executables = {}
        for variant in ("stock", "patched"):
            tree = work / variant
            cpu_header = tree / "include/grub/arm64/efi/memory.h"
            cpu_header.parent.mkdir(parents=True)
            cpu_header.write_bytes(header)
            common_header = tree / "include/grub/efi/memory.h"
            common_header.parent.mkdir(parents=True)
            common_header.write_text("/* Common EFI declarations are provided by the harness. */\n")
            if variant == "patched":
                subprocess.run(["git", "apply", str(patch)], cwd=tree, check=True,
                               capture_output=True, text=True)
            harness = tree / "allocator.c"
            harness.write_text(PREAMBLE + actual_functions + MAIN)
            executable = tree / "allocator"
            subprocess.run([cc, "-std=c11", "-Wall", "-Wextra", "-Werror",
                            "-I", str(tree / "include"), str(harness), "-o", str(executable)],
                           check=True, capture_output=True, text=True)
            cls.executables[variant] = executable

    def run_model(self, variant, scenario):
        result = subprocess.run([str(self.executables[variant]), scenario],
                                check=True, capture_output=True, text=True)
        return {key: int(value) for key, value in
                (item.split("=") for item in result.stdout.strip().split())}

    def test_stock_32_bit_cap_reproduces_native_memory_map_allocation_failure(self):
        result = self.run_model("stock", "high")
        self.assertEqual(result, {"address": 0, "error": 1, "calls": 2,
                                 "bound0": OLD_LIMIT, "bound1": OLD_LIMIT,
                                 "stored": 0, "freed": 0, "pages": 0})

    def test_actual_package_patch_allocates_memory_map_above_64_gib(self):
        result = self.run_model("patched", "high")
        self.assertEqual(result, {"address": HIGH_BASE + HIGH_SIZE - MAP_PAGES * PAGE_SIZE,
                                 "error": 0, "calls": 2, "bound0": OLD_LIMIT,
                                 "bound1": NEW_LIMIT, "stored": 1,
                                 "freed": 0, "pages": MAP_PAGES})

    def test_low_memory_still_uses_the_first_allocation_attempt(self):
        for variant in self.executables:
            with self.subTest(variant=variant):
                self.assertEqual(self.run_model(variant, "low"), {
                    "address": 0x80000000 - MAP_PAGES * PAGE_SIZE,
                    "error": 0, "calls": 1, "bound0": OLD_LIMIT, "bound1": 0,
                    "stored": 1, "freed": 0, "pages": MAP_PAGES})

    def test_real_exhaustion_still_fails_after_the_high_memory_retry(self):
        for variant, limit in (("stock", OLD_LIMIT), ("patched", NEW_LIMIT)):
            with self.subTest(variant=variant):
                self.assertEqual(self.run_model(variant, "exhaust"), {
                    "address": 0, "error": 1, "calls": 2,
                    "bound0": OLD_LIMIT, "bound1": limit,
                    "stored": 0, "freed": 0, "pages": 0})

    def test_patch_keeps_high_ram_in_the_real_firmware_map_filter(self):
        self.assertEqual(self.run_model("stock", "filter"), {
            "count": 1, "low": 0x40000000, "high": 0, "pages": 0})
        self.assertEqual(self.run_model("patched", "filter"), {
            "count": 2, "low": 0x40000000, "high": HIGH_BASE,
            "pages": HIGH_SIZE // PAGE_SIZE})

    def test_fixed_high_addresses_pass_the_patched_allocator_guard(self):
        self.assertEqual(self.run_model("stock", "fixed"), {
            "address": 0, "error": 2, "calls": 0, "bound0": 0, "bound1": 0,
            "stored": 0, "freed": 0, "pages": 0})
        self.assertEqual(self.run_model("patched", "fixed"), {
            "address": HIGH_BASE, "error": 0, "calls": 1,
            "bound0": HIGH_BASE, "bound1": 0,
            "stored": 1, "freed": 0, "pages": MAP_PAGES})


if __name__ == "__main__":
    unittest.main()
