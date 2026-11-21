# Programming the KABD-430 amp

The KABD-430's factory program has no crossover for this build. The bridged J12 channel plays
whatever the DSP sends it, so the woofer gets vocals and the 2.5" ND65s get deep bass they can't
handle. This guide loads a 2.1 program instead. It does four things:

- a 150 Hz crossover between the ND65s and the woofer
- a subsonic filter that stops the woofer and passive radiator over-travelling below the box tuning
- a level match between the two
- limiters, because a phone on Bluetooth bypasses the tablet's volume cap (a second pass; the
  crossover works without them)

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

## 1. Edit Dayton's example, with the amp unplugged

Dayton's `Simple 2.1 Project` already has the right shape: inputs, a stereo path to J11 and a mono
path to J12, each with its own Parametric EQ. You don't build a new chain. You change five things in
the one that's there.

Do this with the KPX's 6-pin cable out of J5. Dayton warns that pressing **Add Filter** in a
Parametric EQ block while a board is connected makes loud, awful noises.

1. Open SigmaStudio, then `File → Open` → `KABD-430/Simple 2.1 Project.dspproj`. Straight away,
   `File → Save As` → `counter-2.1.dspproj`, so the example stays untouched.
2. Leave the **Register Control** tab exactly as the example has it. It sets up the Bluetooth I2S
   input and the POT ports, and a project without it plays no Bluetooth audio.
3. Leave the **Hardware Configuration** tab alone too. It shows a USB block wired to the ADAU1701
   at I2C 0x68 and the E2Prom at 0xA0, which is correct for this board.

### What's in the example, and what to change

Read the Schematic tab left to right:

| Block in the example | What it does | Change |
| --- | --- | --- |
| **Input**, then **Left Channel** and **Right Channel** (red-cross Signal Add blocks) | Mixes AUX (channels 0 and 1) with Bluetooth (4 and 5): left = 0 + 4, right = 1 + 5 | Keep |
| **POT4** → **Master Volume** (SW slew) | Master volume from a pot on AUX_ADC_0 | **Change 1:** replace with a fixed volume |
| **Left Split**, **Right Split** | Feed both the J11 and the J12 paths | Keep |
| **J11 PEQ** → DAC0, DAC1 | EQ for J11, the ND65s in stereo | **Change 3:** add the high-pass |
| **POT3** → **J12 Bridged Volume** (SW slew) | Woofer volume from a pot on AUX_ADC_1 | **Change 1:** replace with a fixed volume |
| **Stereo to Mono Mixer** | Sums L and R for the woofer | **Change 2:** set to −6 dB |
| **J12 PEQ** | EQ for J12, the woofer, bridged | **Change 4:** add the low-pass and subsonic filter |
| **Delay** → DAC2 | Time alignment, set to 1 sample (0.0208 ms) | Keep as it is |
| **I2S Output** (DIG0, DIG1) | For cascading a second board | Keep |

**Change 1: remove the pot volumes.** This build has nothing plugged into POT1 to POT4, so a volume
block driven by an empty pot input is unpredictable: silent, or full blast. Delete **POT4** and
**Master Volume**. Drag in a plain volume block (in the classic toolbox, usually **Volume Controls →
Adjustable Gain → No Slew → Single**). Right-click it → **Add Algorithm** (or **Grow Algorithm**)
so it has two inputs and two outputs. Wire the Left and Right T blocks into it, and its outputs to
Left Split and Right Split. SigmaStudio names it **Single 1**; leave it at **0 dB**.

Do the same for **POT3** and **J12 Bridged Volume**: a two-channel volume block between the splits
and the mixer. SigmaStudio names it **Single 2**. This is the **woofer level**. Start it at
**0 dB**; the model puts the two halves within about 1 dB of each other there. Step 4 tunes it by ear.

**Change 2: the mixer.** Set the **Stereo to Mono Mixer** to **−6 dB**. Adding left and right
doubles a mono signal, and this halves it back.

**Changes 3 and 4: the filters.** Click the blue square in each PEQ block. Use **Add Filter** until
you have the rows below. In each row, set **Type**, **Frequency1** and **Q Factor**; leave SubType,
Boost, Gain, View and Bypass at their defaults.

