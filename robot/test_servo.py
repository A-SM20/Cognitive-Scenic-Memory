#!/usr/bin/env python3
"""
Task 4 Commissioning Script: MG90S Servo Calibration & Test
Tests conservative travel angles (center 90°, 45°, 135°) without hitting mechanical stops.
"""

import time
from servo_controller import ServoController


def run_servo_test():
    print("=" * 60)
    print("  COGNITIVE SCENE MEMORY ROBOT — SERVO TEST & CALIBRATION")
    print("=" * 60)
    print("SAFETY CHECK: Ensure camera mount cable has slack and does not snag!")
    input("Press ENTER when ready to test MG90S servo...")

    servo = None
    try:
        print("\n[1/4] Centering servo to 90 degrees...")
        servo = ServoController(pin=12)
        servo.center()
        time.sleep(1.0)

        print("[2/4] Moving gently to 45 degrees (Looking Left/Right)...")
        servo.set_angle(45.0, settle_time=0.6)
        time.sleep(1.0)

        print("[3/4] Moving gently to 135 degrees (Opposite side)...")
        servo.set_angle(135.0, settle_time=0.6)
        time.sleep(1.0)

        print("[4/4] Returning to center (90 degrees)...")
        servo.center()
        time.sleep(0.5)

        print("\n" + "=" * 60)
        print(">> SERVO TEST COMPLETED SUCCESSFULLY!")
        print("Observations:")
        print("  - Did the servo move smoothly without buzzing or clicking?")
        print("  - When stationary, the auto-detach logic stops PWM to keep it cool.")
        print("=" * 60)

    except KeyboardInterrupt:
        print("\n[!] Emergency stop requested.")
    except Exception as e:
        print(f"\n[!] Error during servo test: {e}")
    finally:
        if servo:
            servo.close()
        print("[*] Servo pin released.")


if __name__ == "__main__":
    run_servo_test()
