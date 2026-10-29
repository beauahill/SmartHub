# Bill of Materials: Hub Mini

Quantities are for one Hub Mini. Dimensions come from the parameters in
[`enclosure/enclosure.py`](enclosure/enclosure.py). If you substitute a part, update the matching
parameter and regenerate the STLs. Prices are left out because they move too often to keep current.
Parts marked "same" are identical to the Counter Display on the `main` branch.

## 1. Display and electronics

| # | Qty | Part | Spec / notes | Used by |
| --- | --- | --- | --- | --- |
| E1 | 1 | Samsung Galaxy Tab A9 (8.7", SM-X110 / X115) | 211.0 x 124.7 x 8.0 mm, 1340 x 800. Has a 3.5 mm headphone jack. Measure the corner radius and port positions before printing | `TAB_*`, `USB_*`, `JACK_*` parameters |
| E2 | 1 | Adafruit Mono 2.5 W Class D Audio Amplifier, PAM8302 (product 2130) | 2 to 5.5 V, 2.5 W into 4 Ω at 5 V. Bridge-tied output, onboard gain pot. Fed from the 5 V buck. The cradle is set to 21 x 18 mm; check yours | `amp` cradle |
| E3 | 1 | ESP32-C3 SuperMini | Same. 22.5 x 18 mm. Runs `esphome/mini-presence.yaml` | `esp32_c3` cradle |
| E4 | 1 | HLK-LD2410C 24 GHz mmWave radar | Same. 22 x 16 mm. Solder wires directly to the pads, no headers | 23 x 17 mm chin pocket |
| E5 | 1 | 5 V buck module, MP1584EN | 22 x 17 mm. 20 V in, set to 5.0 V before connecting. Feeds the amp, the ESP32-C3 5V pin and the radar, under 1 A in total | `buck_5v` cradle |
| E6 | 1 | USB-C PD step-down module, 12 to 24 V in, USB-C output | Same type. Runs from the 20 V bus and charges the tablet, which draws up to 15 W. The cradle is set to 40 x 25 mm and the tray clears boards up to 13 mm tall | `pd_module` cradle, `PARTS_H` |
| E8 | 1 | USB-C PD charger, single port, 30 W or more | Must list 20 V among its outputs. The whole unit draws about 20 W at most | |
| E8a | 1 | USB-C to USB-C cable, 3 A | Long enough to reach the outlet | |
| E9 | 1 | Adafruit USB Type C Power Delivery Dummy, I2C or Switchable, HUSB238 (product 5991) | Same. 20.32 x 27.81 mm, four 2.5 mm holes, DIP switch set to 20 V, screw terminal output | `TRIG_*` parameters, `power_plate` sled |
| E9a | 4 | M2.5 x 6 thread-forming screws | Same. PD trigger to the power plate sled | `TRIG_PILOT` |

## 2. Audio path

| # | Qty | Part | Spec / notes | Used by |
| --- | --- | --- | --- | --- |
| A1 | 1 | Flat FPC USB-C extension, male to female, 90°, 5 to 10 cm | Same. Ultra-thin ribbon type, 3 A. The plug must stick out no more than 4 mm past the tablet's edge. Here it only charges | `USB_CLEAR` channel |
| A2 | 1 | 3.5 mm stereo cable with a slim 90° 3-pole TRS plug | The plug must stick out no more than 7 mm past the tablet's edge. Not a 4-pole TRRS headset plug. Cut about 25 cm from the plug and solder to the amp | `JACK_CLEAR` channel |
| A3 | 2 | 1 kΩ resistors, 1/4 W | Sum left and right into the amp's A+ input | |
| A4 | 1 | 3.5 mm ground loop isolator, optional | Only if the speaker hums or picks up charging noise. Needs a second short 3.5 mm cable | |

## 3. Speaker

| # | Qty | Part | Spec / notes | Used by |
| --- | --- | --- | --- | --- |
| S1 | 1 | Dayton Audio ND65-4, 2-1/2" aluminum full-range, 4 Ω | Same driver as the Counter Display's full-range pair. 64 mm frame with corner ears, 4.2 mm holes on a 66 mm bolt circle, 52 mm cutout, 43 mm behind the mounting face. Solder tabs face up | `DRIVERS["nd65"]` |
| S4 | 4 | M3 x 6 pan head thread-forming screws, or #4 x 1/4" | Through the frame holes into 6 mm deep, 2.5 mm blind pilots | `PILOT_D`, `PILOT_DEPTH` |
| S5 | 1 short length | Closed-cell foam gasket tape, about 3 mm wide, 1 mm thick when compressed | Seals the driver flange to the baffle | `GASKET_T` |
| S6 | 1 handful | Polyfill or acoustic wool | Loose fill in the 0.98 L box | |

## 4. Hardware

| # | Qty | Part | Spec / notes | Used by |
| --- | --- | --- | --- | --- |
| H1 | 9 | M3 heat-set inserts | For a 4.0 mm hole, up to 6 mm long. 3 in the shell's chin bosses, 4 in the shell's spine-bolt bosses, 2 in the power plate pocket | `M3_INSERT`, `INSERT_DEPTH` |
| H2 | 3 | M3 x 12 socket head cap screws | Chin to shell, from underneath | `CHIN_SCREW_X` |
| H3 | 4 | M3 x 16 socket head cap screws | Bezel to spine, from the spine's rear. The lower pair sits in deep counterbores, so use a long 2.5 mm hex key | `SPINE_PTS`, `SPINE_GRIP` |
| H3a | 2 | M3 x 8 countersunk (flat head) screws | Power plate to spine, flush with the plate | `PWR_SCREW_X` |
| H5 | 4 | 4 mm dowel pins, 6 mm long | Align the lid to the tub for gluing. Holes are 4.3 mm | `DOWELS` |
| H6 | 8 | Neodymium disc magnets, 6 x 2 mm, N52 | One per tub pocket: four on the rear, two on each side. Sits 0.2 mm below the surface | `MAG_REAR`, `MAG_SIDE` |
| H7 | 8 | Neodymium disc magnets, 6 x 1 mm, N52 | One per grille shell pocket, flush. Opposite polarity to H6 | `MAG_T_FRAME` |
| H8 | 4 | Silicone bumper feet, 10 mm diameter, about 3 mm tall | Lift the shell's edge off the furniture | `FEET` |
| H9 | 1 small sheet | Adhesive felt, 0.5 mm | Pads on the six tablet back-stop posts, 8 mm diameter | Tray posts |
| H10 | 1 roll | VHB double-sided tape | Holds the PD module, buck, amp and ESP32-C3 in their cradles | `CRADLES` |

## 5. Wiring

| # | Qty | Part | Spec / notes |
| --- | --- | --- | --- |
| W1 | 0.5 m | Speaker wire, 20 AWG | One pair from the amp down the spine channel and through the 6 mm lid hole |
| W2 | 0.5 m | Power wire, 18 AWG, red and black | From the PD trigger up the spine channel, then 20 V to the PD module and buck |
| W3 | 1 m | Silicone hookup wire, 26 to 28 AWG | 5 V distribution, radar to ESP32-C3 (5V, GND, TX, RX), audio to the amp |
| W5 | | Heat shrink, solder, hot glue | Hot glue seals the speaker wire hole in the lid |

## 6. Printed parts and materials

| # | Qty | Part | Size (mm) | Solid volume |
| --- | --- | --- | --- | --- |
| P1 | 1 | `base_tub.stl` | 170 x 110 x 76 | 275 cm³ |
| P2 | 1 | `lid_spine.stl` | 170 x 110 x 102 | 207 cm³ |
| P3 | 1 | `grille_shell.stl` | 170 x 110 x 73 | 99 cm³ |
| P4 | 1 | `bezel_shell.stl` | 232 x 136 x 27 | 136 cm³ |
| P5 | 1 | `bezel_chin.stl` | 232 x 21 x 27 | 65 cm³ |
| P6 | 1 | `power_plate.stl` | 44 x 26 x 33 | 4.5 cm³ |

| # | Qty | Material | Notes |
| --- | --- | --- | --- |
| M1 | 1 kg | PETG, PLA or ASA filament | About 0.79 L of solid volume in total, which is just under 1 kg of PLA at 100 % infill. A contrasting color for the grille shell works well. Print the bezel shell in PETG or ASA. Avoid carbon or metal-filled filament on the chin, which the radar looks through |
| M4 | 1 tube | Two-part epoxy | Glues the lid to the tub. The seal must be airtight |

## 7. Tools and software

- 3D printer with at least a 235 mm bed axis. A 256 mm bed is comfortable.
- Soldering iron with a heat-set insert tip.
- Calipers, to check the tablet, plug and board sizes before printing.
- Multimeter, to set the buck to 5.0 V and check 20 V at the PD trigger.
- USB-C data cable for flashing the ESP32-C3 and for `adb`.
- Android platform-tools (`adb`) on a computer, to run `android/setup.sh`.
- JDK 17 and the Android SDK, to build Counter Home v1.2.0.
- Home Assistant with the HACS "kiosk-mode" frontend plugin.
- ESPHome 2026.10 or newer.
- On the tablet: Home Assistant companion app, Spotify, YouTube TV and IPTV Smarters, or whatever your dock tiles open.
