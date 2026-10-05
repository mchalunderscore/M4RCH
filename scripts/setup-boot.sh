#!/bin/sh
# Prepare Recovery enrollment for the built loader, or write the selected SD.
set -eu
project_dir=$(CDPATH='' cd -P "$(dirname "$0")/.." && pwd)
action=boot
case ${1-} in
    --flash) action=flash; shift ;;
    --status) action=boot-status; shift ;;
    --safe) action=boot-safe; shift ;;
esac
case ${REPLACE_PENDING:-0} in
    0) ;;
    1) set -- --replace-pending "$@" ;;
    *) printf '%s\n' 'REPLACE_PENDING must be 0 or 1.' >&2; exit 2 ;;
esac
exec "${PYTHON:-python3}" "$project_dir/sdboot/build.py" "$action" "$@"
