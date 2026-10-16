# Cognitive Scene Memory Robot — Physical Wiring & Commissioning Guide

This folder contains all drivers, commissioning test scripts, and the autonomous capture agent for the **Raspberry Pi 5** robot running the **Cognitive Scene Memory** pipeline.

---

## 1. Hardware Architecture & Confirmed Specifications

- **Compute**: Raspberry Pi 5 (Debian Bookworm, RP1 GPIO architecture).
- **Camera**: Raspberry Pi Camera Module connected via CSI ribbon cable.
- **Drive System**: 4x Yellow plastic dual-shaft TT gear motors (3V–6V DC).
- **Motor Driver**: L298N Dual H-Bridge module.
- **Motor Battery**: 6x AA battery pack (~7.2V NiMH to 9.0V Alkaline).
- **Pan/Tilt Mount**: TowerPro MG90S metal-gear servo.
- **Status Display**: JHD162A 16×2 Character LCD (bare 16-pin, 4-bit parallel mode).

---

## 2. Master Wiring & Pinout Guide

### 2.1 Raspberry Pi 5 to L298N Dual H-Bridge

| L298N Terminal | BCM GPIO | Pi Physical Pin | Function |
|:---|:---:|:---:|:---|
| **ENA** | GPIO 18 | Pin 12 | Left Motor PWM Speed |
| **IN1** | GPIO 17 | Pin 11 | Left Motor Direction A |
| **IN2** | GPIO 27 | Pin 13 | Left Motor Direction B |
| **IN3** | GPIO 22 | Pin 15 | Right Motor Direction A |
| **IN4** | GPIO 23 | Pin 16 | Right Motor Direction B |
| **ENB** | GPIO 13 | Pin 33 | Right Motor PWM Speed |
| **GND** | GND | Pin 6 | **Common Logic Ground** |

### 2.2 Motor Power & Output Connections
- **L298N +12V Terminal**: Connect to **Battery Positive (+)** (Red wire from 6x AA pack).
- **L298N GND Terminal**: Connect to **Battery Negative (-)** (Black wire) AND **Pi GND** (Pin 6).
- **L298N 5V Jumper**: **Keep ON**. Since the 6x AA pack is $\le 12V$, the onboard 78M05 regulator will power the L298N internal logic.
- **L298N +5V Screw Terminal**: **DO NOT CONNECT TO PI 5V RAIL!** Leave open or use only for low-current sensor power if needed. Never backfeed into the Pi's USB-C supply.
- **OUT1 & OUT2**: Connect to the **Left-side two motors in parallel**.
- **OUT3 & OUT4**: Connect to the **Right-side two motors in parallel**.

### 2.3 MG90S Servo Wiring
- **Signal (Orange/Yellow)**: Connect to Pi Physical Pin 32 (**BCM GPIO 12**).
- **Positive (Red)**: Connect to external regulated 5V supply (+) or dedicated 5V buck converter. (Do **not** power from Pi 5V header pins to prevent brownout crashes).
- **Ground (Brown/Black)**: Connect to external supply GND **and** Pi GND (Common Ground).

### 2.4 JHD162A 16×2 Character LCD (4-Bit Safe Mode)

> **SAFETY RULE**: Pin 5 ($R/\overline{W}$) **must be hardwired to Ground**. This locks the LCD in write-only mode and prevents it from ever outputting 5V signals to the Pi 5's 3.3V GPIO.

