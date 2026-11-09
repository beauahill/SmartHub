#!/usr/bin/env bash
# Counter Home: remove Samsung, Google and partner bloat from the tablet.
#
# Usage:  ./debloat.sh            remove everything in debloat-packages.txt that's installed
#         ./debloat.sh --dry-run  only list what would be removed
#
# Uses "pm uninstall -k --user 0", which hides the app for the tablet's only user. Nothing in
# /system changes. restore.sh brings any package back; a factory reset brings all of them back.
# Each run appends what it removed to debloat-removed.log next to this script.

set -euo pipefail
cd "$(dirname "$0")"

LIST=debloat-packages.txt
LOG=debloat-removed.log
DRY=0; [ "${1:-}" = "--dry-run" ] && DRY=1

command -v adb >/dev/null || { echo "adb not found. Install Android platform-tools first."; exit 1; }
adb get-state >/dev/null 2>&1 || { echo "No device. See setup.sh for wireless debugging."; exit 1; }

INSTALLED=$(adb shell pm list packages --user 0 | sed 's/^package://' | tr -d '\r')
removed=0; failed=0
[ $DRY = 1 ] || echo "# $(date -Is) $(adb shell getprop ro.product.model | tr -d '\r')" >> "$LOG"

while read -r line; do
  p=${line%%#*}; p=$(echo "$p" | tr -d '[:space:]')
  [ -n "$p" ] || continue
  grep -qx "$p" <<<"$INSTALLED" || continue
  if [ $DRY = 1 ]; then echo "   would remove $p"; removed=$((removed+1)); continue; fi
  out=$(adb shell pm uninstall -k --user 0 "$p" </dev/null 2>&1 | tr -d '\r')
  if [ "$out" = "Success" ]; then
    echo "   removed $p"; echo "$p" >> "$LOG"; removed=$((removed+1))
  else
    echo "!! kept $p ($out)"; failed=$((failed+1))
  fi
done < "$LIST"

if [ $DRY = 1 ]; then echo "== $removed package(s) would be removed"
else echo "== Removed $removed package(s), $failed refused"; fi
