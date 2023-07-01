import random
import threading
import time
from io import BytesIO

import serial
import structlog
from serial import Serial

DEVICE = "/dev/ttyUSB0"
BAUDRATE = 57600

"""
    0
   ___
5 |   | 1
6  ___
4 |   | 2
   ___
    3
"""

DIGITS = (
    0b0111111,  # 0
    0b0000110,  # 1
    0b1011011,  # 2
    0b1001111,  # 3
    0b1100110,  # 4
    0b1101101,  # 5
    0b1111101,  # 6
    0b0000111,  # 7
    0b1111111,  # 8
    0b1100111,  # 9
)

SNAKE_SEQ = (
    (3, 0b000001),
    (2, 0b000001),
    (1, 0b000001),
    (0, 0b000001),
    (0, 0b000011),
    (0, 0b000111),
    (0, 0b001111),
    (1, 0b001001),
    (2, 0b001001),
    (3, 0b001001),
    (3, 0b011001),
    (3, 0b111001),
    (3, 0b111000),
    (2, 0b001000),
    (1, 0b001000),
    (0, 0b001110),
    (0, 0b001100),
    (0, 0b001000),
    (0, 0b000000),
    (1, 0b000000),
    (2, 0b000000),
    (3, 0b110000),
    (3, 0b100000),
    (3, 0b000000),
)

MARQUEE_SEQ = (
    # Fixme
)


log = structlog.getLogger(__name__)


class FlipDigits(object):
    def __init__(self, *args, **kwargs):
        self._debug = kwargs.pop("debug")
        self.stop = False
        self.delay_thread = threading.Thread()
        if self._debug:
            self.ser = serial.serial_for_url("loop://")
        else:
            self.ser = Serial(*args, **kwargs)

    def close(self):
        self.ser.close()

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.ser.close()

    def set_digit(self, address: int, number: int):
        digit = DIGITS[number]
        log.debug(
            f"write: 0x80 0x89 {address:>08b} {digit:>08b} 0x8f",
            address=address,
            digit=digit,
        )
        self.ser.write([0x80, 0x89, address, digit, 0x8F])

    def write(self, data):
        log.debug(f"write: {data}", data=data)
        return self.ser.write(data)

    def clear(self):
        log.info("Clear display")
        #          START, SET   ALL    0     END
        self.write([0x80, 0x89, 0xFF, 0x00, 0x8F])

    def set_number(self, number: int, delay=0, callback=None):
        log.debug("set_number", number=number, delay=delay)
        if number > 9999:
            number = 9999
        digits = [int(d) for d in f"{number:04}"]
        digits.reverse()
        for address, d in enumerate(digits):
            self.set_digit(address, d)
            if self.stop:
                self.stop = False
                break
            time.sleep(delay)
        if callback:
            callback()

    def snake(self, delay=0.1, callback=None):
        log.debug("snake()", delay=delay)
        for addr, bits in SNAKE_SEQ:
            if self.stop:
                self.stop = False
                break
            self.write([0x80, 0x89, addr, bits, 0x8F])
            time.sleep(delay)
        if callback:
            callback()


if __name__ == "__main__":
    fd = FlipDigits(DEVICE, BAUDRATE)
    fd.set_number(8888)
    fd.clear()
    while True:
        inp = input("> ")
        if inp == "":
            fd.clear()
        elif inp == "m":
            fd.snake(0.25)
            fd.snake(0.05)
        elif inp == "q":
            fd.ser.close()
            exit()
        else:
            fd.set_number(int(inp), 0.1)
