# Bill of Materials: Counter Display

Quantities are for one display. Dimensions come from the parameters in
[`enclosure/enclosure.py`](enclosure/enclosure.py). If you substitute a part, update the matching
parameter and regenerate the STLs. Prices are left out because they move too often to keep current.

## 1. Display and electronics

| # | Qty | Part | Spec / notes | Used by |
| --- | --- | --- | --- | --- |
| E1 | 1 | Samsung Galaxy Tab A9+ (11", SM-X210 / X216) | 257.1 x 168.7 x 6.9 mm. Bezel pocket is sized to this | `TAB_*` parameters |
| E2 | 1 | Dayton Audio KABD-430 amplifier board (325-430) | 4 x 30 W from two TPA3118, ADAU1701 DSP, Bluetooth 5.0 aptX HD, 10 to 26 V (24 V typical). Board 91.4 x 68.6 mm, 3.5 mm holes on 83.8 x 61.0 mm. Height 20 mm from the bottom of the PCB, per Dayton's spec sheet. Fed from its AUX input (J13). Run it in 2.1 mode | `AMP_*` parameters, tray standoffs |
| E3 | 1 | ESP32-C3 SuperMini | 22.5 x 18 mm. Runs `esphome/counter-presence.yaml` | `esp32_c3` cradle |
| E4 | 1 | HLK-LD2410C 24 GHz mmWave radar | 22 x 16 mm. Solder wires directly to the pads, no headers | 23 x 17 mm chin pocket |
| E5 | 1 | 5 V buck module, MP1584EN | 22 x 17 mm. 20 V in, 5 V out, feeds the ESP32-C3 5V pin and the radar | `buck_5v` cradle |
| E6 | 1 | USB-C PD step-down module, 12 to 24 V in, USB-C output | Runs from the 20 V bus. 15 W or more. Charges the tablet through the UGREEN adapter's charging port. The cradle is set to 40 x 25 mm; change it to fit your module | `pd_module` cradle |
| E8 | 1 | USB-C PD charger, single port, 65 W or more, GaN | Must list 20 V among its outputs. Single-port, so plugging in another device never cuts the voltage | |
| E8a | 1 | USB-C to USB-C cable, 3 A (60 W) or 5 A (100 W) | Long enough to reach the outlet | |
| E9 | 1 | Adafruit USB Type C Power Delivery Dummy, I2C or Switchable, HUSB238 (product 5991) | 20.32 x 27.81 mm, four 2.5 mm holes, DIP switch set to 20 V, screw terminal output, up to 5 A | `TRIG_*` parameters, `power_plate` sled |
| E9a | 4 | M2.5 x 6 thread-forming screws | PD trigger to the power plate sled | `TRIG_PILOT` |
| E10 | 1 | Dayton Audio KPX (or ICP1) in-circuit programmer, USB | Bench tool, not mounted in the enclosure. It plugs into the KABD-430's 6-pin J5 port only while SigmaStudio loads a DSP program, which the amp keeps after unplugging. J5 is reachable through the open front of the shell before the tablet goes in | J5 programming port |

## 2. Audio path

| # | Qty | Part | Spec / notes | Used by |
| --- | --- | --- | --- | --- |
| A1 | 1 | Flat FPC USB-C extension, male to female, 90°, 5 to 10 cm | Ultra-thin ribbon type. The plug must stick out no more than 4 mm past the tablet's edge. Needs USB 2.0 data (for audio) and 3 A | `USB_CLEAR` channel |
| A2 | 1 | UGREEN 2-in-1 USB-C to 3.5 mm audio adapter with PD charging | Splits the tablet port into a 3.5 mm output and a USB-C charging input. The cradle is set to a 45 x 30 mm body; change it to fit yours | `audio_adapter` cradle |
| A3 | 1 | Dayton KABD functional cable kit, plus a short 3.5 mm stereo cable | The kit's 3.5 mm aux-in jack plugs into J13. The cable runs from the UGREEN audio jack to that jack | |
| A4 | 1 | 3.5 mm ground loop isolator, optional | Only if the speakers hum or pick up charging noise | |

## 3. Speakers

| # | Qty | Part | Spec / notes | Used by |
| --- | --- | --- | --- | --- |
| S1 | 2 | Dayton Audio ND65-4, 2-1/2" aluminum full-range, 4 Ω | 64 mm frame with corner ears, 4.2 mm holes on a 66 mm bolt circle, 52 mm cutout. 48 mm deep, 43 mm behind the mounting face. 1 mm flange; surround 3.1 mm proud of it. Xmax 3.5 mm, 15 W. Left and right, each in a sealed 0.54 L chamber. Solder tabs face up | `DRIVERS["nd65"]` |
| S2 | 1 | Dayton Audio ND105-4, 4" aluminum midbass, 4 Ω | 105 mm frame with ears to 120 mm, 4.2 mm holes on a 108.5 mm bolt circle, 93 mm cutout. 67 mm deep, 57 mm behind the mounting face. Xmax 4 mm, 30 W. Front center | `DRIVERS["nd105"]` |
| S3 | 1 | Dayton Audio ND105-PR, 4" passive radiator | Same frame and bolt circle as the ND105-4, 93 mm cutout. 40.5 mm deep, 30.5 mm behind the mounting face. Fs 51.5 Hz, Vas 2.6 L, Xmax 11 mm. Rear center | `DRIVERS["nd105pr"]` |
| S4 | 16 | M3 x 6 pan head thread-forming screws, or #4 x 1/4" | 4 per driver, through the 4.2 mm frame holes into 6 mm deep, 2.5 mm blind pilots | `PILOT_D`, `PILOT_DEPTH` |
| S5 | 1 roll | Closed-cell foam gasket tape, about 3 mm wide, 1 mm thick when compressed | Seals each driver flange to the baffle. A thicker gasket eats into the excursion clearance | `GASKET_T` |
| S6 | 1 bag | Polyfill or acoustic wool | Light fill in the full-range chambers, lining in the woofer chamber | |

The woofer and passive radiator face each other front to back. With Dayton's depths, the woofer
motor and the back of the radiator clear by about 25 mm.

Dimensions come from Dayton's spec sheets, and the ND65 outline from its STEP/STL model. The ND105
ear shape is inferred from the drawing, so test-fit one driver in the printed tub before gluing the lid.

## 4. Hardware

| # | Qty | Part | Spec / notes | Used by |
| --- | --- | --- | --- | --- |
| H1 | 10 | M3 heat-set inserts | For a 4.0 mm hole, up to 6 mm long. 4 in the chin bar's back face, 4 in the shell's spine-bolt bosses, 2 in the power plate pocket | `M3_INSERT`, `INSERT_DEPTH` |
| H2 | 4 | M3 x 20 socket head cap screws | Chin bar to shell, from the back of the tray | `CHIN_SCREW_X`, `CHIN_SCREW_LEN` |
| H3 | 4 | M3 x 16 socket head cap screws | Bezel to spine, from the spine's rear. The lower pair sits in deep counterbores, so use a long 2.5 mm hex key | `SPINE_PTS`, `SPINE_GRIP` |
| H3a | 2 | M3 x 8 countersunk (flat head) screws | Power plate to spine, flush with the plate | `PWR_SCREW_X` |
| H4 | 4 | M3 x 6 thread-forming screws | KABD-430 into its 2.6 mm standoff pilots, which are about 4.9 mm deep. Longer screws bottom out | Amp standoffs |
| H5 | 6 | 4 mm dowel pins, 6 mm long | Align the lid to the tub for gluing. Holes are 4.3 mm | `BOSSES` |
| H6 | 12 | Neodymium disc magnets, 6 x 2 mm, N52 | One per tub pocket. Sits 0.2 mm below the surface | `MAG_T_TUB` |
| H7 | 12 | Neodymium disc magnets, 6 x 1 mm, N52 | One per grille ring or grille shell pocket, flush. Opposite polarity to H6 | `MAG_T_FRAME` |
| H8 | 4 | Silicone bumper feet, 10 mm diameter, about 3 mm tall | Lift the fabric edge off the counter | 10.5 mm recesses |
| H9 | 1 sheet | Adhesive felt, 0.5 mm | Pads on the six tablet back-stop posts, 8 mm diameter. Thin and slippery, so the tablet slides in | Tray posts |
| H10 | 1 roll | VHB double-sided tape | Holds the PD module, UGREEN adapter, buck and ESP32-C3 in their cradles | `CRADLES` |

## 5. Wiring

| # | Qty | Part | Spec / notes |
| --- | --- | --- | --- |
| W1 | 3 m | Speaker wire, 20 AWG | Three pairs from the KABD-430 down the spine channel and through the 8 mm lid hole into the tub |
| W2 | 1 m | Power wire, 18 AWG, red and black | From the PD trigger up the spine channel, then 20 V distribution in the tray |
| W3 | 1 m | Silicone hookup wire, 26 to 28 AWG | Radar to ESP32-C3: 5V, GND, TX, RX |
| W4 | 1 set | Speaker and power connectors for the KABD-430 | The functional cable kit covers the AUX input; check what else ships with your board |
| W5 | | Heat shrink, solder, hot glue | Hot glue seals the full-range wire pass-throughs and the lid's speaker wire hole |

## 6. Printed parts and materials

| # | Qty | Part | Size (mm) | Solid volume |
| --- | --- | --- | --- | --- |
| P1 | 1 | `base_tub.stl` | 300 x 150 x 116 | 943 cm³ |
| P2 | 1 | `lid_spine.stl` | 300 x 150 x 119 | 344 cm³ |
| P3 | 1 | `grille_ring.stl`, linen version | 299 x 149 x 111 | 81 cm³ |
| P3a | 1 | `grille_shell.stl`, fabric-free version instead of P3, M2 and M3 | 300 x 150 x 112 | 196 cm³ |
| P4 | 1 | `bezel_shell.stl` | 272 x 197 x 36 | 226 cm³ |
| P5 | 1 | `bezel_chin.stl` | 272 x 23 x 9 | 46 cm³ |
| P6 | 1 | `power_plate.stl` | 44 x 26 x 33 | 4.5 cm³ |

| # | Qty | Material | Notes |
| --- | --- | --- | --- |
| M1 | 2 kg | PETG, PLA or ASA filament | About 1.6 L of solid volume in total (1.75 L with the grille shell), which is 2 to 2.2 kg of PLA at 100 % infill. A contrasting color for the grille shell works well. Print the bezel shell in PETG or ASA. Avoid carbon or metal-filled filament on the chin, which the radar looks through |
| M2 | 1 piece | Linen version only. Acoustically transparent linen or speaker grille cloth, about 950 x 160 mm | Wraps the grille ring. The perimeter is about 870 mm and the band is 112 mm tall |
| M3 | 1 can | Linen version only. Spray adhesive or thin double-sided tape | Fixes the fabric to the grille ring |
| M4 | 1 tube | Two-part epoxy | Glues the lid to the tub. The seal must be airtight |

## 7. Tools and software

- 3D printer with at least a 300 mm bed axis. A 320 mm or larger bed is recommended.
- Soldering iron with a heat-set insert tip.
- Calipers, to check the amp height and the adapter sizes before printing.
- USB-C data cable for flashing the ESP32-C3 and for `adb`.
- Android platform-tools (`adb`) on a computer, to run `android/setup.sh`.
- JDK 17 and the Android SDK, to build Counter Home v1.1.0.
- Home Assistant with the HACS "kiosk-mode" frontend plugin.
- ESPHome 2026.10 or newer. The presence config validates on 2026.10.1.
- On the tablet: Home Assistant companion app, Spotify, YouTube TV and IPTV Smarters, or whatever your dock tiles open.
