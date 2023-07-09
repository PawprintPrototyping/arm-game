import json
import logging
import os
import re
import threading

import paho.mqtt.client as mqtt
import structlog

from talk_to_bot import TargetSerial

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")
DEVICE = os.getenv("DEVICE", "/dev/ttyUSB1")
BAUDRATE = int(os.getenv("BAUDRATE", "9600"))

TOPIC_REGEX = re.compile(r"^/targets/(?P<id>\d)/(?P<command>.*)$")


if DEBUG:
    logging.basicConfig(level=logging.DEBUG)
log = structlog.getLogger(__name__)


def on_connect(client, userdata, flags_dict, result):
    log.info(
        "on_connect",
        client=client,
        userdata=userdata,
        flags_dict=flags_dict,
        result=result,
    )
    client.subscribe(f"/targets/#")

"""
Subscribes to:
/targets/{id}/enable
/targets/{id}/disable
/targets/{id}/clear

Publishes to:
/targets/{id}/hit
"""

def on_message(client, targetserial, msg):
    log.debug("on_message", targetserial=targetserial, topic=msg.topic, payload=msg.payload)
    data = {}
    try:
        data = json.loads(msg.payload.decode("utf8"))
    except json.JSONDecodeError:
        log.warn("Payload is not valid JSON", mqtt_msg=msg.payload)

    match = TOPIC_REGEX.match(msg.topic)

    match match['topic']:
        case "enable":
            log.debug(f"Set target {match['id']} to enabled")
            targetserial.target_id = match['id']
            targetserial.command = TargetSerial.COMMAND_ENABLE
        case "disable":
            log.debug(f"Set target {match['id']} to disabled")
            targetserial.target_id = match['id']
            targetserial.command = TargetSerial.COMMAND_DISABLE
        case "clear":
            log.debug(f"Set target {match['id']} to clear")
            targetserial.target_id = match['id']
            targetserial.command = TargetSerial.COMMAND_ENABLE


mqttc = mqtt.Client()
mqttc.enable_logger(log)
mqttc.on_connect = on_connect
mqttc.on_message = on_message

if __name__ == "__main__":
    try:
        ts = TargetSerial(DEVICE, BAUDRATE, timeout=10)
        ts.setup()
        mqttc.user_data_set(ts)
        mqttc.connect(host=MQTT_HOST)
        ts.thread.start()
        while ts.thread.is_alive():
            mqttc.loop()
    except KeyboardInterrupt:
        log.info("Shutting down target handler gracefully....")
        ts.stop = True
        ts.thread.join(timeout=5)
        ts.close()