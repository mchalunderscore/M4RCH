"""Pinned J614s ANS handoff for the explicitly selected NVMe loader."""
from pathlib import Path

from common import run, sha256

M1N1_REVISION = "16b1f61fd2a995f855da8909411d06005d1e2b35"
WALLACE_REVISION = "55f116dd0e0f28d1412c6be728a101f7d861c473"
BASE_SHA256 = "061b3c6aea60387e90b368eff6c3beeab121a7f4f9e57ec85a4d6cd12a8f1702"
RESULT_SHA256 = "8e1dd3624647e0a53b142b43127707ac6c0d3f4483d4456b87a67409278bba74"
HEADER_RESULT_SHA256 = "2d02f48a3a7c3b250e5977894aaf530e9ce0b6cc2012fac7e88d2307a1cfe514"
RTKIT_BASE_SHA256 = {
    "src/rtkit.c": "f0cfc194bd8996abdf404f4d5052d284c76f0ceb9613d77933226990703584f4",
    "src/rtkit.h": "e4dbd8f2693b288991642645d8e26644221e2bc5f66858943f099518722ab82f",
}
RTKIT_RESULT_SHA256 = {
    "src/rtkit.c": "21becedabcf206721a4953ddc48c4232fc9a577497365b8746e6b4fb7b75edb4",
    "src/rtkit.h": "35a6f8bff6fd0537e56fe628a5f9718dc579d77c79031b85c9d0aea4f3179951",
}
PATCHES = {
    "m1n1-nvme-upstream-read-count.patch": "6ab09540a4d065a35b46043afc1d4b6f6dcc1314f992a6cd2c1c42e300cd8cf2",
    "m1n1-nvme-upstream-dma-direction.patch": "031e62624a56746184ca0653c347b8aa59f113c24962ae028cc4c3f0a9d4e72a",
    "m1n1-nvme-upstream-tcb-opcode.patch": "c3db55aa014f449e3fd648d0c8bb87f675b95073347bfc3f6d31591f9ceb3f24",
    "m1n1-nvme-upstream-prp-check.patch": "7d9bf38996c5be7c9067c219bca2e913c8de8c8ea784ef033612dcd3b8cf3dc6",
    "m1n1-nvme-upstream-t8132.patch": "af03240c509e430fe9956843e460e54fa6ed1f8804e1908a90d36d011397a52c",
    "m1n1-nvme-j614s-handoff-v2.patch": "a8d248ec9810136ae2db98bda7769a8774e2e591c8d674855abd779c7f97767a",
    "m1n1-nvme-checked-lifetime.patch": "33c6896e4612e5a2966db9be61cf0f7157c7f8dc0f0104bb95748fa4fe86bc25",
}
UPSTREAM_COMMITS = (
    "34925643ca627a95b193b43632fae09e270b175e",
    "b0cdce107543235c8a83c616a0d12aae4c5fc248",
    "0e77db5bf051274362bdf18540caa0f258aaac66",
    "1aead9e78af0096d4dd2203ae73ec10556c8b26e",
    "53f8ee9b54ba52b7f87e607e8206a8c827f06b04",
)
MARKER = b"arch-m4 NVMe handoff v2: initializing ANS before UEFI"
DT_MARKER = "arch-m4,ans-handoff"
DT_MARKER_VALUE = "v2"


