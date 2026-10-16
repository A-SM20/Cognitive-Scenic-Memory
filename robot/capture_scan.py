#!/usr/bin/env python3
"""
Task 6: Four-Direction Image Capture & Local Storage
Coordinates:
1. Motor Controller (stops motors before capturing, performs calibrated 90° pivots).
2. Servo Controller (centers the MG90S mount).
3. Pi Camera (captures high-resolution images with Picamera2 or libcamera-still fallback).
4. JHD162A LCD (displays live progress).
5. Timestamped scan directory storage.
"""

import os
import sys
import time
import subprocess
from datetime import datetime
from pathlib import Path

from motor_controller import MotorController
from servo_controller import ServoController
from lcd_driver import LCD1602

# Check if Picamera2 is available
try:
    from picamera2 import Picamera2
    PICAMERA2_AVAILABLE = True
except ImportError:
    PICAMERA2_AVAILABLE = False


class SceneScanner:
    """Orchestrates 4-direction room scanning."""

    def __init__(self, output_root: str = "scans"):
        self.output_root = Path(output_root)
        self.output_root.mkdir(parents=True, exist_ok=True)

        print("[*] Initializing robot subsystems...")
        self.lcd = LCD1602()
        self.lcd.write_message("Initializing...", "Please wait")

        self.motors = MotorController()
        self.motors.stop()  # Strict safety rule: ensure motors stopped

        self.servo = ServoController(pin=12)
        self.servo.center()  # Keep camera looking straight ahead relative to chassis

        self.camera = None
        if PICAMERA2_AVAILABLE:
            try:
                self.camera = Picamera2()
                config = self.camera.create_still_configuration(main={"size": (1920, 1080)})
                self.camera.configure(config)
                self.camera.start()
                time.sleep(1.0)  # Camera warm-up / auto-exposure
                print("[*] Picamera2 started successfully.")
            except Exception as e:
                print(f"[!] Warning: Picamera2 initialization error ({e}). Falling back to libcamera-still.")
                self.camera = None

        self.lcd.write_message("System Ready", "4-View Scanner")
        time.sleep(1.0)

    def capture_image(self, target_filepath: Path) -> bool:
        """Capture an image to the specified path."""
        target_filepath.parent.mkdir(parents=True, exist_ok=True)

        if self.camera is not None:
            try:
                self.camera.capture_file(str(target_filepath))
                return True
            except Exception as e:
                print(f"[!] Picamera2 capture error: {e}. Trying CLI fallback...")

        # Fallback to libcamera-still / rpicam-still command
        cmd = ["libcamera-still", "-n", "-o", str(target_filepath), "--width", "1920", "--height", "1080", "-t", "500"]
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
            if res.returncode == 0:
                return True
        except FileNotFoundError:
            # On latest Debian Bookworm, libcamera-still is aliased to rpicam-still
            cmd[0] = "rpicam-still"
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
            if res.returncode == 0:
                return True

        return False

    def perform_4_direction_scan(self) -> list[Path]:
        """
        Executes a 4-direction room scan:
          View 1: Front (0°)
          View 2: Right (90°)
          View 3: Back (180°)
          View 4: Left (270°)
        Returns the list of saved image paths.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        scan_dir = self.output_root / f"scan_{timestamp}"
        scan_dir.mkdir(parents=True, exist_ok=True)

        views = [
            ("view_1_front", "Front (0 deg)", False),
            ("view_2_right", "Right (90 deg)", True),
            ("view_3_back",  "Back (180 deg)", True),
            ("view_4_left",  "Left (270 deg)", True),
        ]

        captured_files = []

        print(f"\n[*] Starting 4-Direction Scan into: {scan_dir}")
        self.lcd.write_message("Scan Initiated", "Stay clear")
        time.sleep(1.0)

        for idx, (view_name, view_label, need_turn) in enumerate(views, start=1):
            if need_turn:
                # Pivot 90 degrees right
                print(f"[*] Rotating chassis 90° right to face {view_label}...")
                self.lcd.write_message("Turning 90 deg", f"Target: View {idx}")
                self.motors.pivot_90(direction="right")

            # Ensure motors are completely stopped and settle camera vibration
            self.motors.stop()
            time.sleep(0.6)

            # Update LCD and capture
            img_path = scan_dir / f"{view_name}.jpg"
            print(f"[*] Capturing View {idx}/4: {view_label} -> {img_path.name}")
            self.lcd.write_message(f"View {idx}/4: {view_label[:7]}", "Capturing...")

            success = self.capture_image(img_path)
            if success and img_path.exists():
                file_size_kb = img_path.stat().st_size / 1024
                print(f"  [✓] Saved {img_path.name} ({file_size_kb:.1f} KB)")
                captured_files.append(img_path)
                self.lcd.write_message(f"View {idx}/4 OK", f"{file_size_kb:.0f}KB saved")
            else:
                print(f"  [✗] Failed to capture {img_path.name}")
                self.lcd.write_message(f"View {idx}/4", "Capture Failed!")

            time.sleep(0.5)

        # Pivot 90° once more to return robot to original front heading (360° total rotation)
        print("[*] Realigning chassis back to original forward heading...")
        self.lcd.write_message("Realigning...", "Heading 0 deg")
        self.motors.pivot_90(direction="right")
        self.motors.stop()

        print("\n" + "=" * 60)
        print(f">> SCAN COMPLETE! Captured {len(captured_files)}/4 images in {scan_dir}")
        print("=" * 60)
        self.lcd.write_message("Scan Complete!", f"{len(captured_files)} views saved")
        return captured_files

    def close(self):
        """Clean shutdown of all peripherals."""
        print("[*] Shutting down scanner...")
        if self.motors:
            self.motors.stop()
            self.motors.close()
        if self.servo:
            self.servo.close()
        if self.camera is not None:
            try:
                self.camera.stop()
            except Exception:
                pass
        if self.lcd:
            # Leave message visible
            time.sleep(1.0)


def main():
    scanner = None
    try:
        scanner = SceneScanner()
        input("Press ENTER to trigger 4-direction room capture...")
        scanner.perform_4_direction_scan()
    except KeyboardInterrupt:
        print("\n[!] Scan cancelled by user.")
    except Exception as e:
        print(f"\n[!] Error during scan: {e}")
    finally:
        if scanner:
            scanner.close()


if __name__ == "__main__":
    main()
