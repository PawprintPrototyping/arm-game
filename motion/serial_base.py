import threading
import serial
import structlog


class SerialBase(object):
    logger = structlog.get_logger()

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
        SerialBase.logger.debug("write", data=data)
        self.ser.write(data)
        return self.readline()

    def readline(self):
        line = self.ser.readline()
        SerialBase.logger.debug("readline", line=line)
        return line

    def close(self):
        self.ser.close()
