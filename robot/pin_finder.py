#!/usr/bin/env python3
"""
Cognitive Scene Memory — Interactive GPIO Pin Diagnostic & Finder Tool
Quickly identify which physical GPIO pins your L298N motors and Servo are connected to!
"""

import sys
import time
from gpiozero import OutputDevice, AngularServo

COMMON_PINS = [17, 27, 22, 23, 18, 13, 12, 5, 6, 16, 20, 21, 26, 24, 25, 4]


def test_single_motor_pin(pin: int):
    """Pulses a GPIO high for 0.8 seconds to see which motor spins."""
    print(f"\n[*] Pulsing GPIO {pin} HIGH for 0.8 seconds...")
    try:
        dev = OutputDevice(pin)
        dev.on()
        time.sleep(0.8)
        dev.off()
        dev.close()
        print(f"[✓] Finished pulsing GPIO {pin}.")
    except Exception as e:
        print(f"[!] Error on GPIO {pin}: {e}")


def test_servo_pin(pin: int):
    """Tests if a pin is connected to the MG90S servo signal."""
    print(f"\n[*] Testing GPIO {pin} as Servo PWM signal...")
    try:
        servo = AngularServo(pin, min_angle=0, max_angle=180, min_pulse_width=0.0006, max_pulse_width=0.0024)
        print("  -> Moving to 45°...")
        servo.angle = 45
        time.sleep(0.6)
        print("  -> Moving to 135°...")
        servo.angle = 135
        time.sleep(0.6)
        print("  -> Centering to 90°...")
        servo.angle = 90
        time.sleep(0.6)
        servo.angle = None  # Detach
        servo.close()
        print(f"[✓] Finished servo test on GPIO {pin}.")
    except Exception as e:
        print(f"[!] Error on GPIO {pin}: {e}")


def main():
    print("=" * 65)
    print("  COGNITIVE SCENE MEMORY — GPIO PIN IDENTIFIER & DIAGNOSTIC")
    print("=" * 65)
    print("SAFETY: Elevate the car wheels so it cannot drive off the table!")
    print("This tool lets you test pins one-by-one to discover your exact wiring.")
    print("=" * 65)

    while True:
        print("\nChoose an option:")
        print("  [1] Test a specific pin for a Motor (Pulse HIGH for 0.8s)")
        print("  [2] Test a specific pin for the Servo (Pan 45° -> 135° -> 90°)")
        print("  [3] Auto-scan common motor pins (GPIO 17, 27, 22, 23, 24, 25)")
        print("  [4] Show Pi 5 40-Pin Header Reference Map")
        print("  [Q] Exit")

        choice = input("\nEnter choice [1/2/3/4/Q]: ").strip().lower()

        if choice == 'q':
            print("Exiting.")
            break

        elif choice == '1':
            pin_str = input("Enter BCM GPIO pin number to pulse (e.g. 17): ").strip()
            if pin_str.isdigit():
                test_single_motor_pin(int(pin_str))
            else:
                print("Invalid number.")

        elif choice == '2':
            pin_str = input("Enter BCM GPIO pin number for Servo (e.g. 12): ").strip()
            if pin_str.isdigit():
                test_servo_pin(int(pin_str))
            else:
                print("Invalid number.")

        elif choice == '3':
            print("\nScanning common pins (watch which wheel moves):")
            for p in [17, 27, 22, 23, 24, 25]:
                print(f"\n--- Ready to test GPIO {p} ---")
                input(f"Press ENTER to pulse GPIO {p} (or Ctrl+C to stop)...")
                test_single_motor_pin(p)

        elif choice == '4':
            print("\n" + "=" * 60)
            print("  RASPBERRY PI 5 — 40-PIN HEADER REFERENCE (BCM vs PHYSICAL)")
            print("=" * 60)
            print("  Pin  1: 3.3V Power         |  Pin  2: 5V Power (Servo Red)")
            print("  Pin  3: GPIO 2 (SDA)       |  Pin  4: 5V Power")
            print("  Pin  5: GPIO 3 (SCL)       |  Pin  6: GND (L298N/Servo GND)")
            print("  Pin  7: GPIO 4             |  Pin  8: GPIO 14 (TX)")
            print("  Pin  9: GND                |  Pin 10: GPIO 15 (RX)")
            print("  Pin 11: GPIO 17 (Def IN1)  |  Pin 12: GPIO 18 (PWM)")
            print("  Pin 13: GPIO 27 (Def IN2)  |  Pin 14: GND")
            print("  Pin 15: GPIO 22 (Def IN3)  |  Pin 16: GPIO 23 (Def IN4)")
            print("  Pin 17: 3.3V Power         |  Pin 18: GPIO 24")
            print("  Pin 19: GPIO 10 (MOSI)     |  Pin 20: GND")
            print("  Pin 21: GPIO 9 (MISO)      |  Pin 22: GPIO 25")
            print("  Pin 23: GPIO 11 (SCLK)     |  Pin 24: GPIO 8 (CE0)")
            print("  Pin 25: GND                |  Pin 26: GPIO 7 (CE1)")
            print("  Pin 27: GPIO 0             |  Pin 28: GPIO 1")
            print("  Pin 29: GPIO 5 (LCD RS)    |  Pin 30: GND")
            print("  Pin 31: GPIO 6 (LCD E)     |  Pin 32: GPIO 12 (Def Servo)")
            print("  Pin 33: GPIO 13 (PWM)      |  Pin 34: GND")
            print("  Pin 35: GPIO 19            |  Pin 36: GPIO 16 (LCD D4)")
            print("  Pin 37: GPIO 26 (LCD D7)   |  Pin 38: GPIO 20 (LCD D5)")
            print("  Pin 39: GND                |  Pin 40: GPIO 21 (LCD D6)")
            print("=" * 60)


if __name__ == "__main__":
    main()
