# Wiring: TI-83 Plus SE link port <-> Waveshare ESP32-S3-Zero

Decision taken for this project: **one BSS138 level shifter per line** (your spec offered a resistor divider; the reasons it is not the
default are below, and the resistor variant is documented so you can still try it after measuring).

## Pin map

| Calculator (2.5 mm plug) | ESP32-S3-Zero | Role |
|---|---|---|
| Tip (D0, red wire) | GPIO1 (RTC) | data line 0 + deep-sleep wake (`ext0`, LOW) |
| Ring (D1, white wire) | GPIO2 (RTC) | data line 1 |
| Sleeve (GND) | GND | common reference |
| 4xAAA + (only when mounted inside) | 5V pin | power; during bench tests power the ESP32 from USB-C |

## Recommended: BSS138 bidirectional shifter (x2)

```
 calculator VCC-side pull-up line ----[HV1 ] BSS138 [LV1]---- GPIO1   (3V3 pull-up on the LV side)
 calculator ring line            ----[HV2 ] BSS138 [LV2]---- GPIO2   (3V3 pull-up on the LV side)
 GND ---------------------------------------------------------- GND
 HV reference = the voltage the calculator pulls its link lines up to (measure it, 4.5-6 V)   LV reference = 3V3
```
Why: the lines are open-drain in both directions. A shifter keeps them open-drain, lets the calculator and the ESP32 each pull low,
and never presents more than 3.3 V to the ESP32 pins.

## The resistor variant from the spec (1 kOhm series + 2.2 kOhm to GND) - risks to check first

* The 2.2 kOhm to GND is a permanent load on a line that the calculator only pulls up weakly. If the calculator's pull-up is, say, 10 kOhm,
  the idle level becomes `Vcc * 3.2k / (10k + 3.2k)` ~ 1.2-1.5 V: too low for the ESP32 to read as "high" and the handshake fails.
  Measure the idle voltage of tip and ring with the ESP32 connected before trusting it.
* With 5 V on the line the divider gives ~3.5 V at the pin: above the 3.3 V rail, close to the absolute maximum (3.6 V).
* If you try it anyway: use the 1 kOhm series resistor only (current limiting through the ESP32 clamp diodes) and keep the line load light;
  expect it to work only if the calculator's pull-ups are strong enough.

## Power from the AAA cells (mounted inside)

* Four fresh alkaline cells measure up to ~6.4 V. Check the 5V-pin regulator limit of your board revision before connecting; add a
  Schottky diode or a small LDO if the datasheet maximum is below that.
* "~8 uA in deep sleep" is the chip-level figure. The board's regulator quiescent current and the RGB LED usually add tens of uA:
  measure the real total with the board on its battery supply (the firmware does not drive the LED).
* Treat the calculator battery as the ESP32's battery too: expect the Wi-Fi bursts (80-250 mA) to sag alkaline cells; NiMH or Li handle it better.
