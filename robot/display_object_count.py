#!/usr/bin/env python3
"""
Standalone LCD Display Monitor for JHD162A 16x2 LCD.
Connects to Cognitive Scene Memory backend and continuously displays:
  - Total detected objects in room
  - Number of active persistent objects in memory
  - Breakdown of detected classes (e.g. Chair: 3, Table: 1, Laptop: 2)
  - Recent change detection count
"""

import argparse
import sys
import time
import requests
from lcd_driver import LCD1602


class LCDObjectMonitor:
    """Displays real-time detected object stats from Cognitive Scene Memory on JHD162A."""

    def __init__(self, backend_url: str = "http://127.0.0.1:8000"):
        self.backend_url = backend_url.rstrip("/")
        print(f"[*] Initializing LCD Object Monitor pointing to {self.backend_url}...")
        self.lcd = LCD1602()
        self.lcd.write_message("Object Monitor", "Connecting...")

    def fetch_memory_summary(self) -> dict:
        """Fetch overall memory status and active object count."""
        try:
            resp = requests.get(f"{self.backend_url}/api/memory/summary", timeout=4.0)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return {}

    def fetch_active_objects(self) -> list:
        """Fetch list of all active tracked objects."""
        try:
            resp = requests.get(f"{self.backend_url}/api/memory/objects", timeout=4.0)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return []

    def fetch_recent_changes(self) -> list:
        """Fetch recent changes detected."""
        try:
            resp = requests.get(f"{self.backend_url}/api/changes/recent?limit=5", timeout=4.0)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return []

    def run_monitor_loop(self, cycle_interval: float = 3.0):
        """Continuously cycles useful object counts and metrics on the LCD."""
        print("[*] Starting LCD Monitor display loop. Press Ctrl+C to exit.")

        while True:
            summary = self.fetch_memory_summary()
            objects = self.fetch_active_objects()
            changes = self.fetch_recent_changes()

            if not summary:
                self.lcd.write_message("Waiting Server..", self.backend_url[-16:])
                time.sleep(2.0)
                continue

            active_count = summary.get("active_count", 0)
            total_unique = summary.get("total_objects", 0)

            # Count classes
            class_counts = {}
            for obj in objects:
                cname = obj.get("class_name", "item")
                class_counts[cname] = class_counts.get(cname, 0) + 1

            # Build top classes summary (e.g., "chair:3 cup:2")
            top_classes = sorted(class_counts.items(), key=lambda x: x[1], reverse=True)[:2]
            top_str = " ".join([f"{k[:4]}:{v}" for k, v in top_classes]) or "None yet"

            # Screen 1: Total detected objects in room
            self.lcd.write_message(
                f"Room Objs: {active_count}",
                f"Unique: {total_unique} items",
            )
            time.sleep(cycle_interval)

            # Screen 2: Top object classes detected
            self.lcd.write_message(
                "Top Detected:",
                top_str[:16],
            )
            time.sleep(cycle_interval)

            # Screen 3: Environment changes detected
            total_changes = len(changes)
            self.lcd.write_message(
                "Changes Seen:",
                f"Total Chgs: {total_changes}",
            )
            time.sleep(cycle_interval)


def main():
    parser = argparse.ArgumentParser(description="LCD Object Count Monitor")
    parser.add_argument(
        "--server",
        default="http://10.150.189.180:8001",
        help="Cognitive Scene Memory Server URL (e.g. http://10.150.189.180:8001)",
    )
    args = parser.parse_args()

    monitor = None
    try:
        monitor = LCDObjectMonitor(backend_url=args.server)
        monitor.run_monitor_loop()
    except KeyboardInterrupt:
        print("\n[*] Monitor stopped.")
    finally:
        if monitor:
            monitor.lcd.write_message("Monitor Stopped", "Ready")


if __name__ == "__main__":
    main()
