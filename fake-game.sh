#!/bin/bash

mosquitto_pub -h arm-display -t /scoreboard/rgb/start_timer -m ''
mosquitto_pub -h arm-display -t /motion/motion/start -m ''
mosquitto_pub -h arm-display -t /target_movement/start -m ''

mosquitto_sub -h arm-display -t /scoreboard/timer/game_over -C 1
mosquitto_pub -h arm-display -t /motion/motion/stop -m ''
mosquitto_pub -h arm-display -t /target_movement/stop -m ''
