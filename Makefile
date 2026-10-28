PYTHON = python3

.PHONY: all packages check
all: packages

packages:
	"$(PYTHON)" packages/tools/build.py

check:
	"$(PYTHON)" -m py_compile packages/tools/*.py
	@for source in packages/install.sh packages/tools/*.sh packages/*/PKGBUILD; do bash -n "$$source" || exit; done
	"$(PYTHON)" -m unittest discover -s tests
	"$(PYTHON)" packages/tools/test-steam-launcher.py
