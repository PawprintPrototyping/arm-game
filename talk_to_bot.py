import os
import serial
import random

DEVICE = os.environ.get("DEVICE", "/dev/ttyUSB0")
BAUDRATE = int(os.environ.get("BAUDRATE", "38400"))

STARTUP_SCRIPT = b"""speed 100
"""

ROBOT_LOCATIONS = ["p1", "p2", "p3", "p4", "p5"]

class RobotSerial(object):
    def __init__(self, *args, **kwargs):
        self.ser = serial.Serial(*args, **kwargs)


    def __enter__(self, *args, **kwargs):
        return self

    def __exit__(self, *args, **kwargs):
        self.ser.close()


    def write(self, data): 
        print("<", data)
        self.ser.write(data)
        return self.readline()

    def readline(self):
        line = self.ser.readline()
        print(">", line)
        return line


    def assert_ash_prompt(self): 
        self.ser.write(b'\n')
        prompt = self.ser.readline()
        prompt += self.ser.readline()
        if prompt != b"\r\ntest> ":
            print(f"Not in an ash!  (got '{prompt}' but expected 'test> ')")
            assert False
        assert True


    def poll_position(self):
        # Check to see if the missile knows where it is
        # (commanded position matches current position)
        pass


    def move(self, location):
        self.write(f"move {location}\n".encode('latin1'))

    def finish(self, location):
        prompt = self.write(f"move {location}\n".encode('latin1'))
        assert prompt.endswith(f"move {location}\r\n".encode('latin1'))
        prompt = self.write(b"finish\n")
        while prompt != b"test> ":
            prompt = self.readline()
            print(prompt)


    def close(self):
        self.ser.close()


if __name__ == "__main__":
    with RobotSerial(DEVICE, BAUDRATE, timeout=0.5) as rs:
        rs.assert_ash_prompt()
        rs.write(STARTUP_SCRIPT)
        
        locations = ROBOT_LOCATIONS
        random.shuffle(locations)
        for location in ROBOT_LOCATIONS:
            rs.finish(location)

        rs.finish(ROBOT_LOCATIONS[-1])
