.POSIX:

PYTHON = python3
DISK =
REPLACE_PENDING = 0

all: image

image: FORCE
	PYTHON="$(PYTHON)" sh scripts/assemble-image.sh

kernel: FORCE
	PYTHON="$(PYTHON)" sh scripts/assemble-image.sh --kernel

packages: FORCE
	PYTHON="$(PYTHON)" sh scripts/assemble-image.sh --packages

cpu-tools: FORCE
	"$(PYTHON)" sdboot/cpu_tools.py

diagnose: FORCE
	"$(PYTHON)" sdboot/collect_sd_logs.py --disk "$(DISK)"

loader: FORCE
	PYTHON="$(PYTHON)" sh scripts/assemble-image.sh --loader

boot: FORCE
	PYTHON="$(PYTHON)" REPLACE_PENDING="$(REPLACE_PENDING)" sh scripts/setup-boot.sh

boot-safe: FORCE
	PYTHON="$(PYTHON)" REPLACE_PENDING="$(REPLACE_PENDING)" sh scripts/setup-boot.sh --safe

boot-status: FORCE
	PYTHON="$(PYTHON)" sh scripts/setup-boot.sh --status

flash: FORCE
	PYTHON="$(PYTHON)" sh scripts/setup-boot.sh --flash --disk "$(DISK)"

verify: FORCE
	PYTHON="$(PYTHON)" sh scripts/assemble-image.sh --verify

smoke: FORCE
	PYTHON="$(PYTHON)" sh scripts/assemble-image.sh --smoke

check: FORCE
	for file in scripts/*.sh sdboot/init sdboot/recovery-enroll.sh templates/*.sh; do sh -n "$$file" || exit; done
	"$(PYTHON)" -m unittest discover -s tests -v

help: FORCE
	@printf '%s\n' 'Build (ordinary user):' '  make              Build the complete SD image (same as make image)' '  make kernel       Build the kernel and matching modules' '  make packages     Build a pacman update kit for installation in Linux' '  make loader       Build NVMe-aware and SD-only internal loaders' '  make cpu-tools    Publish a CPU benchmark and diagnostic kit'
	@printf '%s\n' '' 'Card and boot setup:' '  sudo make flash DISK=/dev/diskN    Erase and verify the SD card' '  sudo make diagnose DISK=/dev/diskN Read saved Linux logs' '  sudo make boot                    Prepare internal boot setup and enrollment' '  sudo make boot-safe               Prepare the SD-only fallback loader' '  sudo make boot-status             Inspect enrollment state'
	@printf '%s\n' '' 'Checks:' '  make check        Run source tests and shell syntax checks' '  make verify       Verify built image and package artifacts' '  make smoke        Test the image in a disposable Linux VM'
	@printf '%s\n' '' 'Variables:' '  PYTHON=python3    Python interpreter path for build and setup commands' '  DISK=/dev/diskN   Explicit SD card for flash or diagnose' '  REPLACE_PENDING=1 Allow boot staging to replace a verified pending loader' '' 'Install routine updates in Linux using the generated update kit.'

FORCE:
