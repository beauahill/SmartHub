# SmartHub: Counter Display

An open source kitchen-counter smart display and sound system. A Samsung Galaxy Tab A9+ sits in a
tilted 3D-printed bezel on top of a linen-wrapped speaker base. A custom Android home app shows a
Home Assistant dashboard full screen with a dock of app tiles. A 24 GHz mmWave radar in the bezel
chin wakes the screen when someone walks up.

![Counter display](enclosure/renders/hero.png)

| ![Exploded view](enclosure/renders/exploded.png) | ![Speaker base internals](enclosure/renders/internals.png) |
| --- | --- |
| ![Rear](enclosure/renders/rear.png) | ![Side](enclosure/renders/side.png) |

The full parts list is in [BOM.md](BOM.md).

## How it works

- **Display.** The tablet runs **Counter Home**, a small Kotlin launcher that replaces Fully Kiosk.
  It is the Android device owner, so it can pin itself with lock task mode, turn the panel off and
  set brightness without root. No root means YouTube TV and Spotify keep full DRM.
- **Control.** Counter Home runs a token-protected HTTP API on port 2323. Home Assistant uses it to
  wake, dim, blank and navigate the display.
- **Presence.** An ESP32-C3 SuperMini reads an HLK-LD2410C radar and reports presence to Home
  Assistant over ESPHome. Automations wake the screen, fall back to a dim clock, then turn it off.
- **Sound.** A Wondom JAB4 Bluetooth/DSP amplifier in the bezel tray drives two Dayton ND65 full-range
  drivers in sealed side chambers, plus a Dayton ND105 woofer loaded by a rear ND105 passive radiator.
- **Power.** One 24 V adapter enters through the rear of the spine. It feeds the amp directly, a
  USB-C PD module that charges the tablet, and a small 5 V buck for the ESP32 and radar.

## Repository layout

| Path | What it is |
| --- | --- |
| [`android/`](android) | Counter Home launcher: Kotlin source, Gradle build, `setup.sh` provisioning script |
| `android/CounterHome.apk` | Prebuilt v1.0.0 release |
| [`esphome/counter-presence.yaml`](esphome/counter-presence.yaml) | ESP32-C3 + LD2410C presence sensor firmware |
| [`homeassistant/packages/counter_display.yaml`](homeassistant/packages/counter_display.yaml) | REST commands, status sensors and the wake / ambient / off automations |
| [`homeassistant/auth_trusted_networks.yaml`](homeassistant/auth_trusted_networks.yaml) | Lets the dashboard load without a login screen |
| [`enclosure/enclosure.py`](enclosure/enclosure.py) | Parametric enclosure model (manifold3d). Generates every STL |
| `enclosure/stl/` | Print-ready STLs, already in print orientation |
| `enclosure/renders/` | Renders of the assembled and exploded design |
| [`BOM.md`](BOM.md) | Bill of materials |

## Build order

### 1. Print the enclosure

The STLs in `enclosure/stl/` are ready to slice. They are the `print_*.stl` outputs of the script,
already oriented for printing.

| Part | Size (mm) | Notes |
| --- | --- | --- |
| `base_tub` | 300 x 150 x 116 | Speaker box with two sealed full-range chambers |
| `lid_spine` | 300 x 150 x 119 | Top plate and tilted stand in one piece. Glued to the tub |
| `grille_ring` | 299 x 149 x 112 | Linen wraps around it. Slides on from below, held by magnets |
| `bezel_front` | 276 x 200 x 10 | Prints face down. Holds the tablet and the radar |
| `bezel_tray` | 276 x 200 x 26 | Prints back wall down. Holds the amp and power modules |

You need a printer with at least a 300 mm bed axis; a 320 mm or larger bed is more comfortable.
Use PETG or ASA for the bezel tray, because it sits behind a charging tablet and an amplifier.
Do not use carbon-fiber or metal-filled filament for the bezel front: the radar looks through its
2.4 mm lip.

