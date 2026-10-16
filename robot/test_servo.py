#!/usr/bin/env python3
"""
MG90S / SG90 Servo Calibration & Test Script for Raspberry Pi 5.
Tests pan movement: Center (90°), Left (45°), Right (135°), and gentle sweep.
"""

import argparse
import sys
import time
from servo_controller import ServoController


def main():
    parser = argparse.ArgumentParser(description="Test MG90S servo on Raspberry Pi 5")
    parser.add_argument("--pin", type=int, default=12, help="BCM GPIO pin for servo PWM signal (default: 12, Physical Pin 32)")
    args = parser.parse_args()

    print("=" * 60)
    print("  COGNITIVE SCENE MEMORY ROBOT — SERVO TEST & CALIBRATION")
    print("=" * 60)
    print(f"Target Servo Signal Pin: GPIO {args.pin} (BCM)")
    print("Wiring Check:")
    print("  - Brown / Black wire -> Pi 5 GND (e.g. Pin 6 or 14)")
    print("  - Red wire           -> Pi 5 5V  (Pin 2 or 4)")
    print(f"  - Orange / Yellow    -> Pi 5 GPIO {args.pin}")
    print("SAFETY CHECK: Ensure camera mount ribbon cable has slack and does not snag!")
    print("=" * 60)
    input("Press ENTER when ready to test servo...")

    servo = None
    try:
        print("\n[1/5] Centering servo to 90 degrees...")
        servo = ServoController(pin=args.pin)
        servo.center()
        time.sleep(1.0)

        print("[2/5] Panning gently to 45 degrees (Looking Left)...")
        servo.set_angle(45.0, settle_time=0.6)
        time.sleep(1.0)

        print("[3/5] Panning gently to 135 degrees (Looking Right)...")
        servo.set_angle(135.0, settle_time=0.6)
        time.sleep(1.0)

        print("[4/5] Returning to center (90 degrees)...")
        servo.center()
        time.sleep(0.5)

        print("[5/5] Performing smooth 3-point sweep...")
        for angle in [60, 90, 120, 90]:
            servo.set_angle(angle, settle_time=0.3)
            time.sleep(0.2)

        print("\n" + "=" * 60)
        print(">> SERVO TEST COMPLETED SUCCESSFULLY!")
        print("Auto-detach is active: servo is de-energized to prevent buzzing & overheating.")
        print("=" * 60)

    except KeyboardInterrupt:
        print("\n[!] Emergency stop requested.")
    except Exception as e:
        print(f"\n[!] Error during servo test: {e}")
        print("💡 Tip: If you get a pin busy error, verify no other script is running on that GPIO.")
    finally:
        if servo:
            servo.close()
        print("[*] Servo pin released.")


if __name__ == "__main__":
    main()
