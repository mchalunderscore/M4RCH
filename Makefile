PYTHON = python3

.PHONY: all packages check legacy-image
all: packages

packages:
	"$(PYTHON)" packages/tools/build.py

check:
	"$(PYTHON)" -m py_compile packages/tools/*.py
	@for source in packages/install.sh packages/tools/*.sh packages/*/PKGBUILD; do bash -n "$$source" || exit; done

# Historical SD-card workflow, kept separate from current package updates.
legacy-image:
	$(MAKE) -f Makefile.legacy image
