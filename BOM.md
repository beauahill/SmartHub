# Bill of Materials: Counter Display

Quantities are for one display. Dimensions come from the parameters in
[`enclosure/enclosure.py`](enclosure/enclosure.py). If you substitute a part, update the matching
parameter and regenerate the STLs. Prices are left out because they move too often to keep current.

## 1. Display and electronics

| # | Qty | Part | Spec / notes | Used by |
| --- | --- | --- | --- | --- |
| E1 | 1 | Samsung Galaxy Tab A9+ (11", SM-X210 / X216) | 257.1 x 168.7 x 6.9 mm. Bezel pocket is sized to this | `TAB_*` parameters |
| E2 | 1 | Wondom JAB4 (AA-JA33285) amplifier board | 4 x 30 W TPA3118, Bluetooth 5.0, ADAU1701 DSP, 10 to 26 V, about 91 x 68 mm. Run it in 2.1 mode | Tray standoffs, 84 x 61 mm pattern |
| E3 | 1 | ESP32-C3 SuperMini | Runs `esphome/counter-presence.yaml` | Bezel tray |
| E4 | 1 | HLK-LD2410C 24 GHz mmWave radar | 22 x 16 mm. Solder wires directly to the pads, no headers | 23 x 17 mm chin pocket |
| E5 | 1 | 5 V buck module, MP1584EN or Mini360 type | 24 V in, 5 V out, feeds the ESP32-C3 5V pin and the radar | Bezel tray |
| E6 | 1 | USB-C PD step-down module, 12 to 24 V in | PD output for the tablet, 15 W or more | Bezel tray |
| E7 | 1 | Right-angle USB-C adapter or short right-angle USB-C cable | Must fit in 6 mm past the tablet edge and turn back into the tray | USB-C notch |
| E8 | 1 | 24 V DC power adapter, 4 A (96 W) | Regulated. Stays under the JAB4's 26 V maximum | |
| E9 | 1 | DC barrel jack pigtail, 5.5 x 2.1 mm female | Body under 11 mm diameter | Rear hole in the spine |
| E10 | 1 | Wondom ICP5 programmer, optional | Only needed to change the JAB4 DSP program in SigmaStudio: crossover, high-pass, limiter | |

## 2. Speakers

| # | Qty | Part | Spec / notes | Used by |
| --- | --- | --- | --- | --- |
| S1 | 2 | Dayton Audio ND65-4, 2-1/2" aluminum full-range, 4 Ω | 52 mm cutout, 64 mm OD, 48 mm deep, 15 W rated. Left and right, each in a sealed 0.58 L chamber | `FR_CUT`, `FR_FLANGE` |
| S2 | 1 | Dayton Audio ND105-4, 4" aluminum midbass, 4 Ω | 93 mm cutout, 105 mm OD, 67 mm deep. Front center | `WF_CUT`, `WF_FLANGE` |
| S3 | 1 | Dayton Audio ND105-PR, 4" passive radiator | 93 mm cutout, 105 mm OD, 67 mm deep, Fs 51.5 Hz. Rear center | `PR_CUT`, `PR_FLANGE` |
| S4 | 16 | Driver mounting screws, M3 x 10 thread-forming or #4 x 1/2" pan head | 4 per driver. Drill pilot holes; the model has none | |
| S5 | 1 roll | Closed-cell foam gasket tape, about 3 mm wide | Seals each driver flange to the baffle | |
| S6 | 1 bag | Polyfill or acoustic wool | Light fill in the full-range chambers, lining in the woofer chamber | |

The woofer and passive radiator face each other front to back. With the listed depths they clear by
about 10 mm.

## 3. Hardware

| # | Qty | Part | Spec / notes | Used by |
| --- | --- | --- | --- | --- |
| H1 | 12 | M3 heat-set inserts | For a 4.0 mm hole, up to 6 mm long. 8 in the bezel front, 4 in the spine | `M3_INSERT`, `INSERT_DEPTH` |
| H2 | 8 | M3 x 25 socket head cap screws | Tray to bezel front. Heads sit in 5 mm counterbores, giving about 4 mm insert engagement | `SCREWS` |
| H3 | 4 | M3 x 8 socket or button head screws | Tray to spine. Heads inside the tray | `SPINE_PTS` |
| H4 | 4 | M3 x 6 thread-forming screws | JAB4 into its 2.6 mm standoff holes | JAB4 standoffs |
| H5 | 6 | 4 mm dowel pins, 6 mm long | Align the lid to the tub for gluing. Holes are 4.3 mm | `BOSSES` |
| H6 | 12 | Neodymium disc magnets, 6 x 2 mm, N52 | One per tub pocket | `MAG_TUB` pockets |
| H7 | 12 | Neodymium disc magnets, 6 x 1 mm, N52 | One per grille ring pocket. Opposite polarity to H6 | `MAG_FRAME` pockets |
| H8 | 4 | Silicone bumper feet, 10 mm diameter, about 3 mm tall | Lift the fabric edge off the counter | 10.5 mm recesses |
| H9 | 1 sheet | Adhesive foam, 1.5 mm | Pads on the six tablet back-stop posts, 8 mm diameter | Tray posts |
| H10 | 1 roll | VHB double-sided tape | Holds the ESP32-C3, buck and PD module in the tray | |

The script comment originally called for 6 x 3 mm magnets split between parts. The pockets total
only 3.2 mm, so a single 6 x 3 mm magnet cannot attract anything on the other side. The 6 x 2 plus
6 x 1 pair fits with 0.2 mm to spare.

## 4. Wiring

| # | Qty | Part | Spec / notes |
| --- | --- | --- | --- |
| W1 | 3 m | Speaker wire, 20 AWG | Three pairs from the JAB4 down the spine channel and through the 12 mm lid hole |
| W2 | 1 m | Power wire, 18 AWG, red and black | 24 V distribution in the tray |
| W3 | 1 m | Silicone hookup wire, 26 to 28 AWG | Radar to ESP32-C3: 5V, GND, TX, RX |
| W4 | 1 set | Molex speaker and power plugs for the JAB4 | Check what ships with your board |
| W5 | | Heat shrink, solder, hot glue | Hot glue seals the full-range wire pass-throughs |

## 5. Printed parts and materials

| # | Qty | Part | Size (mm) | Solid volume |
| --- | --- | --- | --- | --- |
| P1 | 1 | `base_tub.stl` | 300 x 150 x 116 | 851 cm³ |
| P2 | 1 | `lid_spine.stl` | 300 x 150 x 119 | 348 cm³ |
| P3 | 1 | `grille_ring.stl` | 299 x 149 x 112 | 92 cm³ |
| P4 | 1 | `bezel_front.stl` | 276 x 200 x 10 | 121 cm³ |
| P5 | 1 | `bezel_tray.stl` | 276 x 200 x 26 | 190 cm³ |

| # | Qty | Material | Notes |
| --- | --- | --- | --- |
| M1 | 2 kg | PETG, PLA or ASA filament | About 1.6 L of solid volume in total, which is 2 kg of PLA at 100 % infill. Print the tray in PETG or ASA. Avoid carbon or metal-filled filament on the bezel front |
| M2 | 1 piece | Acoustically transparent linen or speaker grille cloth, about 950 x 160 mm | Wraps the grille ring. The perimeter is about 870 mm and the band is 112 mm tall |
| M3 | 1 can | Spray adhesive or thin double-sided tape | Fixes the fabric to the grille ring |
| M4 | 1 tube | Two-part epoxy | Glues the lid to the tub. The seal must be airtight |

## 6. Tools and software

- 3D printer with at least a 300 mm bed axis. A 320 mm or larger bed is recommended.
- Soldering iron with a heat-set insert tip.
- USB-C data cable for flashing the ESP32-C3 and for `adb`.
- Android platform-tools (`adb`) on a computer, to run `android/setup.sh`.
- Home Assistant with the HACS "kiosk-mode" frontend plugin.
- ESPHome 2026.10 or newer. The presence config validates on 2026.10.1.
- On the tablet: Home Assistant companion app, Spotify, YouTube TV and IPTV Smarters, or whatever your dock tiles open.
