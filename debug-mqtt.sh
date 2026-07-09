#!/bin/bash

mosquitto_sub -h arm-display -F '\e[92m%t \t\e[96m%p\e[0m' -q 2 -t '#'
