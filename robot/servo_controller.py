"""
MG90S Servo controller for Raspberry Pi 5.
Uses AngularServo from gpiozero backed by lgpio.
Supports auto-detaching to eliminate jitter, buzz, and current drain when stationary.
"""

import time
from gpiozero import AngularServo


class ServoController:
    """Controls the MG90S camera mount servo on Raspberry Pi 5."""

    def __init__(
        self,
        pin: int = 12,
        min_angle: float = 0,
        max_angle: float = 180,
        min_pulse_width: float = 0.0006,  # 600 microseconds (safe conservative limit)
        max_pulse_width: float = 0.0024,  # 2400 microseconds (safe conservative limit)
    ):
        """
        Initialize servo on BCM GPIO pin (default: GPIO 12 / Physical Pin 32).
        Pulse widths are tuned for MG90S to prevent grinding against internal hard stops.
        """
        self.pin = pin
        self.min_angle = min_angle
        self.max_angle = max_angle
        self.servo = AngularServo(
            pin,
            min_angle=min_angle,
            max_angle=max_angle,
            min_pulse_width=min_pulse_width,
            max_pulse_width=max_pulse_width,
        )
        self.current_angle = 90.0
        self.center()

    def set_angle(self, angle: float, settle_time: float = 0.4, detach: bool = True) -> None:
        """
        Move servo to specified angle (0 to 180 degrees).
        If detach is True, disables PWM output after movement to prevent buzzing and jitter.
        """
        bounded_angle = max(self.min_angle, min(self.max_angle, angle))
        self.servo.angle = bounded_angle
        self.current_angle = bounded_angle
        time.sleep(settle_time)

        if detach:
            # Setting angle to None releases the PWM signal
            self.servo.angle = None

    def center(self) -> None:
        """Center the servo (90 degrees)."""
        self.set_angle(90.0)

    def close(self) -> None:
        """Safely release the servo resource."""
        try:
            self.servo.angle = None
            self.servo.close()
        except Exception:
            pass
