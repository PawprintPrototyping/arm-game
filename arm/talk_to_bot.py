import json
import logging
import os
import random
import sys
import threading
import time

import serial
import structlog
from paho.mqtt import publish as mqtt

logger = structlog.get_logger()

DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")

if DEBUG:
    logging.basicConfig(level=logging.DEBUG)
log = structlog.getLogger(__name__)


ROBOT_DEVICE = os.environ.get(
    "DEVICE",
    "/dev/serial/by-id/usb-Prolific_Technology_Inc._USB-Serial_Controller-if00-port0",
)
ROBOT_BAUDRATE = int(os.environ.get("BAUDRATE", "38400"))

TARGETS_DEVICE = os.environ.get(
    "TARGETS_DEVICE", "/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A50285BI-if00-port0"
)
TARGETS_BAUDRATE = int(os.environ.get("TARGETS_BAUDRATE", "9600"))
MQTT_HOSTNAME = os.environ.get("MQTT_HOST", "arm-display")

STARTUP_SCRIPT = b"""speed 100
"""

ROBOT_LOCATIONS = ["p1", "p2", "p3", "p4", "p5"]
TARGET_IDS = [1, 2, 3]


class SerialBase(object):
    def __init__(self, *args, **kwargs):
        self.ser = serial.Serial(*args, **kwargs)
        self.stop = False
        self.thread = threading.Thread(target=self.run)

    def __enter__(self, *args, **kwargs):
        return self

    def __exit__(self, *args, **kwargs):
        self.ser.close()

    def run(self):
        pass

    def write(self, data):
        logger.info("write", data=data)
        self.ser.write(data)
        return self.readline()

    def readline(self):
        line = self.ser.readline()
        logger.info("readline", line=line)
        return line


class TargetSerial(SerialBase):
    COMMAND_CLEAR = b"clear \n"
    COMMAND_ENABLE = b"enable {index}\n"
    COMMAND_DISABLE = b"disable {index}\n"
    COMMAND_POLL = b"poll {index}\n"
    STATE_HIT = b"hit"
    STATE_UNHIT = b"unhit"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.command = None
        self.target_id = None

    def run(self):
        while not self.stop:
            match self.command:
                case TargetSerial.COMMAND_ENABLE:
                    self.enable(self.target_id)
                case TargetSerial.COMMAND_DISABLE:
                    self.disable(self.target_id)
                case TargetSerial.COMMAND_CLEAR:
                    self.clear(self.target_id)
            self.command = None
            time.sleep(0.02)

            for idx in TARGET_IDS:
                state = self.poll(idx)
                if state:
                    self.publish_hit(idx)
                time.sleep(0.02)

    def publish_hit(self, index):
        mqtt.single(f"/targets/{index}/hit", b"", hostname=MQTT_HOSTNAME)

    def poll(self, index):
        self.write(f"poll {index}".encode("latin1"))
        line = self.readline()
        logger.info(line)
        idx, cmd, state, hit = line.split()
        logger.debug("Target poll", index=index, hit=hit)
        if index != idx:
            return None
        if hit == TargetSerial.STATE_HIT:
            return True
        if hit == TargetSerial.STATE_UNHIT:
            return False

    def enable(self, index):
        self.write(TargetSerial.COMMAND_ENABLE.format(index=index))
        return self.readline()

    def disable(self, index):
        self.write(TargetSerial.COMMAND_DISABLE.format(index=index))
        return self.readline()

    def clear(self, index):
        self.write(TargetSerial.COMMAND_CLEAR.format(index=index))
        return self.readline()

    def poll_and_clear(self, index):
        state = self.poll(index)
        self.clear(index)
        return state


class RobotSerial(SerialBase):
    IDLE = "idle"
    ACTIVE = "active"

    def __init__(self, *args, **kwargs):
        log.debug("Opening robot serial", args=args, kwargs=kwargs)
        super().__init__(*args, **kwargs)
        self.state = RobotSerial.IDLE
        self.location = None

    def setup(self):
        self.assert_ash_prompt()
        self.write(STARTUP_SCRIPT)

    def get_random_location(self):
        new_location = self.location
        while self.location == new_location:
            new_location = random.choice(ROBOT_LOCATIONS)
        self.location = new_location
        return new_location

    def run(self):
        while not self.stop:
            match self.state:
                case RobotSerial.ACTIVE:
                    self.finish(self.get_random_location())
            time.sleep(0.05)

    def assert_ash_prompt(self):
        self.ser.write(b'\n')
        prompt = self.ser.readline()
        logger.info("assert_ash_prompt readline()", prompt=prompt)
        prompt += self.ser.read(6)
        logger.info("assert_ash_prompt readline()", prompt=prompt)
        if prompt != b"\r\ntest> ":
            print(f"Not in an ash!  (got '{prompt}' but expected 'test> ')")
            assert False
        assert True

    def poll_position(self):
        # Check to see if the missile knows where it is
        # (commanded position matches current position)
        pass

    def move(self, location):
        if type(location) == list:
            for loc in location:
                self.write(f"move {loc}\n".encode('latin1'))
        self.write(f"move {location}\n".encode('latin1'))

    def finish(self, location):
        prompt = self.write(f"move {location}\n".encode('latin1'))
        if prompt == b'S: Arm power is OFF\r\n':
            log.error("Unable to move, Arm power is OFF!")
            self.state = RobotSerial.IDLE
            return

        assert prompt.endswith(f"move {location}\r\n".encode('latin1'))
        self.write(b"finish\n")
        prompt = b""
        while prompt != b"test> ":
            prompt += self.ser.read()
        logger.info("read()", prompt=prompt)

    def close(self):
        self.ser.close()


def increment_flippies(score: int):
    mqtt.single("/scoreboard/digits/set_number", json.dumps({"number":score}), hostname="arm-display")

if __name__ == "__main__":
    #with TargetSerial(TARGETS_DEVICE, TARGETS_BAUDRATE, timeout=10) as ts:
    #    while True:
    #        state = ts.poll(1)
    #        time.sleep(0.5)
    
    with RobotSerial(ROBOT_DEVICE, ROBOT_BAUDRATE, timeout=30) as rs:
        rs.assert_ash_prompt()
        rs.write(STARTUP_SCRIPT)
        
        locations = list(ROBOT_LOCATIONS*5)
        random.shuffle(locations)
        for location in locations:
            rs.finish(location)
 
        rs.finish(ROBOT_LOCATIONS[-1])
