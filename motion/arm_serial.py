import structlog
import random
import time

from serial_base import SerialBase


class ArmSerial(SerialBase):
    logger = structlog.get_logger()
    STARTUP_SCRIPT = b"""speed 100
    """
    ROBOT_LOCATIONS = ["p1", "p2", "p3", "p4", "p5", "tease1", "tease2"]

    IDLE = "idle"
    PARK = "park"
    ACTIVE = "active"
    ESTOP = "estop"

    def __init__(self, *args, **kwargs):
        ArmSerial.logger.debug("Opening robot serial", args=args, kwargs=kwargs)
        super().__init__(*args, **kwargs)
        self.state = ArmSerial.IDLE
        self.location = None

    def setup(self):
        self.assert_ash_prompt()
        self.write(ArmSerial.STARTUP_SCRIPT)

    def get_random_location(self):
        new_location = self.location
        while self.location == new_location:
            new_location = random.choice(ArmSerial.ROBOT_LOCATIONS)
        self.location = new_location
        return new_location

    def run(self):
        while not self.stop:
            match self.state:
                case ArmSerial.ACTIVE:
                    self.finish(self.get_random_location())
                case ArmSerial.PARK:
                    # Move to the final resting position and transition state to idle
                    self.finish("p3")
                    self.state = ArmSerial.IDLE
            time.sleep(0.05)

    def assert_ash_prompt(self):
        self.ser.write(b'\n')
        prompt = self.ser.readline()
        ArmSerial.logger.info("assert_ash_prompt readline()", prompt=prompt)
        prompt += self.ser.read(6)
        ArmSerial.logger.info("assert_ash_prompt readline()", prompt=prompt)
        if prompt != b"\r\ntest> ":
            print(f"Not in an ash!  (got '{prompt}' but expected 'test> ')")
            assert False
        assert True

    def poll_position(self):
        # Check to see if the missile knows where it is
        # (commanded position matches current position)
        pass

    def check_estop(self, message):
        if b'Arm power is OFF\r\n' in message:
            ArmSerial.logger.error("Unable to move, Arm power is OFF!")
            ArmSerial.logger.info("Setting state to ESTOP")
            self.state = ArmSerial.ESTOP
            # At this point, these extra signal messages will mess up our prompt and command echo,
            # so we'll need to clear the message buffer and assert an ash prompt again:
            self.ser.reset_input_buffer()
            while self.ser.in_waiting != 0:
                self.readline()
                time.sleep(0.5)

            try:
                self.assert_ash_prompt()
            except AssertionError:
                pass
            return True, message
        return False, message


    def move(self, location):
        if type(location) == list:
            for loc in location:
                self.check_estop(self.write(f"move {loc}\n".encode('latin1')))
        self.check_estop(self.write(f"move {location}\n".encode('latin1')))

    def finish(self, location):
        prompt = self.write(f"move {location}\n".encode('latin1'))
        state, message = self.check_estop(prompt)
        if state:
            return

        #assert prompt.endswith(f"move {location}\r\n".encode('latin1'))
        self.write(b"finish\n")
        prompt = b""
        while prompt != b"test> ":
            prompt += self.ser.read()
            estop, message = self.check_estop(prompt)
            if estop:
                break
        ArmSerial.logger.info("read()", prompt=prompt)

    def close(self):
        self.ser.close()
