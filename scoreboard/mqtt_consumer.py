import json
import logging
import os
import threading

import paho.mqtt.client as mqtt
import structlog

from scoreboard import Scoreboard

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")
DEVICE = os.getenv("DEVICE", "/dev/ttyUSB0")
BAUDRATE = int(os.getenv("BAUDRATE", "57600"))


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
    client.subscribe(f"/scoreboard/rgb/#")


def on_message(client, rgbmatrix, msg):
    log.info("on_message", rgbmatrix=rgbmatrix, topic=msg.topic, payload=msg.payload)
    data = {}
    try:
        data = json.loads(msg.payload.decode("utf8"))
    except json.JSONDecodeError:
        log.warn("Payload is not valid JSON", mqtt_msg=msg)

    match msg.topic:
        case "/scoreboard/rgb/clear":
            rgbmatrix.state = Scoreboard.CLEAR

        case "/scoreboard/rgb/start_timer":
            rgbmatrix.state = Scoreboard.TIMER

        case "/scoreboard/rgb/game_over":
            rgbmatrix.state = Scoreboard.GAME_OVER

        case "/scoreboard/rgb/stop_gracefully":
            rgbmatrix.stop = True
            rgbmatrix.delay_thread.join(timeout=10)


mqttc = mqtt.Client()
mqttc.enable_logger(log)
mqttc.on_connect = on_connect
mqttc.on_message = on_message

if __name__ == "__main__":
    rgb_matrix = Scoreboard(debug=DEBUG)
    mqttc.user_data_set(rgb_matrix)
    mqttc.connect(host=MQTT_HOST)
    rgb_matrix.delay_thread = threading.Thread(target=rgb_matrix.process)
    rgb_matrix.delay_thread.start()
    try:
        mqttc.loop_forever()
    except KeyboardInterrupt:
        rgb_matrix.stop = True
        rgb_matrix.delay_thread.join(timeout=2)
