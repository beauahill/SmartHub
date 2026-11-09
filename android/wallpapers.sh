#!/usr/bin/env bash
# Pictures for the counter display's sleep screen, over the Counter Home API.
#
#   ./wallpapers.sh list
#   ./wallpapers.sh push photo1.jpg photo2.jpg ...     # adds or replaces, keeps the file names
#   ./wallpapers.sh delete photo1.jpg
#
# Reads the tablet address and token from ../android/keystore/ha-secrets.yaml (counter_display_api,
# counter_display_token) unless TABLET (host:port) and TOKEN are set in the environment.
# JPEG, PNG and WebP up to 20 MB each; the tablet is 1920x1200, so anything around that is plenty.

set -euo pipefail
cd "$(dirname "$0")"

SECRETS=keystore/ha-secrets.yaml
if [ -z "${TABLET:-}" ] && [ -f "$SECRETS" ]; then
  TABLET=$(sed -nE 's#^counter_display_api: *"?http://([^/]+)/.*#\1#p' "$SECRETS")
fi
if [ -z "${TOKEN:-}" ] && [ -f "$SECRETS" ]; then
  TOKEN=$(sed -nE 's/^counter_display_token: *"?Bearer ([^"]+)"?.*/\1/p' "$SECRETS")
fi
[ -n "${TABLET:-}" ] && [ -n "${TOKEN:-}" ] || { echo "Set TABLET=host:port and TOKEN, or fill $SECRETS"; exit 1; }

api() { curl -sS -m 120 -H "Authorization: Bearer $TOKEN" "$@"; }

case "${1:-}" in
  list)
    api "http://$TABLET/wallpapers" | python3 -c 'import json,sys; [print(f"  {w[\"bytes\"]//1024:6d} KB  {w[\"name\"]}") for w in json.load(sys.stdin)["wallpapers"]] or print("  (none; the built-in gradients are showing)")'
    ;;
  push)
    shift; [ $# -gt 0 ] || { echo "push: give image files"; exit 1; }
    for f in "$@"; do
      name=$(basename "$f")
      printf '%s -> ' "$name"
      api -X PUT --data-binary @"$f" "http://$TABLET/wallpapers/$(python3 -c 'import sys,urllib.parse;print(urllib.parse.quote(sys.argv[1]))' "$name")"
      echo
    done
    ;;
  delete)
    shift; [ $# -gt 0 ] || { echo "delete: give names"; exit 1; }
    for name in "$@"; do
      printf '%s -> ' "$name"
      api -X DELETE "http://$TABLET/wallpapers/$(python3 -c 'import sys,urllib.parse;print(urllib.parse.quote(sys.argv[1]))' "$name")"
      echo
    done
    ;;
  *)
    sed -n 2,13p "$0"; exit 1 ;;
esac