| PEQ | Rows | Result |
| --- | --- | --- |
| **J11 PEQ** | 2 × **General High Pass**, **150 Hz**, Q **0.71** | A 24 dB/oct Linkwitz-Riley high-pass. The curve is flat above about 300 Hz and falls steeply below 150 Hz |
| **J12 PEQ** | 2 × **General Low pass**, **150 Hz**, Q **0.71**, and 2 × **General High Pass**, **45 Hz**, Q **0.71** (55 Hz if the radiator's disk is ever removed) | The matching low-pass, plus a 24 dB/oct subsonic filter. The curve is a hill that peaks about 2 dB below zero near 80 Hz and is down about 28 dB at 20 Hz |

The woofer's hill tops out about 2 dB low because its 45 Hz and 150 Hz filters are close enough to
each take a little off the middle. The woofer level in step 4 makes up for it. One stacked pair is
the minimum: a single 12 dB/oct row is not enough for either filter.

**Change 5: a polarity switch.** Drag in a **Signal Invert** block (Basic DSP in the toolbox) and
put it between **J12 PEQ** and **Delay**. SigmaStudio names it **Inv1**. Leave it unchecked; step 4
checks it.

The Delay block shows **Max 5** milliseconds while you edit. After a compile it may grey out and
show **240**: that's the same 5 ms, counted in samples at 48 kHz. Don't change it.

### The finished chain

```
Input 0+4 ─┐            ┌─ Left Split ── J11 PEQ (HP 150 Hz) ── DAC0 ┐ J11 stereo
Input 1+5 ─┴─ Single 1 ─┤  Right Split ─        "          ──── DAC1 ┘ ND65 pair
             (0 dB)     └─ both splits ─ Single 2 ─ Mixer −6 dB ─ J12 PEQ ─ Inv1 ─ Delay ─ DAC2   J12 bridged
                                         (woofer)                (LP 150, HP 45)
```

Check the three output boxes before you download: **DAC0** and **DAC1** for J11, **DAC2** for J12.
Dayton's guide says a bridged J12 takes DAC2, so DAC3 stays unused. On a high-DPI screen the boxes
can show only "DAC" with the number cut off; click the arrow to see which one is ticked. Save.

### Limiters, for a second pass

Step 5's limiters protect the drivers when a phone on Bluetooth plays at full volume. The rest of the
guide works without them, so you can get the crossover sounding right first and add them later:

- **Limiter A** (stereo, linked) between **J11 PEQ** and DAC0/DAC1, and **Limiter B** between
  **Delay** and DAC2. Use a compressor or limiter from the toolbox's Dynamics Processors section.
  The block names differ between SigmaStudio versions, so pick an RMS type you can set as a
  limiter: a high ratio, about 10:1 or more above the threshold. Leave attack and release at their
  defaults, and the thresholds at 0 dB, which does nothing until step 5.
- **Test tone for step 5.** Add a **Sine Tone** source, followed by a Single Volume set to
  **−20 dB**. Split it with a T block. Put a stereo **Switch** (multiplexer) in front of Limiter A
  and a mono Switch in front of Limiter B, so each limiter takes either the music or the tone. Leave
  both Switches on music.

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
3. **Woofer polarity.** Play something with a steady bass line and male vocals. Tick **Inv1**,
   then untick it, while it plays. While SigmaStudio is linked to the amp, checkboxes and sliders
   change the sound live, without another download. One setting sounds clearly thinner around the upper bass. The
   model predicts a hole about 15 dB deep near 140 Hz when the polarity is wrong. Keep the fuller setting.
4. **Woofer level.** Adjust **Single 2**, the woofer level, in 1 dB steps, standing where you normally hear the
   display. A counter against a wall adds bass, so 1 to 3 dB below 0 is a likely result. Change one
   thing at a time, and `File → Save` as you go.

## 5. Set the limiters

Add the limiters and test tone first (see
[Limiters, for a second pass](#limiters-for-a-second-pass)), then Link Compile Download.

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
