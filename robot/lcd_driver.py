"""
Pure-Python 4-bit HD44780 LCD Driver for Raspberry Pi 5.
Uses gpiozero (which works on Pi 5 via lgpio / RP1 chip).
Pin 5 (R/W) MUST be hard-wired to GND to guarantee Pi 3.3V GPIO safety.
"""

import time
from gpiozero import OutputDevice


class LCD1602:
    """Controls a standard 16x2 character LCD (HD44780 / JHD162A) in 4-bit mode."""

    # Commands
    LCD_CLEARDISPLAY = 0x01
    LCD_RETURNHOME = 0x02
    LCD_ENTRYMODESET = 0x04
    LCD_DISPLAYCONTROL = 0x08
    LCD_FUNCTIONSET = 0x20
    LCD_SETDDRAMADDR = 0x80

    # Flags for display entry mode
    LCD_ENTRYLEFT = 0x02
    LCD_ENTRYSHIFTDECREMENT = 0x00

    # Flags for display on/off control
    LCD_DISPLAYON = 0x04
    LCD_CURSOROFF = 0x00
    LCD_BLINKOFF = 0x00

    # Flags for function set
    LCD_4BITMODE = 0x00
    LCD_2LINE = 0x08
    LCD_5x8DOTS = 0x00

    def __init__(
        self,
        pin_rs: int = 5,
        pin_e: int = 6,
        pin_d4: int = 16,
        pin_d5: int = 20,
        pin_d6: int = 21,
        pin_d7: int = 26,
    ):
        """
        Initialize the LCD with BCM GPIO pin assignments.
        Default pinout:
          RS: GPIO 5  (Pin 29)
          E:  GPIO 6  (Pin 31)
          D4: GPIO 16 (Pin 36)
          D5: GPIO 20 (Pin 38)
          D6: GPIO 21 (Pin 40)
          D7: GPIO 26 (Pin 37)
        """
        self.rs = OutputDevice(pin_rs)
        self.e = OutputDevice(pin_e)
        self.data_pins = [
            OutputDevice(pin_d4),
            OutputDevice(pin_d5),
            OutputDevice(pin_d6),
            OutputDevice(pin_d7),
        ]
        self._init_lcd()

    def _pulse_enable(self) -> None:
        """Pulse the Enable line high then low with HD44780 timing."""
        self.e.off()
        time.sleep(0.000001)  # 1 microsecond
        self.e.on()
        time.sleep(0.000001)  # 1 microsecond
        self.e.off()
        time.sleep(0.00005)   # 50 microseconds

    def _write_4_bits(self, value: int) -> None:
        """Write lower 4 bits to DB4-DB7."""
        for i in range(4):
            bit = (value >> i) & 0x01
            if bit:
                self.data_pins[i].on()
            else:
                self.data_pins[i].off()
        self._pulse_enable()

    def _send(self, value: int, is_data: bool = False) -> None:
        """Send a byte in 4-bit mode (upper nibble then lower nibble)."""
        if is_data:
            self.rs.on()
        else:
            self.rs.off()

        # Send high nibble
        self._write_4_bits((value >> 4) & 0x0F)
        # Send low nibble
        self._write_4_bits(value & 0x0F)

    def send_command(self, cmd: int) -> None:
        """Send a control command to LCD."""
        self._send(cmd, is_data=False)
        time.sleep(0.002)

    def send_data(self, data: int) -> None:
        """Send a data character byte to LCD."""
        self._send(data, is_data=True)

    def _init_lcd(self) -> None:
        """Execute the standard HD44780 4-bit initialization sequence."""
        time.sleep(0.050)  # Wait >40ms after power-on
        self.rs.off()
        self.e.off()

        # Special 4-bit startup sequence
        self._write_4_bits(0x03)
        time.sleep(0.005)
        self._write_4_bits(0x03)
        time.sleep(0.005)
        self._write_4_bits(0x03)
        time.sleep(0.001)
        self._write_4_bits(0x02)  # Set to 4-bit interface

        # Function set: 4-bit, 2 lines, 5x8 font
        self.send_command(self.LCD_FUNCTIONSET | self.LCD_4BITMODE | self.LCD_2LINE | self.LCD_5x8DOTS)

        # Display control: display ON, cursor OFF, blink OFF
        self.send_command(self.LCD_DISPLAYCONTROL | self.LCD_DISPLAYON | self.LCD_CURSOROFF | self.LCD_BLINKOFF)

        # Clear display
        self.clear()

        # Entry mode: increment automatically, no display shift
        self.send_command(self.LCD_ENTRYMODESET | self.LCD_ENTRYLEFT | self.LCD_ENTRYSHIFTDECREMENT)
        time.sleep(0.002)

    def clear(self) -> None:
        """Clear LCD display and return cursor to home."""
        self.send_command(self.LCD_CLEARDISPLAY)
        time.sleep(0.003)

    def set_cursor(self, col: int, row: int) -> None:
        """Position cursor at col (0-15) and row (0-1)."""
        row_offsets = [0x00, 0x40]
        row = max(0, min(1, row))
        col = max(0, min(15, col))
        self.send_command(self.LCD_SETDDRAMADDR | (col + row_offsets[row]))

    def write_line(self, line_num: int, text: str) -> None:
        """Write a string (up to 16 characters) to row 0 or 1, padding spaces."""
        self.set_cursor(0, line_num)
        padded_text = text.ljust(16)[:16]
        for char in padded_text:
            self.send_data(ord(char))

    def write_message(self, line1: str, line2: str = "") -> None:
        """Write a 2-line message conveniently."""
        self.write_line(0, line1)
        self.write_line(1, line2)

    def close(self) -> None:
        """Clean up GPIO pins."""
        self.clear()
        self.rs.close()
        self.e.close()
        for p in self.data_pins:
            p.close()
