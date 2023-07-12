import json
import logging
import os
import queue
import time
import structlog

from paho.mqtt import publish as mqtt
from serial_base import SerialBase

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
logger = structlog.get_logger()

class TargetScoringSerial(SerialBase):


    TARGET_IDS = [1, 2, 3]
    COMMAND_CLEAR = "clear {index}\n"
    COMMAND_ENABLE = "enable {index}\n"
    COMMAND_DISABLE = "disable {index}\n"
    COMMAND_POLL = "poll {index}\n"
    STATE_HIT = b"1"
    STATE_UNHIT = b"0"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.command_queue = queue.Queue(maxsize=20)
        self.command = None
        self.target_id = None
        self.score = 0

    def enqueue(self, command, target_id):
        try:
            self.queue.put_nowait({"command": command, "target_id": target_id})
        except queue.Full:
            logging.warning("Target serial command queue is full!")

    def run(self):
        while not self.stop:
            try:
                cmd = self.command_queue.get_nowait()
            except queue.Empty:
                cmd = None

            match cmd["command"]:
                case TargetScoringSerial.COMMAND_ENABLE:
                    self.enable(cmd["target_id"])
                case TargetScoringSerial.COMMAND_DISABLE:
                    self.disable(cmd["target_id"])
                case TargetScoringSerial.COMMAND_CLEAR:
                    self.clear(cmd["target_id"])
            time.sleep(0.02)

            for idx in TargetScoringSerial.TARGET_IDS:
                if self.command_queue.not_empty():
                    break
                state = self.poll(idx)
                if state:
                    self.publish_hit(idx)
                    self.clear(idx)
                time.sleep(0.06)

    def publish_hit(self, index):
        TargetScoringSerial.logger.info("Publish hit for target", target=index)
        mqtt.single(f"/targets/{index}/hit", f"hit {index}", hostname=MQTT_HOST)
        if index == 2:
            self.score += 75
        else:
            self.score += 69
        logger.info("Current score", score=self.score)
        mqtt.single(f"/scoreboard/digits/set_number", json.dumps({"number":self.score}), hostname=MQTT_HOST)

    def poll(self, index):
        TargetScoringSerial.logger.debug("Writing poll command", index=index)
        self.ser.write(f"poll {index}\n".encode("latin1"))
        TargetScoringSerial.logger.debug("Reading response")
        line = self.ser.read(12)
        TargetScoringSerial.logger.debug("read(12)", line=line)
        idx, cmd, state, hit = line.split()
        logger.debug("Target poll", index=index, hit=hit, state=state)
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
