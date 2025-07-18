import json
import logging
import os
import re
import time

import structlog
import paho.mqtt.client as mqtt

import oopsie
from target_blinkies import TargetBlinkies

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
#DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")
DEBUG = True


logging.basicConfig(level=logging.INFO)
if DEBUG:
    logging.basicConfig(level=logging.DEBUG)
log = structlog.getLogger(__name__)
if DEBUG:
    log.debug("Debug true.")


def on_connect(client, userdata, flags_dict, result):
    log.info(
        "on_connect",
        client=client,
        userdata=userdata,
        flags_dict=flags_dict,
        result=result,
    )
    client.subscribe(f"scoreboard/timer/game_over")
    client.subscribe(f"scoreboard/rgb/start_timer")


"""
Subscribes to:
targets/{id}/enable
targets/{id}/disable
targets/{id}/clear

Publishes to:
targets/{id}/hit
"""
def on_message(client, blinkies, msg):
    log.debug("on_message", topic=msg.topic, payload=msg.payload)

    if msg.topic == "scoreboard/rgb/start_timer":
        #blinkies.game_start()
        log.debug("Enabling targets (flag)...")
        blinkies.enabled = True

    if msg.topic == "scoreboard/timer/game_over":
        log.debug("Disabling targets...")
        blinkies.enabled = False
        blinkies.game_over()


mqttc = mqtt.Client()
mqttc.enable_logger(log)
mqttc.on_connect = on_connect
mqttc.on_message = on_message

if __name__ == "__main__":
    blinkies = TargetBlinkies(MQTT_HOST)
    mqttc.user_data_set(blinkies)
    mqttc.connect(host=MQTT_HOST)
    blinkies.thread.start()
    while blinkies.thread.is_alive():
        mqttc.loop(0.1)
