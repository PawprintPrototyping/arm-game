import time

from serial_base import SerialBase


class TargetMovementSerial(SerialBase):
    START_COMMAND = "start"
    STOP_COMMAND = "stop"

    START_SERIAL_COMMAND = "start\n"
    STOP_SERIAL_COMMAND = "stop\n"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.command = None

    def run(self):
        while not self.stop:
            match self.command:
                case TargetMovementSerial.START_COMMAND:
                    self.write(TargetMovementSerial.START_SERIAL_COMMAND)
                case TargetMovementSerial.STOP_COMMAND:
                    self.write(TargetMovementSerial.STOP_SERIAL_COMMAND)

            self.command = None
            time.sleep(0.05)

        # Go to idle before shutdown
        self.write("stop\n")
