import json
import logging
import os
import re
import time

import sqlite3
import RPi.GPIO as GPIO

import structlog
import paho.mqtt.client as mqtt

import oopsie
from target_scoring_serial import TargetScoringSerial

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
DEVICE = os.getenv("DEVICE", "/dev/ttyTargets")
BAUDRATE = int(os.getenv("BAUDRATE", "9600"))
DATABASE = os.getenv("DATABASE", "/home/pi/scores.db")
BELL_PIN = 7

TOPIC_REGEX = re.compile(r"^/targets/(?P<id>\d)/(?P<command>.*)$")


structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.INFO))
if DEBUG:
    structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG))
log = structlog.getLogger(__name__)

GPIO.setmode(GPIO.BOARD)
GPIO.setup(BELL_PIN, GPIO.OUT)

def init_db():
    db = sqlite3.connect(DATABASE, isolation_level=None)
    db.execute("CREATE TABLE IF NOT EXISTS scores(id INTEGER PRIMARY KEY, name TEXT, score INTEGER);")
    return db

def on_connect(client, userdata, flags_dict, result):
    log.info(
        "on_connect",
        client=client,
        userdata=userdata,
        flags_dict=flags_dict,
        result=result,
    )
    client.subscribe(f"/targets/#")
    client.subscribe(f"/scoreboard/rgb/start_timer")
    client.subscribe(f"/scoreboard/timer/game_over")
    client.subscribe(f"/scoreboard/player_info")


"""
Subscribes to:
/targets/{id}/enable
/targets/{id}/disable
/targets/{id}/clear
/targets/{id}/home
/targets/{id}/up
/targets/{id}/down

Publishes to:
/targets/{id}/hit
"""


def record_score(player_info, score):
    log.info("record score", score=score, player_info=player_info)
    db.execute("INSERT INTO scores(name, score) VALUES (?, ?)", (player_info["name"], score))


def get_high_score():
    res = db.execute("SELECT MAX(score) FROM scores;")
    high_score = res.fetchone()[0]
    return high_score


def ring_bell():
    BELL_ON_DURATION = 0.02
    BELL_DWELL_DURATION = 0.25
    GPIO.output(BELL_PIN, GPIO.HIGH)
    time.sleep(BELL_ON_DURATION)
    GPIO.output(BELL_PIN, GPIO.LOW)
    time.sleep(BELL_DWELL_DURATION)

def ring_bell_high_score():
    for i in range(10):
        ring_bell()


def on_message(client, targetserial, msg):
    log.debug("on_message", targetserial=targetserial, topic=msg.topic, payload=msg.payload)
    data = {}
    try:
        data = json.loads(msg.payload.decode("utf8"))
    except json.JSONDecodeError:
        log.warn("Payload is not valid JSON", mqtt_msg=msg.payload)

    if msg.topic == "/scoreboard/rgb/start_timer":
        targetserial.score = 0
        return

    if msg.topic == "/scoreboard/timer/game_over":
        # Record high score and reset player info
        if targetserial.player_info["name"] != "NO NAME":
            record_score(targetserial.player_info, targetserial.score)
        targetserial.player_info = {"name": "NO NAME"}
        high_score = get_high_score()
        if targetserial.score >= high_score:
            time.sleep(0.5)
            ring_bell_high_score()
        return

    if msg.topic == "/scoreboard/player_info":
        if "name" in data:
            targetserial.player_info = data
        else:
            log.warn("Could not set player info: 'name' not in payload!")
        return

    match = TOPIC_REGEX.match(msg.topic)

    if not match:
        log.warn("Skip regex match")
    match match['command']:
        case "enable":
            log.debug(f"Set target {match['id']} to enabled")
            targetserial.enqueue(TargetScoringSerial.COMMAND_ENABLE, match['id'])
        case "disable":
            log.debug(f"Set target {match['id']} to disabled")
            targetserial.enqueue(TargetScoringSerial.COMMAND_DISABLE, match['id'])
        case "clear":
            log.debug(f"Set target {match['id']} to clear")
            targetserial.enqueue(TargetScoringSerial.COMMAND_CLEAR, match['id'])
        case "home":
            log.debug(f"Set target {match['id']} to home")
            targetserial.enqueue(TargetScoringSerial.COMMAND_HOME, match['id'])
        case "up":
            log.debug(f"Set target {match['id']} to up")
            targetserial.enqueue(TargetScoringSerial.COMMAND_UP, match['id'])
        case "down":
            log.debug(f"Set target {match['id']} to down")
            targetserial.enqueue(TargetScoringSerial.COMMAND_DOWN, match['id'])

mqttc = mqtt.Client()
mqttc.enable_logger(log)
mqttc.on_connect = on_connect
mqttc.on_message = on_message

if __name__ == "__main__":
    try:
        db = init_db()
        ts = TargetScoringSerial(DEVICE, BAUDRATE, timeout=5)
        mqttc.user_data_set(ts)
        mqttc.connect(host=MQTT_HOST)
        ts.thread.start()
        while ts.thread.is_alive():
            mqttc.loop(0.05)
    except KeyboardInterrupt:
        log.info("Shutting down target handler gracefully....")
        ts.stop = True
        ts.thread.join(timeout=5)
        ts.ser.close()
        db.close()
