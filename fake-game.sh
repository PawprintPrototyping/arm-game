#!/bin/bash

mosquitto_pub -h arm-display -t /scoreboard/digits/clear -m ''
mosquitto_pub -h arm-display -t /scoreboard/rgb/start_timer -m ''
mosquitto_pub -h arm-display -t /motion/motion/start -m ''
mosquitto_pub -h arm-display -t /target_movement/start -m ''
mosquitto_pub -h arm-display -t /targets/3/enable -m ''
mosquitto_pub -h arm-display -t /targets/2/enable -m ''
mosquitto_pub -h arm-display -t /targets/1/enable -m ''

mosquitto_sub -h arm-display -t /scoreboard/timer/game_over -C 1

mosquitto_pub -h arm-display -t /targets/3/disable -m ''
mosquitto_pub -h arm-display -t /targets/2/disable -m ''
mosquitto_pub -h arm-display -t /targets/1/disable -m ''
mosquitto_pub -h arm-display -t /scoreboard/rgb/clear -m ""
mosquitto_pub -h arm-display -t /scoreboard/rgb/game_over -m "GAME OVER"
mosquitto_pub -h arm-display -t /motion/motion/stop -m ''
mosquitto_pub -h arm-display -t /target_movement/stop -m ''
