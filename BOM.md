# Bill of Materials: Counter Display

Quantities are for one display. Dimensions come from the parameters in
[`enclosure/enclosure.py`](enclosure/enclosure.py). If you substitute a part, update the matching
parameter and regenerate the STLs. Prices are left out because they move too often to keep current.

## 1. Display and electronics

| # | Qty | Part | Spec / notes | Used by |
| --- | --- | --- | --- | --- |
| E1 | 1 | Samsung Galaxy Tab A9+ (11", SM-X210 / X216) | 257.1 x 168.7 x 6.9 mm. Bezel pocket is sized to this | `TAB_*` parameters |
| E2 | 1 | Dayton Audio KABD-430 amplifier board (325-430) | 4 x 30 W from two TPA3118, ADAU1701 DSP, Bluetooth 5.0 aptX HD, 10 to 26 V (24 V typical). Board 91.4 x 68.6 mm, 3.5 mm holes on 83.8 x 61.0 mm. Height 20 mm per the user guide, 23 mm per listings. Fed from its AUX input (J13). Run it in 2.1 mode | `AMP_*` parameters, tray standoffs |
| E3 | 1 | ESP32-C3 SuperMini | 22.5 x 18 mm. Runs `esphome/counter-presence.yaml` | `esp32_c3` cradle |
| E4 | 1 | HLK-LD2410C 24 GHz mmWave radar | 22 x 16 mm. Solder wires directly to the pads, no headers | 23 x 17 mm chin pocket |
| E5 | 1 | 5 V buck module, MP1584EN | 22 x 17 mm. 24 V in, 5 V out, feeds the ESP32-C3 5V pin and the radar | `buck_5v` cradle |
| E6 | 1 | USB-C PD step-down module, 12 to 24 V in, USB-C output | 15 W or more. Charges the tablet through the UGREEN adapter's charging port. The cradle is set to 40 x 25 mm; change it to fit your module | `pd_module` cradle |
| E8 | 1 | 24 V DC power adapter, 4 A (96 W) | Regulated. Stays under the KABD-430's 26 V maximum | |
| E9 | 1 | DC barrel jack pigtail, 5.5 x 2.1 mm female | Body under 11 mm diameter | Rear hole in the spine |
| E10 | 1 | Dayton Audio ICP1 or KPX programmer, optional | Only needed to change the KABD-430 DSP program in SigmaStudio, which runs on Windows: crossover, high-pass, limiter, Bluetooth input | J5 programming port |

## 2. Audio path

| # | Qty | Part | Spec / notes | Used by |
| --- | --- | --- | --- | --- |
| A1 | 1 | Right-angle USB-C adapter, male to female, 90° | Plugs into the tablet and turns back into the tray. Must fit within 10 mm of the tablet edge, and carry audio and PD | `USB_CLEAR` notch |
| A2 | 1 | UGREEN 2-in-1 USB-C to 3.5 mm audio adapter with PD charging | Splits the tablet port into a 3.5 mm output and a USB-C charging input. The cradle is set to a 45 x 30 mm body; change it to fit yours | `audio_adapter` cradle |
| A3 | 1 | Dayton KABD functional cable kit, plus a short 3.5 mm stereo cable | The kit's 3.5 mm aux-in jack plugs into J13. The cable runs from the UGREEN audio jack to that jack | |
| A4 | 1 | 3.5 mm ground loop isolator, optional | Only if the speakers hum or pick up charging noise | |

## 3. Speakers

| # | Qty | Part | Spec / notes | Used by |
| --- | --- | --- | --- | --- |
| S1 | 2 | Dayton Audio ND65-4, 2-1/2" aluminum full-range, 4 Ω | 52 mm cutout, 64 mm OD, 48 mm deep, 15 W rated. Left and right, each in a sealed 0.58 L chamber | `FR_CUT`, `FR_FLANGE`, `FR_BC` |
| S2 | 1 | Dayton Audio ND105-4, 4" aluminum midbass, 4 Ω | 93 mm cutout, 105 mm OD, 67 mm deep. Front center | `WF_CUT`, `WF_FLANGE`, `WF_BC` |
| S3 | 1 | Dayton Audio ND105-PR, 4" passive radiator | 93 mm cutout, 105 mm OD, 67 mm deep, Fs 51.5 Hz. Rear center | `PR_CUT`, `PR_FLANGE`, `PR_BC` |
| S4 | 16 | Driver mounting screws, M3 x 10 thread-forming or #4 x 1/2" pan head | 4 per driver, into 2.5 mm blind pilot holes | |
| S5 | 1 roll | Closed-cell foam gasket tape, about 3 mm wide | Seals each driver flange to the baffle | |
| S6 | 1 bag | Polyfill or acoustic wool | Light fill in the full-range chambers, lining in the woofer chamber | |

The woofer and passive radiator face each other front to back. With the listed depths they clear by
about 10 mm.

The pilot holes sit on estimated bolt circles: 58 mm for the ND65 and 99 mm for the ND105 pair.
Measure your drivers and correct `FR_BC`, `WF_BC` and `PR_BC` before printing the tub.

## 4. Hardware

| # | Qty | Part | Spec / notes | Used by |
| --- | --- | --- | --- | --- |
| H1 | 12 | M3 heat-set inserts | For a 4.0 mm hole, up to 6 mm long. 8 in the bezel front, 4 in the spine | `M3_INSERT`, `INSERT_DEPTH` |
| H2 | 8 | M3 x 25 socket head cap screws | Tray to bezel front. The counterbores deepen with the tray, so M3 x 25 always gives about 4 mm insert engagement | `SCREWS` |
| H3 | 4 | M3 x 8 socket or button head screws | Tray to spine. Heads inside the tray | `SPINE_PTS` |
| H4 | 4 | M3 x 6 thread-forming screws | KABD-430 into its 2.6 mm standoff pilots, which are about 4.9 mm deep. Longer screws bottom out | Amp standoffs |
| H5 | 6 | 4 mm dowel pins, 6 mm long | Align the lid to the tub for gluing. Holes are 4.3 mm | `BOSSES` |
| H6 | 12 | Neodymium disc magnets, 6 x 2 mm, N52 | One per tub pocket. Sits 0.2 mm below the surface | `MAG_T_TUB` |
| H7 | 12 | Neodymium disc magnets, 6 x 1 mm, N52 | One per grille ring pocket, flush. Opposite polarity to H6 | `MAG_T_FRAME` |
| H8 | 4 | Silicone bumper feet, 10 mm diameter, about 3 mm tall | Lift the fabric edge off the counter | 10.5 mm recesses |
| H9 | 1 sheet | Adhesive foam, 1.5 mm | Pads on the six tablet back-stop posts, 8 mm diameter | Tray posts |
| H10 | 1 roll | VHB double-sided tape | Holds the PD module, UGREEN adapter, buck and ESP32-C3 in their cradles | `CRADLES` |

## 5. Wiring

| # | Qty | Part | Spec / notes |
| --- | --- | --- | --- |
| W1 | 3 m | Speaker wire, 20 AWG | Three pairs from the KABD-430 down the spine channel and through the 12 mm lid hole |
| W2 | 1 m | Power wire, 18 AWG, red and black | 24 V distribution in the tray |
| W3 | 1 m | Silicone hookup wire, 26 to 28 AWG | Radar to ESP32-C3: 5V, GND, TX, RX |
| W4 | 1 set | Speaker and power connectors for the KABD-430 | The functional cable kit covers the AUX input; check what else ships with your board |
| W5 | | Heat shrink, solder, hot glue | Hot glue seals the full-range wire pass-throughs |

## 6. Printed parts and materials

| # | Qty | Part | Size (mm) | Solid volume |
| --- | --- | --- | --- | --- |
| P1 | 1 | `base_tub.stl` | 300 x 150 x 116 | 850 cm³ |
| P2 | 1 | `lid_spine.stl` | 300 x 150 x 119 | 348 cm³ |
| P3 | 1 | `grille_ring.stl` | 299 x 149 x 112 | 92 cm³ |
| P4 | 1 | `bezel_front.stl` | 284 x 200 x 10 | 136 cm³ |
| P5 | 1 | `bezel_tray.stl` | 284 x 200 x 30 | 207 cm³ |

| # | Qty | Material | Notes |
| --- | --- | --- | --- |
| M1 | 2 kg | PETG, PLA or ASA filament | About 1.6 L of solid volume in total, which is 2 kg of PLA at 100 % infill. Print the tray in PETG or ASA. Avoid carbon or metal-filled filament on the bezel front |
| M2 | 1 piece | Acoustically transparent linen or speaker grille cloth, about 950 x 160 mm | Wraps the grille ring. The perimeter is about 870 mm and the band is 112 mm tall |
| M3 | 1 can | Spray adhesive or thin double-sided tape | Fixes the fabric to the grille ring |
| M4 | 1 tube | Two-part epoxy | Glues the lid to the tub. The seal must be airtight |

## 7. Tools and software

- 3D printer with at least a 300 mm bed axis. A 320 mm or larger bed is recommended.
- Soldering iron with a heat-set insert tip.
- Calipers, to measure the driver bolt circles and the adapter sizes before printing.
- USB-C data cable for flashing the ESP32-C3 and for `adb`.
- Android platform-tools (`adb`) on a computer, to run `android/setup.sh`.
- JDK 17 and the Android SDK, to build Counter Home v1.1.0.
- Home Assistant with the HACS "kiosk-mode" frontend plugin.
- ESPHome 2026.10 or newer. The presence config validates on 2026.10.1.
- On the tablet: Home Assistant companion app, Spotify, YouTube TV and IPTV Smarters, or whatever your dock tiles open.