def inputs(project, lock):
    if lock["m1n1"]["revision"] != M1N1_REVISION or lock["wallace"]["revision"] != WALLACE_REVISION:
        raise ValueError("NVMe handoff must be reviewed against the pinned m1n1 and Wallace sources")
    for name, expected in PATCHES.items():
        if sha256(Path(project) / "patches" / name) != expected:
            raise ValueError(f"NVMe handoff patch failed verification: {name}")
    return {
        "m1n1_revision": M1N1_REVISION,
        "wallace_revision": WALLACE_REVISION,
        "upstream_commits": list(UPSTREAM_COMMITS),
        "patches": dict(PATCHES),
        "base_nvme_sha256": BASE_SHA256,
        "result_nvme_sha256": RESULT_SHA256,
        "result_nvme_header_sha256": HEADER_RESULT_SHA256,
        "rtkit_base_sha256": dict(RTKIT_BASE_SHA256),
        "rtkit_result_sha256": dict(RTKIT_RESULT_SHA256),
        "uefi_hook_sha256": sha256(Path(__file__)),
        "native_verified": False,
        "scope": "J614s/T6040 board 4; checked ANS init and shutdown before UEFI",
        "provenance": "Five reviewed Asahi NVMe commits through 53f8ee9b54ba plus guarded local handoff",
        "runtime_marker": {"path": "/chosen/" + DT_MARKER, "value": DT_MARKER_VALUE},
    }


def prepare(m1n1, stage):
    """Apply the optional NVMe source updates; no default loader calls this."""
    del stage
    m1n1 = Path(m1n1)
    project = Path(__file__).resolve().parents[1]
    paths = [project / "patches" / name for name in PATCHES]
    for path in paths:
        if sha256(path) != PATCHES[path.name]:
            raise ValueError(f"NVMe handoff patch failed verification: {path.name}")
    source = m1n1 / "src/nvme.c"
    if sha256(source) != BASE_SHA256:
        raise ValueError("NVMe handoff base source differs from the reviewed pinned file")
    for name, digest in RTKIT_BASE_SHA256.items():
        if sha256(m1n1 / name) != digest:
            raise ValueError(f"NVMe handoff RTKit base differs: {name}")
    for path in paths:
        run(["git", "apply", "--check", path], cwd=m1n1)
        run(["git", "apply", path], cwd=m1n1)
    if sha256(source) != RESULT_SHA256 or sha256(m1n1 / "src/nvme.h") != HEADER_RESULT_SHA256:
        raise ValueError("NVMe handoff result differs from the reviewed source")
    for name, digest in RTKIT_RESULT_SHA256.items():
        if sha256(m1n1 / name) != digest:
            raise ValueError(f"NVMe handoff RTKit result differs: {name}")


def prepare_uefi(m1n1):
    """Publish a live marker only after the checked ANS shutdown succeeds.

    kboot_prepare_dt has already packed the blob. Reopen it using its original
    allocated size, then repack after adding the marker. U-Boot and GRUB inherit
    this live DT; the baseline DTB and SD overlay never manufacture the marker.
    """
    path = Path(m1n1) / "src/kboot.c"
    source = path.read_text()
    anchor = '    printf("Setting SMP mode to WFE...\\n");'
    if source.count(anchor) != 1 or '#include "nvme.h"' in source:
        raise ValueError("Pinned m1n1 UEFI handoff sequence changed")
    hook = '''    /* This hook is present only in the optional ANS-aware loader. */
    if (!nvme_prepare_handoff()) {
        printf("SDBOOT: ANS shutdown failed; refusing UEFI handoff\\n");
        return -1;
    }
    if (fdt_open_into(dt, dt, dt_bufsize)) {
        printf("SDBOOT: cannot reopen live DT for ANS marker\\n");
        return -1;
    }
    int chosen = fdt_path_offset(dt, "/chosen");
    if (chosen < 0 || fdt_setprop_string(dt, chosen, "arch-m4,ans-handoff", "v2") ||
        fdt_pack(dt)) {
        printf("SDBOOT: cannot publish ANS handoff marker\\n");
        return -1;
    }
    printf("SDBOOT: ANS handoff v2 complete\\n");

'''
    path.write_text('#include "nvme.h"\n' + source.replace(anchor, hook + anchor))


def check_binary(path, *, uefi=False):
    data = Path(path).read_bytes()
    if MARKER not in data or b"unexpected J614s ANS address translation" not in data:
        raise ValueError("NVMe test prefix is missing its guarded ANS handoff")
    if uefi and DT_MARKER.encode() not in data:
        raise ValueError("NVMe UEFI prefix is missing its live handoff marker")