To change dimensions, edit the `PARAMETERS` block in `enclosure.py` and regenerate:

```
pip install -r enclosure/requirements.txt
python enclosure/enclosure.py enclosure/out
```

The script prints part volumes and the acoustic volumes: about 0.58 L per full-range chamber and
2.77 L gross for the woofer chamber.

### 2. Assemble

1. Press the M3 heat-set inserts into the bezel front (8) and the spine (4).
2. Glue the magnets into the tub and grille ring pockets. Check polarity before the glue sets.
3. Wire the drivers, pass the full-range leads through the chamber holes, and seal them with hot glue.
   Mount the drivers from the outside on gasket tape. The model has no pilot holes, so mark and drill them.
4. Add light stuffing, then glue the lid to the tub using the six dowels for alignment. The joint must be airtight.
5. Wrap the linen around the grille ring, then slide the ring onto the tub.
6. Bolt the tray to the spine, mount the amp on its standoffs, and fit the buck, PD module, ESP32-C3 and radar.
7. Put foam on the six tablet back-stop posts, drop in the tablet, and screw the front bezel on with M3 x 25 screws.

### 3. Flash the presence sensor

```
cd esphome
esphome run counter-presence.yaml
```

The first flash needs USB; after that updates go over the air. Wiring is at the top of the YAML.
It needs `counter_presence_api_key`, `ota_password`, `wifi_ssid` and `wifi_password` in your
ESPHome `secrets.yaml`. Suggested radar tuning is in the YAML comments.

### 4. Provision the tablet

1. Factory reset the tablet. Connect Wi-Fi, skip every Google and Samsung sign-in, and turn on USB debugging.
   Device owner can only be set while the tablet has no accounts.
2. On your computer, with Android platform-tools installed:

   ```
   cd android
   ./setup.sh http://<HA_IP>:8123/dashboard-counter/0?kiosk
   ```

   It installs the APK, makes Counter Home the device owner, removes Samsung extras, and prints the
   tablet IP, the API token and the Home Assistant secrets. Reserve that IP on your router.
3. On the tablet, hold the dock clock for 3 seconds and enter PIN `2580`. Choose
   "Pause kiosk lock and open Android settings". Sign in to Google, install Spotify, YouTube TV,
   IPTV Smarters and the Home Assistant app, set Battery protection to Maximum, and make Home
   Assistant the default digital assistant. Pair the JAB4 over Bluetooth. Then tap "Resume kiosk lock".
4. Change the settings PIN. The default PIN is public in this repository.

Do the YouTube TV and Spotify sign-ins while the kiosk lock is paused. Google's login screens
belong to other packages, and lock task mode blocks them.

### 5. Configure Home Assistant

1. Copy `homeassistant/packages/counter_display.yaml` into `config/packages/` and enable packages in
   `configuration.yaml`.
2. Add the three secrets `setup.sh` printed to `secrets.yaml`:
   `counter_display_token`, `counter_display_api` and `counter_display_status`.
3. Merge `homeassistant/auth_trusted_networks.yaml` into the `homeassistant:` block. Create a non-admin
   `counter` user and put its user ID and the tablet IP in the snippet.
4. Install the HACS "kiosk-mode" plugin so `?kiosk` hides the header and sidebar, then restart Home Assistant.

The automations expect the presence entity `binary_sensor.counter_presence_presence`, which the
ESPHome config creates.

| Time with nobody present | What happens |
| --- | --- |
| Someone arrives | Screen on. Brightness 25 from 22:00 to 06:00, auto otherwise |
| 2 minutes | Dim clock overlay, if the dashboard is in front |
| 10 minutes | Panel off, if the dashboard is in front |
| 30 minutes | Back to the dashboard and panel off, if another app was open |

A notification fires if the tablet battery stays above 42 °C for 5 minutes.

## Counter Home API

Every call needs `Authorization: Bearer <token>` or `?token=<token>`. Port 2323.

