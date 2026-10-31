PYTHON = python3
PACKAGE ?=

.PHONY: all help prepare-package packages check
all: help

help:
	@printf '%s\n' 'Native AArch64 builds: make prepare-package PACKAGE=linux-m4rch' \
	                 '                       make packages PACKAGE=linux-m4rch' \
	                 'Packages: linux-m4rch m1n1-m4rch u-boot-m4rch mesa-m4rch' \
	                 'Builds never install packages. See packages/README.md.'

prepare-package:
	"$(PYTHON)" packages/tools/native.py prepare $(PACKAGE)

packages:
	"$(PYTHON)" packages/tools/native.py build $(PACKAGE)

check:
	"$(PYTHON)" -c 'import ast, pathlib; [ast.parse(p.read_bytes(), filename=str(p)) for p in pathlib.Path("packages/tools").glob("*.py")]'
	@for source in packages/*/PKGBUILD; do bash -n "$$source" || exit; done
	"$(PYTHON)" -B -m unittest discover -s tests
	"$(PYTHON)" -B packages/tools/test-steam-launcher.py
