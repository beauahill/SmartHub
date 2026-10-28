#!/usr/bin/env bash
# Counter Home: one-time provisioning for the Galaxy Tab A9+ over USB.
#
# Before running:
#   1. Factory reset the tablet. In the setup wizard connect Wi-Fi but SKIP the Google and
#      Samsung account sign-ins (device owner can only be set while no accounts exist).
#   2. Settings > About tablet > Software information > tap Build number 7 times.
#   3. Settings > Developer options > USB debugging on. Plug in, accept the RSA prompt.
#
# Usage:  ./setup.sh [dashboard_url]
#   e.g.  ./setup.sh http://192.168.0.50:8123/dashboard-counter/0
#
# Prints the API token and the three Home Assistant secrets (counter_display_token,
# counter_display_api, counter_display_status) at the end.

set -euo pipefail
cd "$(dirname "$0")"

PKG=com.counterdisplay.launcher
# Prefer a fresh build (v1.1.0+, with the media volume cap). Fall back to the prebuilt v1.0.0.
BUILT=app/build/outputs/apk/release/app-release.apk
if [ -z "${APK:-}" ]; then
  if [ -f "$BUILT" ]; then APK=$BUILT
  else
    APK=CounterHome-1.0.0.apk
    echo "!! Using the prebuilt $APK. It has no media volume cap; build v1.1.0 to protect the speakers."
  fi
fi
[ -f "$APK" ] || { echo "APK not found: $APK"; exit 1; }
URL=${1:-}

command -v adb >/dev/null || { echo "adb not found. Install Android platform-tools first."; exit 1; }
adb get-state >/dev/null 2>&1 || { echo "No device. Check the cable and the USB debugging prompt."; exit 1; }

echo "== Device: $(adb shell getprop ro.product.model | tr -d '\r')  Android $(adb shell getprop ro.build.version.release | tr -d '\r')"

ACCOUNTS=$(adb shell dumpsys account | grep -c "Account {" || true)
if [ "$ACCOUNTS" != "0" ]; then
  echo "!! $ACCOUNTS account(s) on the tablet. Remove them (or factory reset) before setting device owner."
  exit 1
fi

echo "== Installing $APK"
adb install -r "$APK"

echo "== Making Counter Home the device owner"
adb shell dpm set-device-owner "$PKG/.KioskAdmin"

echo "== Permissions and battery exemptions"
adb shell pm grant "$PKG" android.permission.POST_NOTIFICATIONS || true
adb shell dumpsys deviceidle whitelist +"$PKG" >/dev/null || true
adb shell cmd appops set "$PKG" RUN_ANY_IN_BACKGROUND allow || true

echo "== Removing Samsung extras (only for the kiosk user; a factory reset brings them back)"
for p in \
  com.samsung.android.bixby.agent \
  com.samsung.android.bixby.wakeup \
  com.samsung.android.visionintelligence \
  com.samsung.android.app.spage \
  com.samsung.android.app.tips \
  com.samsung.android.game.gamehome \
  com.samsung.android.game.gametools \
  com.samsung.android.arzone \
  com.samsung.android.app.routines \
  com.samsung.android.mateagent \
  com.sec.android.app.kidshome \
  com.samsung.android.kidsinstaller \
  com.microsoft.skydrive \
  com.microsoft.office.officehubrow \
  com.netflix.partner.activation \
  com.facebook.katana com.facebook.system com.facebook.appmanager com.facebook.services ; do
  adb shell pm uninstall -k --user 0 "$p" >/dev/null 2>&1 && echo "   removed $p" || true
done

echo "== Display settings"
adb shell settings put system screen_off_timeout 1800000
adb shell settings put global stay_on_while_plugged_in 0   # HA decides when the panel is on

TOKEN=$(openssl rand -hex 18 2>/dev/null || head -c 18 /dev/urandom | od -An -tx1 | tr -d ' \n')
echo "== Provisioning API token"
if [ -n "$URL" ]; then
  adb shell am start -n "$PKG/.MainActivity" --es provision_token "$TOKEN" --es provision_url "'$URL'"
else
  adb shell am start -n "$PKG/.MainActivity" --es provision_token "$TOKEN"
fi

IP=$(adb shell ip -4 addr show wlan0 | awk '/inet /{print $2}' | cut -d/ -f1 | tr -d '\r')

cat <<EOF

Done. Counter Home is now the home app and device owner.

  Tablet IP:  ${IP:-unknown}   (give it a DHCP reservation on the EdgeRouter)
  API port:   2323
  API token:  $TOKEN

Add to Home Assistant secrets.yaml:
  counter_display_token: "Bearer $TOKEN"
  counter_display_api: "http://${IP:-TABLET_IP}:2323/{{ path }}"
  counter_display_status: "http://${IP:-TABLET_IP}:2323/status"

Quick test from any machine on the LAN:
  curl -H "Authorization: Bearer $TOKEN" http://${IP:-TABLET_IP}:2323/status

Next: sign in to Google in Android settings (hold the dock clock 3 s, PIN 2580,
"Pause kiosk lock and open Android settings"), install Spotify, YouTube TV,
IPTV Smarters and the Home Assistant app, then tap "Resume kiosk lock".
Change the PIN while you're in there.
EOF
