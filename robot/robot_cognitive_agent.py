#!/usr/bin/env python3
"""
Cognitive Scene Memory — Autonomous Robot Capture & Cognition Agent
Connects Raspberry Pi 5 hardware directly to the Cognitive Scene Memory backend.

Workflow:
1. Validates connection to Cognitive Scene Memory backend (GET /api/health).
2. Captures 4 directional views of the room (Front, Right, Back, Left) via calibrated turns.
3. Automatically uploads each view to POST /api/process/image.
4. Triggers real-time YOLO detection, spatial scene graph generation, memory tracking,
   and change detection on the backend.
5. Displays real-time detection counts and change detection summaries on the JHD162A LCD!
"""

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Optional

import requests

from motor_controller import MotorController
from servo_controller import ServoController
from lcd_driver import LCD1602
from capture_scan import SceneScanner


class CognitiveRobotAgent:
    """End-to-end robotic capture and cognition pipeline."""

    def __init__(self, backend_url: str = "http://127.0.0.1:8000"):
        self.backend_url = backend_url.rstrip("/")
        print("=" * 60)
        print("  COGNITIVE SCENE MEMORY — ROBOT CAPTURE AGENT")
        print("=" * 60)
        print(f"Backend Target: {self.backend_url}")

        self.scanner = SceneScanner(output_root="robot_scans")
        self.lcd = self.scanner.lcd

    def check_backend_connection(self) -> bool:
        """Verify connection to the Cognitive Scene Memory backend."""
        self.lcd.write_message("Checking Server", self.backend_url[-16:])
        print(f"[*] Testing connection to {self.backend_url}/api/health...")

        try:
            resp = requests.get(f"{self.backend_url}/api/health", timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                print(f"[✓] Backend online! Status: {data.get('status')}")
                self.lcd.write_message("Server: Online", "Model Ready")
                time.sleep(1.5)
                return True
            else:
                print(f"[!] Server returned HTTP {resp.status_code}")
                self.lcd.write_message("Server Error", f"HTTP {resp.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            print(f"[!] Cannot reach backend: {e}")
            self.lcd.write_message("Server Offline", "Check IP/Port")
            return False

    def upload_and_process_image(self, image_path: Path, view_index: int, total_views: int) -> Optional[dict]:
        """
        Uploads captured image to POST /api/process/image.
        Backend automatically:
          - Runs YOLO object detection
          - Saves original & annotated images
          - Updates active objects / Hungarian spatial matching
          - Computes memory decay
          - Builds semantic scene graph
          - Runs change detection vs previous scene!
        """
        endpoint = f"{self.backend_url}/api/process/image"
        print(f"[*] Uploading {image_path.name} to {endpoint}...")
        self.lcd.write_message(f"Upload {view_index}/{total_views}", "Processing YOLO")

        try:
            with open(image_path, "rb") as f:
                files = {"file": (image_path.name, f, "image/jpeg")}
                response = requests.post(endpoint, files=files, timeout=30.0)

            if response.status_code == 200:
                result = response.json()
                scene_id = result.get("scene_id", "N/A")
                total_objs = result.get("total_objects", 0)
                time_ms = result.get("processing_time_ms", 0.0)

                detected_classes = [d.get("class_name") for d in result.get("detections", [])]
                classes_summary = ", ".join(list(dict.fromkeys(detected_classes))[:3]) or "None"

                print(f"  [✓] Scene: {scene_id} | Objects: {total_objs} ({classes_summary}) | Time: {time_ms:.0f}ms")
                self.lcd.write_message(f"View {view_index}: {total_objs} objs", classes_summary[:16])
                return result
            else:
                print(f"  [✗] Upload failed with HTTP {response.status_code}: {response.text}")
                self.lcd.write_message(f"View {view_index} Error", f"HTTP {response.status_code}")
                return None

        except requests.exceptions.RequestException as e:
            print(f"  [✗] Upload request exception: {e}")
            self.lcd.write_message(f"View {view_index} Error", "Network Timeout")
            return None

    def fetch_recent_changes(self) -> list[dict]:
        """Fetch latest change detection results from backend."""
        try:
            resp = requests.get(f"{self.backend_url}/api/changes/recent?limit=5", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            print(f"[!] Could not fetch recent changes: {e}")
        return []

    def run_full_scan_and_cognition(self):
        """Executes full 4-view capture and real-time cognition loop."""
        if not self.check_backend_connection():
            print("[!] Aborting scan due to unavailable backend.")
            return

        print("\n[*] Starting 4-Direction Room Capture...")
        captured_images = self.scanner.perform_4_direction_scan()

        if not captured_images:
            print("[!] No images were captured.")
            self.lcd.write_message("Scan Failed", "No images captured")
            return

        print("\n" + "=" * 60)
        print("  PROCESSING CAPTURED IMAGES IN COGNITIVE SCENE MEMORY")
        print("=" * 60)

        total_detected_objects = 0
        processed_scenes = []

        for idx, img_path in enumerate(captured_images, start=1):
            res = self.upload_and_process_image(img_path, view_index=idx, total_views=len(captured_images))
            if res:
                total_detected_objects += res.get("total_objects", 0)
                processed_scenes.append(res.get("scene_id"))
            time.sleep(1.5)

        # Check for detected environmental changes
        recent_changes = self.fetch_recent_changes()
        print("\n" + "=" * 60)
        print(">> ROOM SCAN & COGNITIVE MEMORY COMPLETE!")
        print(f"Total Scenes Created: {len(processed_scenes)}")
        print(f"Total Objects Seen:   {total_detected_objects}")
        print(f"Recent Changes Found: {len(recent_changes)}")
        for chg in recent_changes[:3]:
            print(f"  - [{chg.get('change_type')}] {chg.get('description')}")
        print("=" * 60)
        print(">> Open your Web Dashboard at http://localhost:5173 to view:")
        print("   - Live Scene Graphs with spatial relationships")
        print("   - Object Track History & Memory Decay")
        print("   - Visual Before/After Change Comparisons")
        print("=" * 60)

        # Query memory summary for unique room objects
        active_room_objects = 0
        try:
            mem_resp = requests.get(f"{self.backend_url}/api/memory/summary", timeout=4.0)
            if mem_resp.status_code == 200:
                mem_data = mem_resp.json()
                active_room_objects = mem_data.get("active_count", total_detected_objects)
        except Exception:
            active_room_objects = total_detected_objects

        # Display final summary on LCD
        print(f"Active Objects in Room: {active_room_objects}")
        print("\n[*] Displaying detected room object summary on JHD162A LCD (Ctrl+C to stop)...")

        screens = [
            ("Room Scan Done!", f"Room Objs: {active_room_objects}"),
            (f"Active: {active_room_objects} objs", f"Observed: {total_detected_objects}"),
            ("Changes Seen:", f"Total Chgs: {len(recent_changes)}"),
            ("Cognitive Memory", "Web UI :5173"),
        ]

        try:
            # Cycle through summary screens 3 times or until interrupted
            for _ in range(3):
                for line1, line2 in screens:
                    self.lcd.write_message(line1, line2)
                    time.sleep(2.5)
        except KeyboardInterrupt:
            pass

        # Leave final persistent message on LCD
        self.lcd.write_message(
            f"Room Objs: {active_room_objects}",
            f"Chgs:{len(recent_changes)} (Ready)",
        )

    def close(self):
        self.scanner.close()


def main():
    parser = argparse.ArgumentParser(description="Cognitive Scene Memory Robot Client")
    parser.add_argument(
        "--server",
        default="http://127.0.0.1:8000",
        help="Backend server URL (e.g. http://192.168.1.100:8000)",
    )
    args = parser.parse_args()

    agent = None
    try:
        agent = CognitiveRobotAgent(backend_url=args.server)
        print("\nPress ENTER to begin 4-Direction Room Scan & Cognition...")
        input()
        agent.run_full_scan_and_cognition()
    except KeyboardInterrupt:
        print("\n[!] Program stopped by user.")
    finally:
        if agent:
            agent.close()


if __name__ == "__main__":
    main()
