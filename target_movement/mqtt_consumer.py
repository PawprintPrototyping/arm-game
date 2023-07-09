import json
import logging
import os
import threading
import re

import paho.mqtt.client as mqtt
import structlog

from arm.talk_to_bot import TargetMovementSerial

MQTT_HOST = os.getenv("MQTT_HOST", "arm-display")
DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")
DEVICE = os.getenv("DEVICE", "/dev/ttyUSB2")
BAUDRATE = int(os.getenv("BAUDRATE", "9600"))

TOPIC_REGEX = re.compile(r"^/target_movement/(?P<command>.*)$")

if DEBUG:
    logging.basicConfig(level=logging.DEBUG)
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
    client.subscribe(f"/target_movement/#")


def on_message(client, target_movement, msg):
    log.info("on_message", target_movement=target_movement, topic=msg.topic, payload=msg.payload)
    data = {}
    try:
        data = json.loads(msg.payload.decode("utf8"))
    except json.JSONDecodeError:
        log.warn("Payload is not valid JSON", mqtt_msg=msg)

    match = TOPIC_REGEX.match(msg.topic)

    match match['command']:
        case "start":
            target_movement.command = TargetMovementSerial.START_COMMAND
        case "stop":
            target_movement.command = TargetMovementSerial.STOP_COMMAND


mqttc = mqtt.Client()
mqttc.enable_logger(log)
mqttc.on_connect = on_connect
mqttc.on_message = on_message

if __name__ == "__main__":
    try:
        tms = TargetMovementSerial(DEVICE, BAUDRATE, timeout=5)
        mqttc.user_data_set(tms)
        mqttc.connect(host=MQTT_HOST)
        tms.thread.start()
        while tms.thread.is_alive():
            mqttc.loop(0.05)
    except KeyboardInterrupt:
        log.info("Shutting down target movement handler gracefully....")
        tms.stop = True
        tms.thread.join(timeout=5)
        tms.ser.close()
