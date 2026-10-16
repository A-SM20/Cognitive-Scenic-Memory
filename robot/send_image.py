#!/usr/bin/env python3
"""
Cognitive Scene Memory — Single Image Capture & Upload Client (Pi 5)
Captures 1 frame from the Pi Camera, uploads to the backend server via HTTP,
and displays the detected object count on the 16x2 JHD162A LCD screen.
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import requests

# Try importing the LCD driver
try:
    from lcd_driver import LCD1602
    LCD_AVAILABLE = True
except Exception:
    LCD_AVAILABLE = False

# Try importing Picamera2
try:
    from picamera2 import Picamera2
    PICAMERA2_AVAILABLE = True
except Exception:
    PICAMERA2_AVAILABLE = False


def safe_lcd_write(lcd: Optional[object], line1: str, line2: str = ""):
    """Helper to update LCD if connected without crashing if disconnected."""
    if lcd:
        try:
            lcd.write_message(line1, line2)
        except Exception as e:
            print(f"[LCD Error] {e}")


def capture_single_image(output_path: Path) -> bool:
    """Captures 1 image from Pi Camera using Picamera2 or CLI fallback."""
    print(f"[*] Capturing camera frame to {output_path}...")

    # Method 1: Picamera2
    if PICAMERA2_AVAILABLE:
        try:
            picam = Picamera2()
            config = picam.create_still_configuration(main={"size": (1280, 720)})
            picam.configure(config)
            picam.start()
            time.sleep(1.0)  # Auto-exposure warm-up
            picam.capture_file(str(output_path))
            picam.stop()
            picam.close()
            print("[✓] Captured via Picamera2.")
            return True
        except Exception as e:
            print(f"[!] Picamera2 failed: {e}. Trying CLI fallback...")

    # Method 2: rpicam-still (Debian Bookworm default on Pi 5)
    for cmd_binary in ["rpicam-still", "libcamera-still"]:
        cmd = [cmd_binary, "-o", str(output_path), "-t", "1000", "--width", "1280", "--height", "720", "-n"]
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
            if res.returncode == 0 and output_path.exists():
                print(f"[✓] Captured via {cmd_binary}.")
                return True
        except FileNotFoundError:
            continue
        except Exception as e:
            print(f"[!] {cmd_binary} error: {e}")

    # Method 3: fswebcam or USB webcam fallback
    try:
        res = subprocess.run(["fswebcam", "-r", "1280x720", "--no-banner", str(output_path)],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=8)
        if res.returncode == 0 and output_path.exists():
            print("[✓] Captured via fswebcam.")
            return True
    except Exception:
        pass

    return False


def main():
    parser = argparse.ArgumentParser(description="Capture 1 image from Pi 5 and send to Cognitive Backend")
    parser.add_argument("--ip", default="172.16.61.163", help="Backend PC IP address (e.g., 172.16.61.163 or 192.168.137.1)")
    parser.add_argument("--port", default=8001, type=int, help="Backend port (default: 8001)")
    parser.add_argument("--image", default="scan_capture.jpg", help="Local output filename for captured image")
    args = parser.parse_args()

    backend_url = f"http://{args.ip}:{args.port}"
    endpoint = f"{backend_url}/api/process/image"
    health_url = f"{backend_url}/api/health"

    print("=" * 60)
    print("  COGNITIVE SCENE MEMORY — PI 5 SINGLE-SHOT SENSOR")
    print("=" * 60)
    print(f"Target Server: {backend_url}")

    # Initialize LCD
    lcd = None
    if LCD_AVAILABLE:
        try:
            lcd = LCD1602()
            safe_lcd_write(lcd, "Connecting...", args.ip[-15:])
        except Exception as e:
            print(f"[!] Warning: Could not initialize LCD: {e}")

    # 1. Test Backend Connection
    print(f"[*] Testing connection to {health_url}...")
    try:
        h_resp = requests.get(health_url, timeout=5.0)
        if h_resp.status_code == 200:
            print(f"[✓] Connected to backend! Model: {h_resp.json().get('model_name')}")
            safe_lcd_write(lcd, "Server: Online", "Ready to Scan")
            time.sleep(1.0)
        else:
            print(f"[!] Server returned HTTP {h_resp.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"[!] Connection failed: {e}")
        safe_lcd_write(lcd, "Server Offline", "Check Wi-Fi/IP")
        print("\n💡 Tip: Check that:")
        print(f"  1. The PC and Pi are on the same Wi-Fi network.")
        print(f"  2. Uvicorn on PC is running with: --host 0.0.0.0 --port {args.port}")
        return

    # 2. Capture Frame
    image_file = Path(args.image)
    safe_lcd_write(lcd, "Capturing...", "Pi Camera")
    if not capture_single_image(image_file):
        print("[✗] Failed to capture image from camera.")
        safe_lcd_write(lcd, "Camera Error", "Capture Failed")
        return

    # 3. Upload to Backend
    safe_lcd_write(lcd, "Uploading...", "Running YOLO")
    print(f"[*] Uploading {image_file.name} ({image_file.stat().st_size // 1024} KB) to {endpoint}...")

    try:
        start_t = time.time()
        with open(image_file, "rb") as f:
            files = {"file": (image_file.name, f, "image/jpeg")}
            response = requests.post(endpoint, files=files, timeout=30.0)
        elapsed = time.time() - start_t

        if response.status_code == 200:
            data = response.json()
            scene_id = data.get("scene_id", "N/A")
            total_objs = data.get("total_objects", 0)
            inference_ms = data.get("processing_time_ms", 0.0)

            # Extract unique classes
            detections = data.get("detections", [])
            class_names = [d.get("class_name") for d in detections]
            unique_classes = list(dict.fromkeys(class_names))
            classes_str = ", ".join(unique_classes[:2]) if unique_classes else "None"

            print("\n" + "=" * 50)
            print(f"  [✓] SCENE ASSIGNED : {scene_id}")
            print(f"  [✓] OBJECTS FOUND  : {total_objs}")
            print(f"  [✓] CLASSES SEEN   : {', '.join(unique_classes) or 'None'}")
            print(f"  [✓] INFERENCE TIME : {inference_ms:.0f}ms (roundtrip: {elapsed*1000:.0f}ms)")
            print("=" * 50)
            print("💡 Now open the website at http://localhost:5173 to view the live annotated photo and scene graph!")

            # 4. Display on 16x2 LCD
            safe_lcd_write(lcd, f"Objs: {total_objs} found", classes_str[:16])

        else:
            print(f"[✗] Upload failed with HTTP {response.status_code}: {response.text}")
            safe_lcd_write(lcd, "Upload Failed", f"HTTP {response.status_code}")

    except requests.exceptions.RequestException as e:
        print(f"[✗] Upload network error: {e}")
        safe_lcd_write(lcd, "Network Error", "Timeout/Dropped")


if __name__ == "__main__":
    main()
