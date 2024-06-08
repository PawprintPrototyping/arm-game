#!/bin/bash
systemctl --user stop opensauce23-arm
python -m serial /dev/ttyUSB2 38400 --eol=LF
systemctl --user start opensauce23-arm
