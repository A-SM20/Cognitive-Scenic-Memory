#!/usr/bin/env python3
"""
Cognitive Scene Memory — Interactive Teleoperation & Cognitive Scanner
Runs directly on Raspberry Pi 5 over SSH.

Controls:
  [W] Drive Forward
  [S] Drive Backward
  [A] Pivot Left
  [D] Pivot Right
  [X] or [Space] Stop Motors

Camera Servo:
  [J] Pan Left (-15°)
  [L] Pan Right (+15°)
  [K] Center Camera (90°)

Cognitive Perception:
  [C] or [Enter] Capture Camera Frame -> Upload to Backend -> Run YOLO & Scene Memory -> Show on LCD & Web App!
  [Q] Quit & Safely Stop Motors
"""

import argparse
import os
import select
import sys
import termios
import time
import tty
from pathlib import Path
from typing import Optional

import requests

from motor_controller import MotorController
from servo_controller import ServoController

try:
    from lcd_driver import LCD1602
    LCD_AVAILABLE = True
except Exception:
    LCD_AVAILABLE = False

try:
    from picamera2 import Picamera2
    PICAMERA2_AVAILABLE = True
except Exception:
    PICAMERA2_AVAILABLE = False


def safe_lcd_write(lcd: Optional[object], line1: str, line2: str = ""):
    if lcd:
        try:
            lcd.write_message(line1, line2)
        except Exception:
            pass


