# Aurora installer integration

This directory vendors the source from Aurora installer commit `704f585` and incorporates the experimental-admission work from [PR 49](https://github.com/aurora-silicon/aurora-installer/pull/49), head `9342ac0f9611b26f52652d70693469f0c016a920`, together with local J614s changes. The previous development checkout had an unfinished Git merge with resolved files and additional uncommitted work; this directory records the resulting source tree, not an upstream merge commit. The Aurora license and attribution are retained in this directory.

The root repository pins Aurora's original `aura` and Asahi `artwork` submodules at their prior revisions. Obtain them with `git submodule update --init installer/aura installer/artwork` when using the legacy installer build. They are not required for the native macOS Swift build.

The vendored source predates current Aurora J614s support. See the [installer comparison](../docs/installer-upstream.md) for the current fork, historical development tools and validation limits. No device firmware, device calibration, generated signing key, sealed developer catalog, installation image or boot artifact is part of this source tree.
