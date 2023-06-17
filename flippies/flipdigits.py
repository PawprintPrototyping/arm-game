import time
import random

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

def set_digit(address, number):
    digit = DIGITS[number]
    print(f"Write: 0x80 0x89 {address:>08b} {digit:>08b} 0x8f")
    ser.write([0x80,0x89, address, digit, 0x8f])

def clear():
    #       START,   SET   ALL    0     END
    ser.write([0x80, 0x89, 0xff, 0x00, 0x8f])


def set_number(number: int, delay=0):
    if number > 9999:
        number = 9999
    digits = [ int(d) for d in f"{number:04}" ]
    digits.reverse()
    for address, d in enumerate(digits):
        set_digit(address, d)
        time.sleep(delay)

def marquee(delay=0.1):
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
        ser.write([0x80, 0x89, addr, bits, 0x8f])
        time.sleep(delay)


if __name__ == "__main__":
    ser = Serial(DEVICE, BAUDRATE)
    set_number(8888)
    clear()
    while True:
        inp = input("> ")
        if inp == "":
            clear()
        elif inp == "m":
            marquee(0.25)
            marquee(0.05)
        elif inp == "q":
            ser.close()
            exit()
        else:
            set_number(int(inp), 0.1)
        #set_number(random.randint(0, 9999))
        #time.sleep(1)
    
