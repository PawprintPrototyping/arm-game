import time
import random

import structlog
from serial import Serial

DEVICE="/dev/ttyUSB4"
BAUDRATE=57600

"""
    0
   ___
5 |   | 1
6  ___ 
4 |   | 2
   ___
    3
"""

DIGITS = [
    0b0111111, # 0 
    0b0000110, # 1
    0b1011011, # 2
    0b1001111, # 3
    0b1100110, # 4
    0b1101101, # 5
    0b1111101, # 6
    0b0000111, # 7
    0b1111111, # 8
    0b1100111, # 9
]

log = structlog.getLogger(__name__)

class FlipDigits(object):
    def __init__(self, *args, **kwargs):
        self._debug = kwargs.get("debug")
        if self._debug:
            self.ser = open("/dev/null")
        else:
            self.ser = Serial(*args, **kwargs)

    def set_digit(self, address: int, number: int):
        digit = DIGITS[number]
        log.debug(f"write: 0x80 0x89 {address:>08b} {digit:>08b} 0x8f", address=address, digit=digit)
        self.ser.write([0x80, 0x89, address, digit, 0x8f])

    def write(self, data):
        log.debug(f"write: {data}", data=data)
        return self.ser.write(data)

    def clear(self):
        log.info("Clear display")
        #          START, SET   ALL    0     END
        self.write([0x80, 0x89, 0xff, 0x00, 0x8f])

    def set_number(self, number: int, delay=0):
        log.debug("set_number", number=number, delay=delay)
        if number > 9999:
            number = 9999
        digits = [ int(d) for d in f"{number:04}" ]
        digits.reverse()
        for address, d in enumerate(digits):
            self.set_digit(address, d)
            time.sleep(delay)

    def marquee(self, delay=0.1):
        log.debug("marquee()", delay=delay)
        SEQ = (
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

        for addr, bits in SEQ:
            self.write([0x80, 0x89, addr, bits, 0x8f])
            time.sleep(delay)


if __name__ == "__main__":
    fd = FlipDigits(DEVICE, BAUDRATE)
    fd.set_number(8888)
    fd.clear()
    while True:
        inp = input("> ")
        if inp == "":
            fd.clear()
        elif inp == "m":
            fd.marquee(0.25)
            fd.marquee(0.05)
        elif inp == "q":
            fd.ser.close()
            exit()
        else:
            fd.set_number(int(inp), 0.1)
        #fd.set_number(random.randint(0, 9999))
        #time.sleep(1)
    
