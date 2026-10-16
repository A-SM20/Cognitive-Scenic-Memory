#!/usr/bin/env python3
"""
Task 3 Commissioning Script: Motor Driver Test
Tests forward, backward, left pivot, right pivot, and stop on L298N.

SAFETY INSTRUCTION:
Ensure robot wheels are lifted off the ground (elevated on a stand or block)
so it cannot drive off the workspace!
"""

import sys
import time
from motor_controller import MotorController


def run_motor_test():
    print("=" * 60)
    print("  COGNITIVE SCENE MEMORY ROBOT — MOTOR TEST SUITE")
    print("=" * 60)
    print("SAFETY CHECK: Ensure robot wheels are ELEVATED off the bench!")
    input("Press ENTER when wheels are elevated and battery is connected...")

    motors = None
    try:
        print("\n[1/5] Initializing motor controller on GPIO 18, 17, 27, 22, 23, 13...")
        motors = MotorController()
        time.sleep(0.5)

        print("[2/5] Testing FORWARD (40% speed, 1.5 seconds)...")
        motors.forward(speed=0.4)
        time.sleep(1.5)
        motors.stop()
        time.sleep(1.0)

        print("[3/5] Testing BACKWARD (40% speed, 1.5 seconds)...")
        motors.backward(speed=0.4)
        time.sleep(1.5)
        motors.stop()
        time.sleep(1.0)

        print("[4/5] Testing PIVOT LEFT (Counter-Clockwise, 1.0 second)...")
        motors.pivot_left(speed=0.5)
        time.sleep(1.0)
        motors.stop()
        time.sleep(1.0)

        print("[5/5] Testing PIVOT RIGHT (Clockwise, 1.0 second)...")
        motors.pivot_right(speed=0.5)
        time.sleep(1.0)
        motors.stop()

        print("\n" + "=" * 60)
        print(">> MOTOR TEST COMPLETED SUCCESSFULLY!")
        print("Verify:")
        print("  - Did left and right wheels turn forward during FORWARD?")
        print("  - If any wheel turned backwards, simply swap its OUT1/OUT2 or OUT3/OUT4 wires.")
        print("=" * 60)

    except KeyboardInterrupt:
        print("\n[!] Emergency stop requested by user.")
    except Exception as e:
        print(f"\n[!] Error during motor test: {e}")
    finally:
        if motors:
            motors.stop()
            motors.close()
        print("[*] Motor driver shutdown complete. All PWM pins cleared.")


if __name__ == "__main__":
    run_motor_test()
