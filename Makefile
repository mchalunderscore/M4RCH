.POSIX:

PYTHON = python3
DISK =
REPLACE_PENDING = 0
STUB_OUTPUT = out/stub-upgrade-25G83-candidate
PREFLIGHT =


all: image

image: FORCE
	PYTHON="$(PYTHON)" sh scripts/assemble-image.sh

kernel: FORCE
	PYTHON="$(PYTHON)" sh scripts/assemble-image.sh --kernel

packages: FORCE
	PYTHON="$(PYTHON)" sh scripts/assemble-image.sh --packages

internal-esp-review: FORCE
	"$(PYTHON)" scripts/internal-esp.py --review

internal-esp: FORCE
	"$(PYTHON)" scripts/internal-esp.py

nvme-review: FORCE
	"$(PYTHON)" scripts/migrate-nvme-macos.py --review --preflight "$(PREFLIGHT)"

nvme-repair-initramfs: FORCE
	"$(PYTHON)" scripts/repair-nvme-initramfs.py

nvme-resume: FORCE
	"$(PYTHON)" scripts/migrate-nvme-macos.py --resume --preflight "$(PREFLIGHT)"

nvme-migrate: FORCE
	"$(PYTHON)" scripts/migrate-nvme-macos.py --preflight "$(PREFLIGHT)"

nvme-preflight: FORCE
	"$(PYTHON)" scripts/nvme-preflight.py --disk "$(DISK)"

nvme-kit: FORCE
	"$(PYTHON)" scripts/prepare-nvme-kit.py

cpu-tools: FORCE
	"$(PYTHON)" sdboot/cpu_tools.py

diagnose: FORCE
	"$(PYTHON)" sdboot/collect_sd_logs.py --disk "$(DISK)"

loader-internal: FORCE
	"$(PYTHON)" sdboot/build.py loader-internal

loader-split: FORCE
	"$(PYTHON)" sdboot/build.py loader-split

boot-split: FORCE
	"$(PYTHON)" scripts/setup-split-boot.py

stage2: FORCE
	"$(PYTHON)" scripts/setup-split-boot.py --stage2-only

loader: FORCE
	PYTHON="$(PYTHON)" sh scripts/assemble-image.sh --loader

boot-internal: FORCE
	"$(PYTHON)" scripts/setup-internal-boot.py

boot: FORCE
	PYTHON="$(PYTHON)" REPLACE_PENDING="$(REPLACE_PENDING)" sh scripts/setup-boot.sh

boot-safe: FORCE
	PYTHON="$(PYTHON)" REPLACE_PENDING="$(REPLACE_PENDING)" sh scripts/setup-boot.sh --safe

stub-upgrade: FORCE
	"$(PYTHON)" scripts/prepare-stub-upgrade.py --output "$(STUB_OUTPUT)"

stub-diagnose: FORCE
	"$(PYTHON)" scripts/diagnose-stub-upgrade.py

stub-install: FORCE
	"$(PYTHON)" sdboot/stub_upgrade.py install --candidate "$(STUB_OUTPUT)"

stub-policy-repair: FORCE
	"$(PYTHON)" sdboot/stub_upgrade.py policy-repair

stub-rollback: FORCE
	"$(PYTHON)" sdboot/stub_upgrade.py rollback

stub-finish: FORCE
	"$(PYTHON)" sdboot/stub_upgrade.py finish

boot-status: FORCE
	PYTHON="$(PYTHON)" sh scripts/setup-boot.sh --status

flash: FORCE
	PYTHON="$(PYTHON)" sh scripts/setup-boot.sh --flash --disk "$(DISK)"

verify: FORCE
	PYTHON="$(PYTHON)" sh scripts/assemble-image.sh --verify

smoke: FORCE
	PYTHON="$(PYTHON)" sh scripts/assemble-image.sh --smoke

check: FORCE
	for file in scripts/*.sh sdboot/init tools/nvme/init sdboot/recovery-enroll.sh templates/*.sh; do sh -n "$$file" || exit; done
	"$(PYTHON)" -m unittest discover -s tests -v

help: FORCE
	@printf '%s\n' 'Split internal boot:' '  make loader-split        Build enrolled stage 1 and ESP boot.bin stage 2' '  sudo make boot-split     Back up/write ESP boot.bin and prepare stage-1 enrollment' '  sudo make stage2         Back up/update ESP boot.bin only; no enrollment changes' '  make loader-gravity      Build pinned Gravity stage 2 with J614s fixes' '  sudo make stage2-gravity Deploy Gravity stage 2 and native check kit'  ''
	@printf '%s\n' 'Build (ordinary user):' '  make              Build the complete SD image (same as make image)' '  make kernel       Build the kernel and matching modules' '  make packages     Build a pacman update kit for installation in Linux' '  make loader       Build NVMe-aware and SD-only internal loaders' '  make loader-internal Build the internal-only NVMe UEFI bridge' '  make nvme-kit     Prepare the native NVMe root migration kit (no disk writes)' '  make cpu-tools    Publish the native handover and CPU/USB diagnostic kit' '  make stub-upgrade Prepare an isolated 25G83 Apple stub (does not install)'
	@printf '%s\n' '' 'Card and boot setup:' '  sudo make flash DISK=/dev/diskN    Erase and verify the SD card' '  sudo make nvme-review PREFLIGHT=path   Review the offline macOS migration' '  sudo make nvme-migrate PREFLIGHT=path  Clone SD root to the reserved NVMe span' '  sudo make nvme-preflight          Read-only macOS NVMe migration checks and GPT backup' '  sudo make diagnose DISK=/dev/diskN Read saved Linux logs' '  sudo make internal-esp-review     Review internal ESP and NVMe /boot setup' '  sudo make internal-esp            Stage internal ESP and save Mac-local rollback' '  sudo make boot-internal           Enroll the internal-only NVMe bridge' '  sudo make boot                    Prepare internal boot setup and enrollment' '  sudo make boot-safe               Prepare the SD-only fallback loader' '  sudo make boot-status             Inspect enrollment state' '  sudo make stub-diagnose           Capture private Apple upgrade diagnostics' '  sudo make stub-install            Back up and upgrade the prepared Apple stub' '  sudo make stub-rollback           Restore the saved Apple stub and prepare Recovery' '  sudo make stub-finish             Verify completed stub Recovery enrollment'
	@printf '%s\n' '' 'Checks:' '  make check        Run source tests and shell syntax checks' '  make verify       Verify built image and package artifacts' '  make smoke        Test the image in a disposable Linux VM'
	@printf '%s\n' '' 'Variables:' '  PYTHON=python3    Python interpreter path for build and setup commands' '  DISK=/dev/diskN   Explicit SD card for flash or diagnose' '  REPLACE_PENDING=1 Allow boot staging to replace a verified pending loader' '  STUB_OUTPUT=path  Prepared Apple-stub candidate directory' '' 'Install routine updates in Linux using the generated update kit.'

FORCE:

loader-gravity: FORCE
	"$(PYTHON)" sdboot/build.py loader-gravity

stage2-gravity: FORCE
	"$(PYTHON)" scripts/setup-split-boot.py --stage2-only --gravity
