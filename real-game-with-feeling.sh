#!/bin/bash
#set -eoxu pipefail



for i in seq 1 30; do
  clear
  python highscores.py

  echo ""
  echo  -n "New Game?  Enter player name and press enter when ready! > "
  read name

  echo "Good luck, $name"
  for i in $(seq 5 -1 1); do
    echo -ne "\r$i"
    sleep 1
  done

  echo -e "\rGO!"


  mosquitto_pub -h arm-display -t /scoreboard/digits/clear -m ''
  mosquitto_pub -h arm-display -t /scoreboard/rgb/start_timer -m ''
  mosquitto_pub -h arm-display -t /motion/motion/start -m ''
  mosquitto_pub -h arm-display -t /target_movement/start -m ''
  mosquitto_pub -h arm-display -t /scoreboard/player_info -m "{\"name\":\"$name\"}"
  # mosquitto_pub -h arm-display -t /targets/3/enable -m ''
  # mosquitto_pub -h arm-display -t /targets/2/enable -m ''
  # mosquitto_pub -h arm-display -t /targets/1/enable -m ''

  mosquitto_sub -h arm-display -t /scoreboard/timer/game_over -C 1 ||
    mosquitto_pub -h arm-display -t /scoreboard/rgb/game_over -m "GAME OVER"


  mosquitto_pub -h arm-display -t /motion/motion/stop -m ''
  mosquitto_pub -h arm-display -t /target_movement/stop -m ''

  python highscores.py

  sleep 1
  mosquitto_pub -h arm-display -t /targets/3/disable -m ''
  sleep 1
  mosquitto_pub -h arm-display -t /targets/2/disable -m ''
  sleep 1
  mosquitto_pub -h arm-display -t /targets/1/disable -m ''
  #mosquitto_pub -h arm-display -t /scoreboard/rgb/clear -m ""
  sleep 1
done

clear
echo "Please wait, recalibrating...."

systemctl  --user restart opensauce23-target-movement.service
sleep 30

