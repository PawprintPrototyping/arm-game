import json
import time
import structlog

from paho.mqtt import publish as mqtt
from motion.serial_base import SerialBase


class TargetScoringSerial(SerialBase):
    logger = structlog.get_logger()

    # TARGET_IDS = [1, 2, 3]
    TARGET_IDS = [2]
    COMMAND_CLEAR = "clear {index}\n"
    COMMAND_ENABLE = "enable {index}\n"
    COMMAND_DISABLE = "disable {index}\n"
    COMMAND_POLL = "poll {index}\n"
    STATE_HIT = b"1"
    STATE_UNHIT = b"0"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.command = None
        self.target_id = None
        self.score = 0

    def run(self):
        while not self.stop:
            match self.command:
                case TargetScoringSerial.COMMAND_ENABLE:
                    self.enable(self.target_id)
                case TargetScoringSerial.COMMAND_DISABLE:
                    self.disable(self.target_id)
                case TargetScoringSerial.COMMAND_CLEAR:
                    self.clear(self.target_id)
            self.command = None
            time.sleep(0.02)

            for idx in TargetScoringSerial.TARGET_IDS:
                state = self.poll(idx)
                if state:
                    self.publish_hit(idx)
                    self.clear(idx)
                time.sleep(0.06)

    def publish_hit(self, index):
        TargetScoringSerial.logger.info("Publish hit for target", target=index)
        mqtt.single(f"/targets/{index}/hit", f"hit {index}", hostname=MQTT_HOSTNAME)
        self.score += 5
        TargetScoringSerial.logger.info("Current score", score=self.score)
        mqtt.single(f"/scoreboard/digits/set_number", json.dumps({"number":self.score}), hostname=MQTT_HOSTNAME)

    def poll(self, index):
        TargetScoringSerial.logger.debug("Writing poll command", index=index)
        self.ser.write(f"poll {index}\n".encode("latin1"))
        TargetScoringSerial.logger.debug("Reading response")
        line = self.ser.read(12)
        TargetScoringSerial.logger.debug("read(12)", line=line)
        idx, cmd, state, hit = line.split()
        TargetScoringSerial.logger.debug("Target poll", index=index, hit=hit, state=state)
        if index != int(idx):
            return None
        if hit == TargetScoringSerial.STATE_HIT:
            return True
        if hit == TargetScoringSerial.STATE_UNHIT:
            return False

    def enable(self, index):
        return self.write(TargetScoringSerial.COMMAND_ENABLE.format(index=index).encode("latin1"))

    def disable(self, index):
        return self.write(TargetScoringSerial.COMMAND_DISABLE.format(index=index).encode("latin1"))

    def clear(self, index):
        return self.write(TargetScoringSerial.COMMAND_CLEAR.format(index=index).encode("latin1"))

    def poll_and_clear(self, index):
        state = self.poll(index)
        self.clear(index)
        return state