| Call | Does |
| --- | --- |
| `GET /status` | JSON: screenOn, ambient, launcherInFront, deviceOwner, kioskPaused, battery, charging, batteryTempC, ip |
| `POST /screen/on`, `/screen/off`, `/screen/toggle` | Panel power |
| `POST /ambient/on`, `/ambient/off` | Dim clock overlay, tap to dismiss |
| `POST /home` | Back to the dashboard from any app |
| `POST /launch?app=Music` | Tile label or package name |
| `POST /assist` | Opens the default assistant (HA Assist) |
| `POST /navigate?url=...` | Load any URL in the dashboard view, such as a camera page when the doorbell rings |
| `POST /brightness?value=0-255` or `?value=auto` | Backlight |
| `POST /reload` | Reload the dashboard |
| `GET /config`, `POST /config` | Read or change settings as JSON: haUrl, tiles, dockSide, kioskLock, pin, port |

Quick test from any machine on the LAN:

```
curl -H "Authorization: Bearer <token>" http://<tablet_ip>:2323/status
```

Example tiles JSON, for the settings screen or `POST /config`:

```json
{"tiles": [
  {"label": "Music",   "package": "com.spotify.music", "color": "#1F8F4E"},
  {"label": "Live TV", "package": "com.google.android.apps.youtube.unplugged", "color": "#C43B33"},
  {"label": "IPTV",    "package": "com.nst.iptvsmarterstvbox", "color": "#3A62B8"},
  {"label": "Assist",  "action": "assist", "color": "#16A3C9"}
]}
```

Tile actions are `assist`, `reload` and `home`. The dock can sit on the right, left or bottom.

## Building the app

You need JDK 17+ and the Android SDK with platform 34. Point `android/local.properties` at the SDK
with `sdk.dir=/path/to/Android/sdk`, then:

```
cd android
./gradlew assembleRelease
adb install -r app/build/outputs/apk/release/app-release.apk
```

The app has no dependencies beyond the Android framework and the Kotlin stdlib.

**The signing keystore is not in this repository.** The repository is public, and anyone holding the
key could sign an update that replaces the device-owner app. Copy your `counterhome.jks` into
`android/keystore/` before building; that folder is git-ignored. Without the keystore the release
APK builds unsigned. Updates must be signed with the same key, or Android refuses to install them
over the device-owner app, and replacing a device owner takes a factory reset. Back the keystore up.

Store and key passwords default to the values the keystore was created with. Override them with the
Gradle properties `counterhome.storePassword`, `counterhome.keyAlias` and `counterhome.keyPassword`,
for example in `~/.gradle/gradle.properties`.

## Undo

Open the settings screen and choose "Release device owner". The tablet goes back to being a normal
Android tablet. A factory reset also clears it.

## Design review notes

These came out of reviewing the Cowork artifact. Check them before you print or buy parts.

- **Magnets.** The pockets in the tub and grille ring total 3.2 mm, so a single 6 x 3 mm magnet
  cannot sit on both sides. Use a 6 x 2 mm magnet in the tub and a 6 x 1 mm magnet in the ring at
  each of the 12 positions. BOM.md lists them that way.
- **Tablet USB-C.** The bezel leaves 6 mm past the tablet's port edge, and the notch turns back into
  the tray. Check that your right-angle USB-C adapter or plug fits in 6 mm before printing the bezel.
- **Tray mounts.** Only the JAB4 has standoffs. Fix the ESP32-C3, buck and PD module with VHB tape.
  The JAB4 standoff pattern is 84 x 61 mm; confirm it against your board.
- **Driver power.** The ND65 full-range drivers are rated 15 W, and the JAB4 can deliver more at 24 V.
  Cap the volume, or program a high-pass and limiter into the JAB4 DSP with a Wondom ICP5.
- **Bed size.** The tub, lid and grille ring are 300 mm long. They will not fit a 256 mm bed, even diagonally.
- **Mesh.** `base_tub.stl` has four non-manifold edges where brace columns meet the walls. Slicers
  repair this automatically.
