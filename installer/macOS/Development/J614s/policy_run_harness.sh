#!/bin/bash
set -euo pipefail

here=$(cd -- "$(dirname -- "$0")" && pwd -P)
macos_root=$(cd -- "$here/../.." && pwd -P)
scratch=$(mktemp -d "${TMPDIR:-/tmp}/j614s-policy.XXXXXXXX")
trap 'rm -rf -- "$scratch"' EXIT

swiftc -parse-as-library -module-cache-path "$scratch/cache" \
  "$macos_root/Sources/AuroraAppleInstaller/NativeInspectionPolicy.swift" \
  "$macos_root/Sources/AuroraAppleInstaller/NativeInspectionPolicySource.swift" \
  "$here/policy_harness.swift" -o "$scratch/policy-harness"
"$scratch/policy-harness"
