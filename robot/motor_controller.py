"""
Motor controller for 4-wheel mobile chassis using L298N Dual H-Bridge.
Compatible with Raspberry Pi 5 using gpiozero (lgpio).
Supports both 4-wire mode (with L298N 5V jumper caps on ENA/ENB) and 6-wire PWM mode.
"""

import time
from typing import Optional
from gpiozero import OutputDevice, PWMOutputDevice


class MotorController:
    """
    Controls 4 DC geared motors paired into 2 channels via an L298N:
      - Left Channel:  OUT1, OUT2 (IN1 = GPIO 17, IN2 = GPIO 27, optional ENA = GPIO 18)
      - Right Channel: OUT3, OUT4 (IN3 = GPIO 22, IN4 = GPIO 23, optional ENB = GPIO 13)
    """

    def __init__(
        self,
        pin_in1: int = 17,
        pin_in2: int = 27,
        pin_in3: int = 22,
        pin_in4: int = 23,
        pin_ena: Optional[int] = None,
        pin_enb: Optional[int] = None,
        turn_90_duration: float = 0.65,  # Tune for floor friction and battery charge
    ):
        self.in1 = OutputDevice(pin_in1)
        self.in2 = OutputDevice(pin_in2)
        self.in3 = OutputDevice(pin_in3)
        self.in4 = OutputDevice(pin_in4)

        self.ena = PWMOutputDevice(pin_ena, frequency=100) if pin_ena is not None else None
        self.enb = PWMOutputDevice(pin_enb, frequency=100) if pin_enb is not None else None

        self.turn_90_duration = turn_90_duration
        self.stop()

    def set_left_motor(self, speed: float) -> None:
        """
        Set left motor speed and direction.
        speed: -1.0 (full reverse) to +1.0 (full forward), 0 is stop.
        """
        speed = max(-1.0, min(1.0, speed))
        if self.ena is not None:
            self.ena.value = abs(speed)

        if speed > 0:
            self.in1.on()
            self.in2.off()
        elif speed < 0:
            self.in1.off()
            self.in2.on()
        else:
            self.in1.off()
            self.in2.off()

    def set_right_motor(self, speed: float) -> None:
        """
        Set right motor speed and direction.
        speed: -1.0 (full reverse) to +1.0 (full forward), 0 is stop.
        """
        speed = max(-1.0, min(1.0, speed))
        if self.enb is not None:
            self.enb.value = abs(speed)

        if speed > 0:
            self.in3.on()
            self.in4.off()
        elif speed < 0:
            self.in3.off()
            self.in4.on()
        else:
            self.in3.off()
            self.in4.off()

    def forward(self, speed: float = 0.6) -> None:
        """Drive straight forward."""
        self.set_left_motor(speed)
        self.set_right_motor(speed)

    def backward(self, speed: float = 0.6) -> None:
        """Drive straight backward."""
        self.set_left_motor(-speed)
        self.set_right_motor(-speed)

    def pivot_left(self, speed: float = 0.6) -> None:
        """Pivot on the spot counter-clockwise (Left reverse, Right forward)."""
        self.set_left_motor(-speed)
        self.set_right_motor(speed)

    def pivot_right(self, speed: float = 0.6) -> None:
        """Pivot on the spot clockwise (Left forward, Right reverse)."""
        self.set_left_motor(speed)
        self.set_right_motor(-speed)

    def stop(self) -> None:
        """Brake and stop all motors immediately."""
        self.set_left_motor(0.0)
        self.set_right_motor(0.0)

    def pivot_90(self, direction: str = "right", speed: float = 0.6) -> None:
        """
        Execute an on-the-spot 90-degree turn.
        direction: 'right' (clockwise) or 'left' (counter-clockwise).
        """
        if direction.lower() == "left":
            self.pivot_left(speed)
        else:
            self.pivot_right(speed)

        time.sleep(self.turn_90_duration)
        self.stop()
        time.sleep(0.3)  # Allow chassis momentum to settle

    def close(self) -> None:
        """Release all PWM and GPIO lines safely."""
        self.stop()
        if self.ena is not None:
            self.ena.close()
        self.in1.close()
        self.in2.close()
        if self.enb is not None:
            self.enb.close()
        self.in3.close()
        self.in4.close()
