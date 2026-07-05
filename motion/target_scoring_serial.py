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

# Remove a target if we haven't heard from it in this amount of time
LAST_HEARD_THRESHOLD_SECONDS = 1


class TargetScoringSerial(SerialBase):
    TARGET_IDS = [3, 5, 7]
    #TARGET_IDS = [1, 2, 4, 6, 7]
    TARGET_ERRORS = dict.fromkeys(TARGET_IDS, {"count": 0, "last_error": time.time(), "last_heard": 0, "rate": 0})
    COMMAND_CLEAR = "clear {index}\n"
    COMMAND_ENABLE = "enable {index}\n"
    COMMAND_DISABLE = "disable {index}\n"
    COMMAND_POLL = "poll {index}\n"
    COMMAND_HOME = "home {index}\n"
    COMMAND_UP = "up {index}\n"
    COMMAND_DOWN = "down {index}\n"
    STATE_HIT = b"1"
    STATE_UNHIT = b"0"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.command_queue = queue.Queue(maxsize=20)
        self.command = None
        self.target_id = None
        self.score = 0
        self.player_info = {"name": "NO NAME"}

    def enqueue(self, command, target_id):
        if int(target_id) not in self.TARGET_IDS:
            logger.warn(f"Target ID {target_id} not found")
            return
        try:
            self.command_queue.put_nowait({"command": command, "target_id": target_id})
        except queue.Full:
            logging.warning("Target serial command queue is full!")

    def run(self):
        while not self.stop:
            try:
                cmd = self.command_queue.get_nowait()
            except queue.Empty:
                cmd = {"command": None}

            match cmd["command"]:
                case TargetScoringSerial.COMMAND_ENABLE:
                    self.enable(cmd["target_id"])
                case TargetScoringSerial.COMMAND_DISABLE:
                    self.disable(cmd["target_id"])
                case TargetScoringSerial.COMMAND_CLEAR:
                    self.clear(cmd["target_id"])
                case TargetScoringSerial.COMMAND_HOME:
                    self.home(cmd["target_id"])
                case TargetScoringSerial.COMMAND_UP:
                    self.up(cmd["target_id"])
                case TargetScoringSerial.COMMAND_DOWN:
                    self.down(cmd["target_id"])
            # Load bearing sleep: if we tell the microcontroller to do too many things back to back, we think it will
            # drop subsequent messages.  See also: `max485DriverEnableDuration` in target_controller/target_stepper/src/main.cpp
            time.sleep(0.02)

            for idx in TargetScoringSerial.TARGET_IDS:
                if not self.command_queue.empty():
                    break
                state = self.poll(idx)
                if state:
                    self.publish_hit(idx)
                    self.clear(idx)
                time.sleep(0.03)

    def publish_hit(self, index):
        TargetScoringSerial.logger.info("Publish hit for target", target=index)
        mqtt.single(f"targets/{index}/hit", f"hit {index}", hostname=MQTT_HOST)
        if index == 1:
            self.score += 75
        else:
            self.score += 69
        logger.info("Current score", score=self.score)
        mqtt.single(f"scoreboard/digits/set_number", json.dumps({"number":self.score}), hostname=MQTT_HOST)

    def poll(self, index):
        TargetScoringSerial.logger.debug("Writing poll command", index=index)
        self.ser.write(f"poll {index}\n".encode("latin1"))
        TargetScoringSerial.logger.debug("Reading response")
        line = self.ser.read(14)
        TargetScoringSerial.logger.debug("read(14)", line=line)
        try:
            idx, cmd, state, hit, pos = line.split()
        except ValueError:
            logger.warn(f"Unable to unpack values ('{line}')")
            self.TARGET_ERRORS[index]["count"] += 1
            now = time.time()
            error_rate = 1 / self.TARGET_ERRORS[index]["last_error"] - now
            self.TARGET_ERRORS[index]["rate"] = (error_rate + self.TARGET_ERRORS[index]["rate"]) / 2
            self.TARGET_ERRORS[index]["last_error"] = now
            
            mqtt.single(f"target/{index}/errors", json.dumps(
                {"target": index, 
                "error_count": self.TARGET_ERRORS[index]["count"],
                "error_rate": self.TARGET_ERRORS[index]["rate"],
                "error_last": self.TARGET_ERRORS[index]["last_error"],
            }), hostname=MQTT_HOST)

            if now - self.TARGET_ERRORS[index]["last_error"] >= LAST_HEARD_THRESHOLD_SECONDS:
                self.TARGET_IDS.remove(index)
            return False

        #mqtt.single(f"target/{index}/healthy", json.dumps({"target": index, "response": str(line)}), hostname=MQTT_HOST)
        self.TARGET_ERRORS[index]["last_heard"] = time.time()
        logger.debug("Target poll", index=index, hit=hit, state=state, pos=pos)
        if index != int(idx):
            return None
        if hit == TargetScoringSerial.STATE_HIT:
            return True
        if hit == TargetScoringSerial.STATE_UNHIT:
            return False
        return None

    def enable(self, index):
        return self.write(TargetScoringSerial.COMMAND_ENABLE.format(index=index).encode("latin1"))

    def disable(self, index):
        return self.write(TargetScoringSerial.COMMAND_DISABLE.format(index=index).encode("latin1"))

    def clear(self, index):
        return self.write(TargetScoringSerial.COMMAND_CLEAR.format(index=index).encode("latin1"))

    def home(self, index):
        return self.write(TargetScoringSerial.COMMAND_HOME.format(index=index).encode("latin1"))

    def up(self, index):
        return self.write(TargetScoringSerial.COMMAND_UP.format(index=index).encode("latin1"))

    def down(self, index):
        return self.write(TargetScoringSerial.COMMAND_DOWN.format(index=index).encode("latin1"))

    def poll_and_clear(self, index):
        state = self.poll(index)
        self.clear(index)
        return state
