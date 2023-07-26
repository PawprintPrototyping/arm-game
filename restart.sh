#!/bin/bash
systemctl --user restart opensauce23-target-blinkies.service opensauce23-target-movement.service opensauce23-target-scoring.service opensauce23-arm.service
sleep 2
systemctl --user status opensauce23-target-blinkies.service opensauce23-target-movement.service opensauce23-target-scoring.service opensauce23-arm.service


