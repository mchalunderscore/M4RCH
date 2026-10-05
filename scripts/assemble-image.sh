#!/bin/sh
# Build the complete raw SD image. Keep this wrapper compatible with POSIX sh.
set -eu
project_dir=$(CDPATH='' cd -P "$(dirname "$0")/.." && pwd)
action=image
case ${1-} in
    --kernel) action=kernel; shift ;;
    --packages) action=packages; shift ;;
    --loader) action=loader; shift ;;
    --verify) action=verify; shift ;;
    --smoke) action=smoke; shift ;;
esac
exec "${PYTHON:-python3}" "$project_dir/sdboot/build.py" "$action" "$@"
