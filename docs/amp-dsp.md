# Programming the KABD-430 amp

The KABD-430's factory program has no crossover for this build. The bridged J12 channel plays
whatever the DSP sends it, so the woofer gets vocals and the 2.5" ND65s get deep bass they can't
handle. This guide loads a 2.1 program instead. It does four things:

- a 150 Hz crossover between the ND65s and the woofer
- a subsonic filter that stops the woofer and passive radiator over-travelling below the box tuning
- a level match between the two
- limiters, because a phone on Bluetooth bypasses the tablet's volume cap

The amp keeps the program in its EEPROM after the programmer is unplugged.

You tune it by ear. The filter values come from the drivers' published parameters and the
enclosure volumes, through a model rather than a measurement (see
[Where the numbers come from](#where-the-numbers-come-from)). They should be close before you
touch anything.

## What you need

- A Windows PC. SigmaStudio is Windows-only.
- [SigmaStudio](https://www.analog.com/sigmastudio), the free download from Analog Devices. Get
  SigmaStudio, not SigmaStudio+: the ADAU1701 on this board belongs to the classic version. The
  installer also installs the USBi driver, so don't install one by hand.
- The Dayton KPX programmer (BOM E10), its 6-pin cable, and a USB-C data cable. Charging-only cables
  are the most common cause of a failed connection, so if the PC doesn't see the KPX, try another cable.
- Dayton's KABD SigmaStudio example projects pack
  ([zip](https://www.parts-express.com/pedocs/more-info/dayton-audio-kabd-sigmastudio-example-projects-pack-v1.zip),
  also linked from the KABD-430 product page). Unzip it on the PC. Its `KABD-430` folder holds
  `Simple 2.1 Project.dspproj`, which you start from. It also holds the original firmware project
  that you restore from; Dayton's manual says it's in the pack, but not under what name.
- A multimeter with an AC volts range, to set the limiters.
- A phone, to play test tracks over the amp's Bluetooth ("DAKAB").

## The radiator's weight disk sets the subsonic filter

This build has the ND105-PR's 21.8 g weight disk fitted on the rod at the back of its cone. The
disk sets the box tuning, and the woofer's subsonic filter has to match it:

| Passive radiator | Box tuning | Box output at 50 Hz, relative to 125 Hz | Woofer subsonic filter |
| --- | --- | --- | --- |
| **Disk fitted (this build)** | about 46 Hz | about −9 dB | **45 Hz** |
| No disk | about 74 Hz | about −28 dB | 55 Hz |

If the disk ever comes off, change the subsonic filter to 55 Hz. Without the disk, a 45 Hz filter
lets the radiator over-travel.

## 1. Build the program, with the amp unplugged

Do this part with the amp disconnected. Dayton warns that pressing **Add Filter** in a Parametric
EQ block while a board is connected makes loud, awful noises.

1. Open SigmaStudio, then `File → Open` → `KABD-430/Simple 2.1 Project.dspproj`. Straight away,
   `File → Save As` → `counter-2.1.dspproj`, so the example stays untouched.
2. Leave the **Register Control** tab exactly as the example has it. It sets up the Bluetooth I2S
   input and the POT ports, and a project without it plays no Bluetooth audio.

### What to keep and what to remove

I haven't opened Dayton's example, so this describes where you want to end up, not the exact
blocks in the file:

- **Inputs.** The Input block feeds two Signal Add blocks. AUX comes in on channels **0 and 1** and
  Bluetooth on **4 and 5**, so you want left = 0 + 4 and right = 1 + 5. Both sources then play
  without switching, the same as the factory program. Dayton's examples are built this way.
- **Remove anything controlled by a pot.** That means any block whose orange control pin is wired
  to an `AUX_ADC` source. Dayton's description of its 2.1 examples mentions a pot for master volume
  and another for the woofer. This build has nothing plugged into POT1 to POT4, so replace those
  with the fixed blocks below.
- **Remove bass enhancement.** Disable or delete any Super Bass or Dynamic Bass block. The box
  doesn't have the excursion headroom for bass boost.

### Signal chain

```
Input 0+4 ─┐                      ┌─ High L ── Limiter A ── DAC0 ┐ J11 stereo
Input 1+5 ─┴─ Crossover (stereo) ─┤  High R ── Limiter A ── DAC1 ┘ ND65 pair
             LR 24 dB/oct, 150 Hz └─ Low L + Low R ─ −6 dB ─ Subsonic HP ─ Woofer level ─ Invert ─ Limiter B ─ DAC2   J12 bridged
```

| Block (SigmaStudio toolbox) | Setting |
| --- | --- |
| **Crossover**, 2-way. Right-click → Add Algorithm to make it stereo | Linkwitz-Riley, 24 dB/oct, **150 Hz**. Its High outputs feed the ND65s and its Low outputs feed the woofer |
| **Signal Add** | Low L + Low R, a mono sum for the woofer |
| **Single Volume** (no slew) | **−6 dB**. This halves the sum, so a mono signal comes out at the same level as either channel |
| **Parametric EQ** (or two General 2nd Order filters) | Two **2nd-order Butterworth high-pass** bands, both at **45 Hz** (55 Hz if the radiator's disk is ever removed). Stacked, they make a 24 dB/oct Linkwitz-Riley subsonic filter. A single 12 dB/oct band is not enough |
| **Single Volume** (no slew), "woofer level" | Start at **0 dB**. The model puts the two halves within about 1 dB of each other there. Tune it by ear in step 4 |
| **Signal Invert** | Unchecked. Step 4 checks this |
| **Limiter A** (stereo, linked) and **Limiter B** | Put them in now with their thresholds at 0 dB, which does nothing yet. Step 5 sets them |
| **Output** | DAC0 and DAC1 to J11, which is in stereo mode for the ND65s. DAC2 to J12, which is bridged for the woofer. Dayton's guide says a bridged J12 takes DAC2, so leave DAC3 unconnected |

For the limiters, use a compressor or limiter from the toolbox's Dynamics Processors section. The
block names differ between SigmaStudio versions, so pick an RMS type you can set as a limiter: a
high ratio, about 10:1 or more above the threshold. Leave attack and release at their defaults.

**Test tone for step 5.** Add a **Sine Tone** source, followed by a Single Volume set to **−20 dB**.
Split it with a T block. Put a stereo **Switch** (multiplexer) in front of Limiter A and a mono
Switch in front of Limiter B, so each limiter takes either the music or the tone. Leave both
Switches on music.

To see the curve before you hear it, put a Stimulus at the input and a Probe on each output, then
press Stimulus. You should see the ND65 output rolling off below 150 Hz, and the woofer output
passing roughly 45 to 150 Hz. Save.

## 2. Get the display ready

1. Take the tablet out of the bezel shell. J5, the 6-pin programming port, is only reachable
   through the open front of the shell.
2. Plug in the wall charger. **The amp must have its own power while programming.** The KPX lights
   the amp's LEDs over USB, so it looks powered even when it isn't, but programming will fail.
3. Turn the source volume down. The first download switches programs mid-signal.

## 3. Connect, in this order

Dayton's manual is firm about the order. If you plug the KPX into the amp before the PC, you get
"Communication failure".

1. On the back of the KPX, set the two switches to **USBi** and **IIC** (I2C). The KABD-430's
   ADAU1701 is programmed over I2C through the 6-pin port. UART goes with the KPX's 4-pin port,
   which is for Dayton's KAB amps and the KABX software, not this board.
2. Plug the USB-C cable into the PC, then into the KPX. In SigmaStudio's Hardware Configuration tab,
   the **USB** block turns green. Green means only that the PC sees the KPX; it hasn't reached the
   amp yet.
   - Still orange: unplug everything from the KPX, plug in USB alone, and try another cable or port.
     If that fails, reinstall SigmaStudio.
3. Only now, plug the KPX's **6-pin** port into J5 on the amp. Leave the KPX's 4-pin port empty;
   it's for a different series of Dayton amps.

## 4. Download and check by ear

Press **Link Compile Download**. The status bar shows "Active: Downloaded" and the new program
plays right away. It is only in RAM for now, so a power cut brings the factory program back.

Pair a phone with "DAKAB" and play at moderate volume:

1. **Left and right.** Play a left/right channel test track. If the left channel comes out of the
   right ND65 (right as you face the display), swap the DAC0 and DAC1 wires in SigmaStudio. Don't
   rewire the harness.
2. **Each driver plays its band.** Put your ear to each driver. The woofer should carry bass with
   no intelligible voice. The ND65s should carry the voice with no deep bass. A slow sine sweep from
   20 Hz to 500 Hz makes this easy to hear: the woofer takes over below about 150 Hz and goes quiet
   below the subsonic filter.
3. **Woofer polarity.** Play something with a steady bass line and male vocals. Tick Signal Invert,
   then untick it, while it plays. One setting sounds clearly thinner around the upper bass. The
   model predicts a hole about 15 dB deep near 140 Hz when the polarity is wrong. Keep the fuller setting.
4. **Woofer level.** Adjust "woofer level" in 1 dB steps, standing where you normally hear the
   display. A counter against a wall adds bass, so 1 to 3 dB below 0 is a likely result. Change one
   thing at a time, and `File → Save` as you go.

## 5. Set the limiters

The tablet caps its media volume at 80 % (Counter Home's `Volume.kt`), but a phone on Bluetooth
bypasses that cap and can drive the DSP to full scale. Dayton rates the board at 2 x 30 W plus
1 x 60 W in 2.1 mode (at 24 V). That's well over the woofer's roughly 20 W excursion budget and
twice the ND65s' 15 W rating. Dayton doesn't publish what full scale is in volts, so measure it at
the limiter inputs.

Do this after step 4, because the woofer level you chose changes what reaches the limiter.

1. Set both Switches to the tone. Set the tone to **400 Hz** for the ND65s, then Link Compile
   Download.
2. Read the AC volts across the left ND65's terminals (J11 pins 5 and 6). Call it `V11`. Then set
   the tone to **80 Hz** and read across the woofer (J12 MONO+ to MONO−). Call it `V12`. The tones
   are loud but brief. Most meters read accurately from 40 to 400 Hz.
3. The tone is 20 dB below full scale, so full scale at each output is ten times the reading. Work
   out the thresholds:
   - ND65s, at 15 W into 4 Ω, which is 7.7 V rms: `threshold = 20·log10(7.7 / (10·V11))` dB
   - Woofer, at 20 W into 4 Ω, which is 8.9 V rms (the excursion limit, not the 30 W thermal
     rating): `threshold = 20·log10(8.9 / (10·V12))` dB
   - If a threshold comes out at 0 dB or above, the amp can't reach that limit and that limiter can
     stay at 0 dB.
4. Enter the thresholds in Limiter A and Limiter B.
5. **Check it.** Raise the tone's volume block from −20 dB to **0 dB**, so the tone hits each limiter
   at full scale. Re-read each output: it should settle at or just under 7.7 V (ND65) and 8.9 V
   (woofer). If it reads higher, lower that threshold until it doesn't. This also catches any
   difference in how your SigmaStudio version scales the tone or the threshold.
6. Set both Switches back to music and the tone volume back to −20 dB.

## 6. Burn to EEPROM

1. After your last tweak, press **Link Compile Download** once more. The burn writes the last
   compilation, so this makes sure it includes the woofer level, the polarity, the limiter
   thresholds and the Switches set to music.
2. In Hardware Configuration, right-click the **ADAU1701** block → **Write Latest Compilation to
   E2PROM**. Accept the default settings in the dialog → OK. If it fails, check the KPX is still on
   USBi and IIC.
3. Unplug the KPX from J5. Unplug the wall charger, wait a few seconds, plug it back in, then check:
   - music plays, not the test tone
   - the woofer carries only bass (check 2 from step 4)
   - the woofer level sounds as you set it

   If the woofer plays full range again, the burn didn't take.
4. Copy `counter-2.1.dspproj` into this repo (for example `amp/counter-2.1.dspproj`), so the
   program you burned is versioned with the build.

Burning replaces Dayton's stock program, including its default pot functions, which this build
doesn't use. To go back, burn the original firmware project from the pack the same way.

## Where the numbers come from

The values come from a lumped model, not a measurement. Inputs:

- **Drivers.** Dayton's published parameters:
  - ND65-4: Fs 89.5 Hz, Qts 0.61, Vas 0.53 L, Xmax 3.5 mm
  - ND105-4: Fs 78.7 Hz, Qts 0.61, Vas 1.97 L, Xmax 4 mm
  - ND105-PR: Fs 51.5 Hz, Mms 13.9 g, Vas 2.6 L, Xmax 6 mm
- **Enclosure.** The chamber volumes `enclosure.py` prints, less an estimate for the drivers:
  about 0.50 L net per ND65 chamber and 2.45 L for the woofer chamber.

Results:

- **ND65s.** In 0.50 L sealed, they roll off below about 128 Hz (Qtc about 0.87). Unfiltered at
  10 W, they would reach 4.8 mm, over their 3.5 mm Xmax. With the 150 Hz high-pass they peak at
  about 1.5 mm.
- **Crossover.** Of the options modelled, LR 24 dB/oct at 150 Hz on both sides, with the woofer
  in normal polarity at the same voltage, summed flattest: within about 1 dB from 100 Hz to 1 kHz.
  A gentler 12 dB/oct high-pass that leans on the ND65s' natural roll-off left a dip around 100 to
  150 Hz.
- **Subsonic filter.** It keeps both woofer and radiator inside Xmax at 20 W. With the disk and a
  45 Hz LR4 filter, the woofer peaks at 3.6 mm and the radiator at 5.2 mm. Without the disk and a
  55 Hz filter, they peak at 3.1 mm and 5.4 mm. Without any filter, the radiator reaches 13 mm with
  the disk fitted. The margins are thin, which is why Limiter B holds the woofer to 20 W.
- **Woofer level.** The two ND65s together, in their passband, and the woofer system both make
  about 88 dB at 2.83 V. That is why the woofer level starts at 0 dB after the −6 dB sum.

Sources: [KABD-430 manual](https://www.daytonaudio.com/images/resources/325-430--dayton-audio-kabd-430-manual.pdf),
[SigmaStudio guide for the KABD series](https://daytonaudio.com/images/resources/sigmastudio-programming-for-the-dayton-audio-kabd-series-of-amplifiers-v1.pdf),
[KPX manual](https://daytonaudio.com/images/resources/325-139--dayton-audio-kpx-programmer-user-manual-v3.pdf),
[ND65-4](https://www.daytonaudio.com/product/63/nd65-4-2-1-2-aluminum-cone-full-range-driver-4-ohm),
[ND105-4](https://www.daytonaudio.com/product/55/nd105-4-4-aluminum-cone-midbass-driver-4-ohm),
[ND105-PR](https://www.daytonaudio.com/product/1554/nd105-pr-4-aluminum-cone-passive-radiator).
