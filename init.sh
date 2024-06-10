#!/bin/bash
systemctl --user start opensauce23-target-blinkies.service opensauce23-target-movement.service opensauce23-target-scoring.service opensauce23-arm.service
systemctl --user status opensauce23-target-blinkies.service opensauce23-target-movement.service opensauce23-target-scoring.service opensauce23-arm.service


