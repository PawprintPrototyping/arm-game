#!/bin/bash
#set -eoxu pipefail

PIN='17'
ON_DURATION='0.1'
DWELL_DURATION='0.25'
MQTT_HOST="arm-display"

trap quit SIGINT
quit() {
	exit
}

while [ 1 ]; do
  mosquitto_sub -h $MQTT_HOST \
    -C 1 \
    -t "/targets/+/hit" \
    -t /scoreboard/cowbell \
    || exit

  if ! [ -e "/sys/class/gpio/gpio${PIN}/value" ] ; then
    echo "$PIN" > '/sys/class/gpio/export'
  fi
  if [[ "$(cat "/sys/class/gpio/gpio${PIN}/direction")" != "out" ]] ; then
    echo 'out' > "/sys/class/gpio/gpio${PIN}/direction"
  fi

  echo '1' > "/sys/class/gpio/gpio${PIN}/value"
  sleep "$ON_DURATION"
  echo '0' > "/sys/class/gpio/gpio${PIN}/value"

  sleep 0.5
done
