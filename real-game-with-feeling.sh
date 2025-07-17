#!/bin/bash
#set -eoxu pipefail

function ctrl_c {
  echo "Interrupt caught, halting game..."
  mosquitto_pub -h arm-display -t /scoreboard/rgb/game_over -m '{"text":"OOPSIE owo"}'
  mosquitto_pub -h arm-display -t /motion/motion/stop -m ''
  mosquitto_pub -h arm-display -t /target_movement/stop -m ''
  sleep 1
  disable_targets
  exit
}

function disable_targets {
  for i in seq 1 8; do
    mosquitto_pub -h arm-display -t "/targets/$i/disable" -m ''
    sleep 0.2
  done
}

trap ctrl_c INT

while true; do
  for i in seq 1 30; do
    clear
    python highscores.py

    echo ""
    echo  -n "New Game?  Enter player name and press enter when ready! > "
    read name

    echo "Good luck, $name"
    for i in $(seq 5 -1 1); do
      #echo -ne "\r$i"
      clear
      echo -e '\n\n\n'
      figlet -c "$i"
      mosquitto_pub -h arm-display -t /scoreboard/cowbell -m ''
      sleep 1
    done

    #echo -e "\rGO!"
    clear
    echo -e '\n\n\n'
    figlet -c "GO!"
    echo


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

    sleep 1
    disable_targets
    #mosquitto_pub -h arm-display -t /scoreboard/rgb/clear -m ""
    sleep 1

  done
  clear
  echo "Please wait, recalibrating...."
  echo -e '\n\n\n'
  figlet 'Please  wait'
  systemctl  --user restart opensauce23-target-movement.service
  sleep 30

  # Old recal code
  #for i in seq 1 30; do
  #  ...
  #done
  #clear
  #echo "Please wait, recalibrating...."
  #
  #systemctl  --user restart opensauce23-target-movement.service
  #sleep 30
done
