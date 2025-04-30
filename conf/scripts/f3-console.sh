#!/bin/bash
systemctl --user stop opensauce23-arm
python -m serial /dev/ttyRobot 57600 --eol=LF
systemctl --user start opensauce23-arm
