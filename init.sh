#!/bin/bash
systemctl --no-pager --user start opensauce23-target-blinkies.service opensauce23-target-movement.service opensauce23-target-scoring.service opensauce23-arm.service opensauce23-dingding.service opensauce23-cowbell.service
systemctl --no-pager --user status opensauce23-target-blinkies.service opensauce23-target-movement.service opensauce23-target-scoring.service opensauce23-arm.service opensauce23-dingding.service opensauce23-cowbell.service


