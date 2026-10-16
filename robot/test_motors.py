#!/usr/bin/env python3
"""
Motor Driver Test Script for L298N on Raspberry Pi 5.
Tests forward, backward, left pivot, right pivot, and stop on L298N.

SAFETY INSTRUCTION:
Ensure robot wheels are lifted off the ground (elevated on a stand or box)
so it cannot drive off the table during testing!
"""

import argparse
import sys
import time
from motor_controller import MotorController


def main():
    parser = argparse.ArgumentParser(description="Test 4WD motors via L298N driver")
    parser.add_argument("--in1", type=int, default=17, help="GPIO for Left Motor IN1 (default: 17)")
    parser.add_argument("--in2", type=int, default=27, help="GPIO for Left Motor IN2 (default: 27)")
    parser.add_argument("--in3", type=int, default=22, help="GPIO for Right Motor IN3 (default: 22)")
    parser.add_argument("--in4", type=int, default=23, help="GPIO for Right Motor IN4 (default: 23)")
    parser.add_argument("--ena", type=int, default=None, help="Optional GPIO for Left ENA PWM (default: None, assumes 5V jumper cap)")
    parser.add_argument("--enb", type=int, default=None, help="Optional GPIO for Right ENB PWM (default: None, assumes 5V jumper cap)")
    args = parser.parse_args()

    print("=" * 60)
    print("  COGNITIVE SCENE MEMORY ROBOT — MOTOR TEST SUITE")
    print("=" * 60)
    print("PIN ASSIGNMENTS:")
    print(f"  Left Motors : IN1=GPIO {args.in1}, IN2=GPIO {args.in2}, ENA={args.ena or '5V Jumper'}")
    print(f"  Right Motors: IN3=GPIO {args.in3}, IN4=GPIO {args.in4}, ENB={args.enb or '5V Jumper'}")
    print("=" * 60)
    print("CRITICAL WIRING CHECK:")
    print("  1. 6V Battery (+) -> L298N +12V/VCC terminal")
    print("  2. 6V Battery (-) -> L298N GND terminal")
    print("  3. L298N GND -> Pi 5 GND pin (COMMON GROUND IS MANDATORY!)")
    print("=" * 60)
    print("SAFETY CHECK: Ensure robot wheels are ELEVATED off the bench!")
    input("Press ENTER when wheels are elevated and battery is switched ON...")

    motors = None
    try:
        print("\n[1/5] Initializing motor controller...")
        motors = MotorController(
            pin_in1=args.in1,
            pin_in2=args.in2,
            pin_in3=args.in3,
            pin_in4=args.in4,
            pin_ena=args.ena,
            pin_enb=args.enb,
        )
        time.sleep(0.5)

        print("[2/5] Testing FORWARD (1.5 seconds)...")
        motors.forward(speed=0.6)
        time.sleep(1.5)
        motors.stop()
        time.sleep(1.0)

        print("[3/5] Testing BACKWARD (1.5 seconds)...")
        motors.backward(speed=0.6)
        time.sleep(1.5)
        motors.stop()
        time.sleep(1.0)

        print("[4/5] Testing PIVOT LEFT (Counter-Clockwise, 1.0 second)...")
        motors.pivot_left(speed=0.6)
        time.sleep(1.0)
        motors.stop()
        time.sleep(1.0)

        print("[5/5] Testing PIVOT RIGHT (Clockwise, 1.0 second)...")
        motors.pivot_right(speed=0.6)
        time.sleep(1.0)
        motors.stop()

        print("\n" + "=" * 60)
        print(">> MOTOR TEST COMPLETED SUCCESSFULLY!")
        print("Verification:")
        print("  - Did all wheels spin forward during FORWARD?")
        print("  - If any wheel spins backwards, simply swap its two motor wires on the L298N green screw terminal!")
        print("=" * 60)

    except KeyboardInterrupt:
        print("\n[!] Emergency stop requested by user.")
    except Exception as e:
        print(f"\n[!] Error during motor test: {e}")
    finally:
        if motors:
            motors.stop()
            motors.close()
        print("[*] Motor driver shutdown complete. All GPIO pins cleared.")


if __name__ == "__main__":
    main()
