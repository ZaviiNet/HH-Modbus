# Waveshare USB to RS485 Adapter — Setup Guide

The **Waveshare USB to RS485 Industrial Converter** is a plug-and-play serial adapter that lets you connect a Home Assistant host directly to an inverter's RS485 port using a standard USB-A cable.  It uses an original **FTDI FT232RL** chip, which has first-class driver support in Linux and Home Assistant OS — no manual driver installation is required.

> This adapter is used with the **Serial (RS485)** connection type in HH Modbus Control.  
> If you want a wireless/Ethernet connection instead, use the [Waveshare RS485-to-TCP gateway](https://www.waveshare.com/wiki/RS485_TO_ETH) and choose **TCP** as the connection type.

---

## Hardware Specifications

| Property | Value |
|---|---|
| Chip | FTDI FT232RL |
| Product type | Industrial converter |
| Baud rate range | 300 – 921 600 bps |
| Host connector | USB-A |
| Device connector | Screw terminal (A+, B−, GND) |
| USB operating voltage | 5 V |
| USB protection | 200 mA self-recovery fuse + ESD |
| USB transmission distance | ≈ 5 m |
| RS485 transmission distance | ≈ 1 200 m at low baud rate |
| RS485 protection | 600 W lightning-proof surge suppression, 15 kV ESD (TVS diode) |
| RS485 onboard resistor | 120 Ω balance resistor |
| Direction control | Hardware automatic (no software flow-control needed) |
| Nodes | Point-to-multipoint, up to 32 nodes (use repeaters for 16+) |
| Operating temperature | −15 °C to 70 °C |
| Humidity | 5 %RH – 95 %RH |
| Supported OS | Linux, macOS, Android, Windows XP/7/8/8.1/10, WinCE |

### LED Indicators

| LED | Colour | Meaning |
|---|---|---|
| PWR | Red | USB power detected |
| TXD | Red | Data being sent from host to inverter |
| RXD | Red | Data being received from the inverter |

---

## Wiring to the Inverter

### General RS485 Connections

Connect the adapter's screw terminals to the inverter's RS485 port:

| Adapter terminal | Inverter RS485 terminal |
|---|---|
| **A+** | RS485_A (or A+, DATA+) |
| **B−** | RS485_B (or B−, DATA−) |
| **GND** | GND *(if available — recommended for noise reduction)* |

Keep the RS485 cable as short as practical. For long runs (> 10 m) use twisted-pair cable (e.g. CAT5e with one pair for A/B and a second pair for GND).

### Inverter-Specific Pinouts

#### Solis Inverters

Solis inverters expose RS485 on the COM port of the main connector. Consult your inverter's installation manual for the exact pin location. The A/B labels are printed on the terminal block.

#### Skyline / Duracell G3 Inverters

Use the **Common Use** RS485 port (not the Meter port):

| Inverter pin | Adapter terminal |
|---|---|
| Pin 7 — RS485_A2 (Common Use) | **A+** |
| Pin 9 — RS485_B2 (Common Use) | **B−** |

See the [Skyline / Duracell G3 setup guide](skyline.md#wiring) for the full 10-pin terminal block diagram.

#### GivEnergy Inverters

GivEnergy Gen 3 inverters expose an RS485 header inside the unit. Refer to your inverter documentation for the exact connector. Use **A+** and **B−** terminals on the adapter.

---

## Home Assistant Setup

### Step 1 — Identify the serial port

After plugging in the adapter, identify the port it was assigned.

**Home Assistant OS (Supervisor):**

1. Go to **Settings → System → Hardware**.
2. Click the three-dot menu → **All Hardware**.
3. Look for a device with `FT232R` or `FTDI` in its description — the serial port will be `/dev/ttyUSB0`, `/dev/ttyUSB1`, etc.

**SSH / Terminal:**

```bash
ls -la /dev/ttyUSB*
# or
dmesg | grep -i "ttyUSB\|FT232\|FTDI"
```

The adapter will typically appear as `/dev/ttyUSB0` if it is the only USB serial device attached.

### Step 2 — Configure HH Modbus Control

1. Go to **Settings → Devices & Services → Add Integration → HH Modbus Control**.
2. Select your inverter brand.
3. When prompted for connection type, choose **Serial (RS485)**.
4. Fill in:

   | Field | Value |
   |---|---|
   | Serial Port | `/dev/ttyUSB0` (or whichever port was identified above) |
   | Baud Rate | `9600` (Solis default) — see table below for other brands |
   | Byte Size | `8` |
   | Parity | `N` (None) |
   | Stop Bits | `1` |

### Baud Rate by Brand

| Brand | Default Baud Rate | Notes |
|---|---|---|
| Solis | 9 600 | Configurable in inverter settings |
| Sun-Synk / Deye | 9 600 | |
| GivEnergy | 9 600 | Gen 3 only; Gen 1/2 use a proprietary framing |
| Sigenergy | 9 600 | |
| Skyline / Duracell G3 | 9 600 | |
| SolarEdge | 115 200 | Modbus TCP on port 1502 is more common |

---

## Troubleshooting

### Port not found (`/dev/ttyUSB0` missing)

- Unplug and re-plug the adapter.
- Check `dmesg` for USB enumeration errors.
- On Home Assistant OS ensure the USB device is visible under **Settings → System → Hardware**.
- If another device is on `/dev/ttyUSB0`, your adapter may be on `/dev/ttyUSB1` or `/dev/ttyUSB2`.

### Permission denied on the serial port

On standard Linux (not HA OS) add your user to the `dialout` group:

```bash
sudo usermod -aG dialout $USER
# Log out and back in for the change to take effect
```

### TXD lights up but RXD never flashes

- Check wiring polarity — swap A and B if the inverter does not respond.
- Verify the baud rate, slave ID, and parity settings match the inverter configuration.
- Confirm no other software (Solis cloud app, another integration) is holding the RS485 bus.

### Intermittent disconnections / CRC errors

- Use a shorter or better-shielded cable.
- Reduce the poll frequency (increase **Fast / Normal / Slow Poll Interval** in the integration options).
- Ensure the GND terminal is connected — floating grounds cause noise on long RS485 runs.
- The adapter's onboard 120 Ω termination resistor is suitable for most installations. If you have very long cable runs with multiple devices, consider whether additional termination is needed at the inverter end.

---

## Where to Buy

Search for **"Waveshare USB to RS485 Industrial Converter"** on:

- [Waveshare official store](https://www.waveshare.com)
- Amazon, AliExpress, or your local electronics distributor

> The adapter uses the **FTDI FT232RL** chip. Beware of counterfeit FTDI chips sold by third parties — genuine Waveshare units use an original FT232RL and are clearly labelled.
