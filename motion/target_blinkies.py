import logging
import os
import threading
import time
import random

import structlog
from paho.mqtt import publish as mqtt

from target_scoring_serial import TargetScoringSerial

CHANCE_DOUBLE_SCORE = 0.2

logger = structlog.get_logger()
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")

class TargetBlinkies(object):
    def __init__(self,  mqtt_host=MQTT_HOST):
        self.mqtt_host = mqtt_host
        self.stop = False
        self.thread = threading.Thread(target=self.run)
        self.enabled = False

    def publish_enable(self, target_id):
        logger.info("Enable target", target_id=target_id, actuion="enable")
        mqtt.single(f"/targets/{target_id}/enable", f"enable {target_id}", hostname=self.mqtt_host)

    def publish_disable(self, target_id):
        if self.enabled:
            logger.info("Disable target", target_id=target_id, action="disable")
            mqtt.single(f"/targets/{target_id}/disable", f"disable {target_id}", hostname=self.mqtt_host)

    def game_over(self):
        logger.info("Disable all targets")
        for target in TargetScoringSerial.TARGET_IDS:
            self.publish_disable(target)

    def run(self):
        while not self.stop:
            if self.enabled:
                target_list = list(TargetScoringSerial.TARGET_IDS)
                # Sleep some random amount of time
                off_time = random.random()
                time.sleep(off_time)

                # Select a random target to turn on
                enable_targets = [random.choice(target_list),]
                target_list.remove(enable_targets[0])

                # Optionally also enable a second target
                if random.random() < CHANCE_DOUBLE_SCORE:
                    enable_targets.append(random.choice(target_list))

                for t in enable_targets:
                    self.publish_enable(t)

                # Dwell for a time
                on_time = random.uniform(0.5, 1.5)
                time.sleep(on_time)

                # Turn off the target(s)
                for t in enable_targets:
                    self.publish_disable(t)
                    time.sleep(random.uniform(0.1, 0.4))

            else:
                time.sleep(0.1)


if __name__ == "__main__":
    blinkies = TargetBlinkies()
    blinkies.run()