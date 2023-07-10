import json
import logging
import os
import threading

import paho.mqtt.client as mqtt
import structlog

from flipdigits import FlipDigits

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")
DEVICE = os.getenv("DEVICE", "/dev/ttyUSB0")
BAUDRATE = int(os.getenv("BAUDRATE", "57600"))


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
    client.subscribe(f"/scoreboard/digits/#")


def on_message(client, flipdigits, msg):
    log.info("on_message", flipdigits=flipdigits, topic=msg.topic, payload=msg.payload)
    data = {}
    try:
        data = json.loads(msg.payload.decode("utf8"))
    except json.JSONDecodeError:
        log.warn("Payload is not valid JSON", mqtt_msg=msg)

    match msg.topic:
        case "/scoreboard/digits/clear":
            if flipdigits.delay_thread.is_alive():
                flipdigits.delay_thread.join()
            flipdigits.clear()
        case "/scoreboard/digits/set_number":
            delay = data.get("delay", 0)
            number = data.get("number")
            if number is not None:
                flipdigits.delay_thread = threading.Thread(
                    target=flipdigits.set_number, args=(number, delay)
                )
                flipdigits.delay_thread.start()
            else:
                log.error("Cannot set_number() - `number` is a required argument")
        case "/scoreboard/digits/snake":
            delay = data.get("delay", 0.1)
            flipdigits.delay_thread = threading.Thread(
                target=flipdigits.snake, args=(delay,)
            )
            flipdigits.delay_thread.start()
        case "/scoreboard/digits/set_digit":
            if "address" in data and "number" in data:
                flipdigits.set_digit(data["address"], data["number"])
            else:
                log.error(
                    "Cannot set_digit() - `address` and `number` are required arguments"
                )


mqttc = mqtt.Client()
mqttc.enable_logger(log)
mqttc.on_connect = on_connect
mqttc.on_message = on_message

if __name__ == "__main__":
    flipdigits = FlipDigits(DEVICE, BAUDRATE, debug=DEBUG)
    mqttc.user_data_set(flipdigits)
    mqttc.connect(host=MQTT_HOST)
    mqttc.loop_forever()
