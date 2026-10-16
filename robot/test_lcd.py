#!/usr/bin/env python3
"""
Task 5 Commissioning Script: JHD162A 16x2 Character LCD Test (4-Bit Mode)
Verifies HD44780 4-bit communication and contrast setup.
"""

import time
from lcd_driver import LCD1602


def run_lcd_test():
    print("=" * 60)
    print("  COGNITIVE SCENE MEMORY ROBOT — LCD DISPLAY TEST")
    print("=" * 60)
    print("SAFETY REMINDER: Pin 5 (R/W) must be tied directly to GND!")
    print("If text is not visible, slowly turn the 10k potentiometer on Pin 3 (VO)")
    print("until dark, crisp characters appear against the background.")
    print("=" * 60)

    lcd = None
    try:
        print("\n[1/3] Initializing LCD in 4-bit mode on GPIO 5, 6, 16, 20, 21, 26...")
        lcd = LCD1602()
        time.sleep(0.5)

        print("[2/3] Writing static greeting...")
        lcd.write_message("Cognitive Scene", "Memory Robot OK")
        time.sleep(3.0)

        print("[3/3] Cycling status display test...")
        messages = [
            ("Status: IDLE", "Ready for scan"),
            ("Motors: STOPPED", "Battery: 6x AA"),
            ("Camera: READY", "Servo: CENTER"),
            ("System Ready", "Awaiting commands"),
        ]

        for line1, line2 in messages:
            lcd.write_message(line1, line2)
            print(f"  [LCD Output] Line 1: '{line1}' | Line 2: '{line2}'")
            time.sleep(2.0)

        print("\n" + "=" * 60)
        print(">> LCD TEST COMPLETED SUCCESSFULLY!")
        print("=" * 60)

    except KeyboardInterrupt:
        print("\n[!] Test stopped by user.")
    except Exception as e:
        print(f"\n[!] Error during LCD test: {e}")
    finally:
        if lcd:
            lcd.write_message("Test Completed", "LCD Standing By")
            # Keep message on screen; do not close/clear immediately
        print("[*] LCD driver test finished.")


if __name__ == "__main__":
    run_lcd_test()
