import json
import logging
import os
import sys
import traceback

import paho.mqtt.client as mqtt
import structlog

from motion.arm_serial import ArmSerial

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")
DEVICE = os.getenv("DEVICE", "/dev/ttyUSB0")
BAUDRATE = int(os.getenv("BAUDRATE", "38400"))


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
    client.subscribe(f"/motion/motion/#")


"""
/motion/motion/start
/motion/motion/stop
"""


def on_message(client, robotserial, msg):
    log.debug("on_message", robotserial=robotserial, topic=msg.topic, payload=msg.payload)
    data = {}
    try:
        data = json.loads(msg.payload.decode("utf8"))
    except json.JSONDecodeError:
        log.warn("Payload is not valid JSON", mqtt_msg=msg.payload)

    match msg.topic:
        case "/motion/motion/start":
            log.debug("Set robot motion state to active")
            arm_serial.state = ArmSerial.ACTIVE
        case "/motion/motion/stop":
            log.debug("Set robot motion state to idle")
            arm_serial.state = ArmSerial.IDLE


mqttc = mqtt.Client()
mqttc.enable_logger(log)
mqttc.on_connect = on_connect
mqttc.on_message = on_message


def excepthook(args):
    log.error("Exception in child thread.", args=args)
    if args.exc_traceback:
        log.error(f"Traceback: {traceback.format_tb(args.exc_traceback)}")
        traceback.print_tb(args.exc_traceback)
    log.debug(locals())
    if "rs" in globals():
        # Gracefully shutdown
        arm_serial.close()
        sys.exit()


if __name__ == "__main__":
    try:
        arm_serial = ArmSerial(DEVICE, BAUDRATE, timeout=10)
        arm_serial.setup()
        mqttc.user_data_set(arm_serial)
        mqttc.connect(host=MQTT_HOST)
        # threading.excepthook = excepthook
        arm_serial.thread.start()
        while arm_serial.thread.is_alive():
            mqttc.loop()
    except KeyboardInterrupt:
        log.info("Shutting down motion motion control gracefully....")
        arm_serial.stop = True
        arm_serial.thread.join(timeout=5)
        arm_serial.close()
