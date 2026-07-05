# MQTT API for robot arm motion control

All arguments are passed as a JSON-encoded payload.

Nothing fancy here.  It's pretty much either on or off.

## Subscribes to `/motion/motion/#`

### `/motion/motion/start`

Sets the robot arm to the `ACTIVE` state.  The arm will continuously move between random preset positions (`p1`–`p5`, `tease1`, `tease2`).  No arguments.

### `/motion/motion/stop`

Sets the robot arm to the `PARK` state.  The arm moves to its home position (`p1`) and then transitions to idle.  No arguments.

### `/motion/motion/idle`

Sets the robot arm to the `IDLE` state.  The arm stops moving immediately without returning to a home position.  No arguments.