| LCD Pin | Label | Connect To | Description |
|:---:|:---:|:---|:---|
| **Pin 1** | VSS | Ground Bus (Pi GND) | Logic Ground |
| **Pin 2** | VDD | +5V Rail (Pi Pin 2 or 4) | Logic Power Supply |
| **Pin 3** | VO | Wiper (center pin) of 10kΩ Potentiometer | Contrast Adjustment |
| **Pin 4** | RS | Pi Physical Pin 29 (**BCM GPIO 5**) | Register Select (3.3V logic) |
| **Pin 5** | R/W | **HARD-WIRED TO GND** | Write-only safe mode |
| **Pin 6** | E | Pi Physical Pin 31 (**BCM GPIO 6**) | Enable Clock Pulse |
| **Pins 7–10** | D0–D3 | *No Connection* | Not used in 4-bit mode |
| **Pin 11** | D4 | Pi Physical Pin 36 (**BCM GPIO 16**) | Data Bit 4 |
| **Pin 12** | D5 | Pi Physical Pin 38 (**BCM GPIO 20**) | Data Bit 5 |
| **Pin 13** | D6 | Pi Physical Pin 40 (**BCM GPIO 21**) | Data Bit 6 |
| **Pin 14** | D7 | Pi Physical Pin 37 (**BCM GPIO 26**) | Data Bit 7 |
| **Pin 15** | A (LED+) | +5V via 220Ω Resistor | Backlight Anode |
| **Pin 16** | K (LED-) | Ground Bus (Pi GND) | Backlight Cathode |

---

## 3. Software Setup on Raspberry Pi 5

Run the following commands on the Raspberry Pi 5 to install the required Bookworm packages:

```bash
# 1. Update package lists
sudo apt update

# 2. Install GPIO and Camera packages for Pi 5 (RP1 chip)
sudo apt install -y python3-gpiozero python3-lgpio python3-picamera2 python3-requests

# 3. Clone or copy this repository to the Pi:
cd ~
git clone <YOUR_REPO_URL> cognitive_scenic_memory
cd cognitive_scenic_memory/robot
```

---

## 4. Step-by-Step Commissioning Procedure

Execute the tests in this strict order:

### Step 1: Commission the LCD Display
```bash
python3 test_lcd.py
```
- Verify backlight turns on.
- Slowly turn the 10k potentiometer until crisp characters appear:
  `Cognitive Scene`
  `Memory Robot OK`

### Step 2: Commission the Servo
```bash
python3 test_servo.py
```
- Verifies conservative travel (90° center, 45°, 135°).
- Checks that the camera ribbon cable has adequate slack.
- Auto-detaches PWM to eliminate motor hum/heat.

### Step 3: Commission the Motor Driver
> **WARNING: Elevate wheels off the bench before running!**
```bash
python3 test_motors.py
```
- Tests forward, backward, pivot left, pivot right.
- If any wheel turns in the opposite direction, invert its two wires at the L298N terminal.

### Step 4: Interactive Teleoperation & Cognitive Scan (WASD Driving + Servo + Perception)
```bash
python3 teleop_drive.py --ip 10.150.189.180 --port 8001
```
- **[W] / [S]**: Drive Forward / Backward
- **[A] / [D]**: Pivot Left / Right
- **[X] / [Space]**: Stop Motors
- **[J] / [L]**: Pan Servo Left / Right
- **[K]**: Center Servo (90°)
- **[C] / [Enter]**: Capture camera frame, upload to PC backend, run YOLO detection, and display object counts on the LCD!
- **[Q]**: Quit safely.

---

## 5. End-to-End System Integration

Connect the robot directly to the **Cognitive Scene Memory** server running on your workstation/laptop:

```bash
# Run the autonomous cognitive client:
python3 robot_cognitive_agent.py --server http://10.150.189.180:8001
```

### What Happens Automatically:
1. Validates connection to `http://10.150.189.180:8001/api/health`.
2. Captures all 4 views of the room in sequence.
3. Uploads each view via HTTP POST to `/api/process/image`.
4. The server runs real-time YOLOv8 detection, updates spatial objects, advances memory decay, constructs the semantic scene graph, and detects changes vs previous scans.
5. Displays live object counts and changes summary directly on the robot's 16×2 LCD!
6. You can immediately open the Web Dashboard (`http://localhost:5173`) to view:
   - Interactive 2D/3D Scene Graphs
   - Before/After Change Detection Comparisons
   - Cognitive Memory Decay Timeline

---

## 6. Standalone Real-Time LCD Object Count Monitor

You can also run a dedicated monitor on the Raspberry Pi 5 to display current room object counts at any time:

```bash
python3 display_object_count.py --server http://10.150.189.180:8001
```