def capture_frame(output_path: Path, camera_obj: Optional[object] = None) -> bool:
    """Captures 1 frame using Picamera2 or CLI fallback."""
    if camera_obj is not None:
        try:
            camera_obj.capture_file(str(output_path))
            return True
        except Exception:
            pass

    import subprocess
    for cmd in ["rpicam-still", "libcamera-still"]:
        try:
            res = subprocess.run(
                [cmd, "-o", str(output_path), "-t", "500", "--width", "1280", "--height", "720", "-n"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=8,
            )
            if res.returncode == 0 and output_path.exists():
                return True
        except Exception:
            continue

    try:
        res = subprocess.run(
            ["fswebcam", "-r", "1280x720", "--no-banner", str(output_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5,
        )
        if res.returncode == 0 and output_path.exists():
            return True
    except Exception:
        pass

    return False


def get_key(timeout: float = 0.1) -> str:
    """Read a single keypress from standard input non-blockingly."""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        rlist, _, _ = select.select([sys.stdin], [], [], timeout)
        if rlist:
            key = sys.stdin.read(1)
            # Handle ANSI escape sequences for arrow keys
            if key == '\x1b':
                more = sys.stdin.read(2)
                if more == '[A':
                    return 'UP'
                elif more == '[B':
                    return 'DOWN'
                elif more == '[C':
                    return 'RIGHT'
                elif more == '[D':
                    return 'LEFT'
            return key
        return ''
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def main():
    parser = argparse.ArgumentParser(description="Interactive Robot Drive & Cognitive Scan")
    parser.add_argument("--ip", default="10.150.189.180", help="Cognitive Server PC IP")
    parser.add_argument("--port", type=int, default=8001, help="Cognitive Server Port")
    parser.add_argument("--servo-pin", type=int, default=12, help="Servo GPIO pin (default: 12)")
    parser.add_argument("--in1", type=int, default=17, help="Motor IN1 (default: 17)")
    parser.add_argument("--in2", type=int, default=27, help="Motor IN2 (default: 27)")
    parser.add_argument("--in3", type=int, default=22, help="Motor IN3 (default: 22)")
    parser.add_argument("--in4", type=int, default=23, help="Motor IN4 (default: 23)")
    parser.add_argument("--ena", type=int, default=None, help="Motor ENA PWM (default: None for 5V jumper)")
    parser.add_argument("--enb", type=int, default=None, help="Motor ENB PWM (default: None for 5V jumper)")
    args = parser.parse_args()

    backend_url = f"http://{args.ip}:{args.port}"
    endpoint = f"{backend_url}/api/process/image"
    health_url = f"{backend_url}/api/health"

    print("=" * 65)
    print("  COGNITIVE SCENE MEMORY — ROBOT TELEOPERATION & SCANNER")
    print("=" * 65)
    print(f"Server Target : {backend_url}")
    print(f"Servo Pin     : GPIO {args.servo_pin}")
    print(f"Motor Pins    : IN1={args.in1}, IN2={args.in2}, IN3={args.in3}, IN4={args.in4}")
    print("=" * 65)

    # Initialize LCD
    lcd = None
    if LCD_AVAILABLE:
        try:
            lcd = LCD1602()
            safe_lcd_write(lcd, "Teleop Ready", "WASD to Drive")
        except Exception:
            pass

    # Initialize Motors
    motors = None
    try:
        motors = MotorController(
            pin_in1=args.in1,
            pin_in2=args.in2,
            pin_in3=args.in3,
            pin_in4=args.in4,
            pin_ena=args.ena,
            pin_enb=args.enb,
        )
        motors.stop()
        print("[✓] Motors initialized safely.")
    except Exception as e:
        print(f"[!] Warning: Motor init failed: {e}")

    # Initialize Servo
    servo = None
    servo_angle = 90.0
    try:
        servo = ServoController(pin=args.servo_pin)
        servo.center()
        print(f"[✓] Servo centered at 90° on GPIO {args.servo_pin}.")
    except Exception as e:
        print(f"[!] Warning: Servo init failed: {e}")

    # Initialize Camera
    camera = None
    if PICAMERA2_AVAILABLE:
        try:
            camera = Picamera2()
            cfg = camera.create_still_configuration(main={"size": (1280, 720)})
            camera.configure(cfg)
            camera.start()
            time.sleep(1.0)
            print("[✓] Picamera2 ready.")
        except Exception as e:
            print(f"[!] Picamera2 error: {e}. Will use CLI fallback.")
            camera = None

    print("\nREADY TO CONTROL ROBOT! (Press keys in this terminal):")
    print("  [W] Forward    | [S] Backward   | [A] Turn Left   | [D] Turn Right")
    print("  [X] Stop       | [Space] Stop")
    print("  [J] Pan Left   | [L] Pan Right  | [K] Center Cam (90°)")
    print("  [C] / [Enter]  Capture & Process in Cognitive Scene Memory!")
    print("  [Q] Quit")
    print("-" * 65)

    drive_duration = 0.35  # seconds per movement pulse
    capture_index = 1
    captured_dir = Path("teleop_scans")
    captured_dir.mkdir(exist_ok=True)

    try:
        while True:
            key = get_key(timeout=0.05)
            if not key:
                continue

            k = key.lower()

            if k == 'q':
                print("\n[!] Quitting teleoperation...")
                break

            elif k == 'w':
                print(">> [FORWARD] ⬆️")
                safe_lcd_write(lcd, "Driving...", "FORWARD ^")
                if motors:
                    motors.forward(speed=0.6)
                    time.sleep(drive_duration)
                    motors.stop()

            elif k == 's':
                print(">> [BACKWARD] ⬇️")
                safe_lcd_write(lcd, "Driving...", "BACKWARD v")
                if motors:
                    motors.backward(speed=0.6)
                    time.sleep(drive_duration)
                    motors.stop()

            elif k == 'a':
                print(">> [PIVOT LEFT] ⬅️")
                safe_lcd_write(lcd, "Driving...", "TURN LEFT <")
                if motors:
                    motors.pivot_left(speed=0.6)
                    time.sleep(0.25)
                    motors.stop()

            elif k == 'd':
                print(">> [PIVOT RIGHT] ➡️")
                safe_lcd_write(lcd, "Driving...", "TURN RIGHT >")
                if motors:
                    motors.pivot_right(speed=0.6)
                    time.sleep(0.25)
                    motors.stop()

            elif k in ['x', ' ']:
                print(">> [STOP] 🛑")
                if motors:
                    motors.stop()
                safe_lcd_write(lcd, "Motors Stopped", f"Cam: {int(servo_angle)} deg")

            elif k in ['j', 'left']:
                servo_angle = max(15.0, servo_angle - 15.0)
                print(f">> [SERVO LEFT] ↰ Angle: {int(servo_angle)}°")
                if servo:
                    servo.set_angle(servo_angle, settle_time=0.25)
                safe_lcd_write(lcd, "Servo Panning", f"Angle: {int(servo_angle)} deg")

            elif k in ['l', 'right']:
                servo_angle = min(165.0, servo_angle + 15.0)
                print(f">> [SERVO RIGHT] ↱ Angle: {int(servo_angle)}°")
                if servo:
                    servo.set_angle(servo_angle, settle_time=0.25)
                safe_lcd_write(lcd, "Servo Panning", f"Angle: {int(servo_angle)} deg")

            elif k in ['k', 'up']:
                servo_angle = 90.0
                print(">> [SERVO CENTER] ⏺ Angle: 90°")
                if servo:
                    servo.center()
                safe_lcd_write(lcd, "Servo Centered", "Angle: 90 deg")

            elif k in ['c', '\r', '\n']:
                # Stop motors first
                if motors:
                    motors.stop()
                time.sleep(0.3)

                img_path = captured_dir / f"scan_{capture_index:03d}.jpg"
                print(f"\n[*] Capturing view {capture_index} -> {img_path.name}...")
                safe_lcd_write(lcd, f"Scan #{capture_index}", "Capturing...")

                if not capture_frame(img_path, camera):
                    print("[✗] Camera capture failed!")
                    safe_lcd_write(lcd, "Camera Error", "Capture Failed")
                    continue

                safe_lcd_write(lcd, f"Scan #{capture_index}", "Uploading YOLO")
                print(f"[*] Uploading to {endpoint}...")

                try:
                    start_t = time.time()
                    with open(img_path, "rb") as f:
                        files = {"file": (img_path.name, f, "image/jpeg")}
                        resp = requests.post(endpoint, files=files, timeout=30.0)
                    elapsed = time.time() - start_t

                    if resp.status_code == 200:
                        data = resp.json()
                        total_objs = data.get("total_objects", 0)
                        classes = [d.get("class_name") for d in data.get("detections", [])]
                        unique_classes = list(dict.fromkeys(classes))
                        classes_str = ", ".join(unique_classes[:2]) if unique_classes else "None"

                        print(f"  [✓] Objects Detected : {total_objs}")
                        print(f"  [✓] Classes Seen     : {', '.join(unique_classes) or 'None'}")
                        print(f"  [✓] Server Time      : {elapsed*1000:.0f}ms")
                        print("  💡 Check live web UI at http://localhost:5173\n")

                        safe_lcd_write(lcd, f"Objs: {total_objs} found", classes_str[:16])
                        capture_index += 1
                    else:
                        print(f"  [!] Server error {resp.status_code}: {resp.text}")
                        safe_lcd_write(lcd, "Server Error", f"HTTP {resp.status_code}")
                except Exception as e:
                    print(f"  [!] Upload error: {e}")
                    safe_lcd_write(lcd, "Network Error", "Timeout")

    except KeyboardInterrupt:
        print("\n[!] Emergency stop requested.")

    finally:
        print("\n[*] Shutting down subsystems...")
        if motors:
            motors.stop()
            motors.close()
        if servo:
            servo.center()
            servo.close()
        if camera:
            try:
                camera.stop()
            except Exception:
                pass
        safe_lcd_write(lcd, "Robot Standby", "Cognitive Memory")
        print("[✓] All GPIO pins safely released. Robot stopped.")


if __name__ == "__main__":
    main()
