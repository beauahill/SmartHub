#!/usr/bin/env bash
# Counter Home: put back packages that debloat.sh removed.
#
# Usage:  ./restore.sh com.samsung.android.calendar [more packages...]
#         ./restore.sh --all     restore everything in debloat-packages.txt
#
# Uses "cmd package install-existing", which re-enables the copy still in /system. No download.

set -euo pipefail
cd "$(dirname "$0")"

[ $# -gt 0 ] || { sed -n '2,7p' "$0"; exit 1; }
adb get-state >/dev/null 2>&1 || { echo "No device. See setup.sh for wireless debugging."; exit 1; }

if [ "$1" = "--all" ]; then
  set -- $(sed 's/#.*//' debloat-packages.txt | tr -s '[:space:]' '\n' | grep .)
fi

for p in "$@"; do
  out=$(adb shell cmd package install-existing --user 0 "$p" </dev/null 2>&1 | tr -d '\r')
  case "$out" in
    *"installed for user"*) echo "   restored $p" ;;
    *) echo "!! $p: $out" ;;
  esac
done
