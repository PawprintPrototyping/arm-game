# MQTT API for target movement

Controls the side target platform stepper motor movement over serial to an Arduino with two stepper motor drivers and limit switches on each end.

See the corresponding Arduino sketch in [target_controller/target_stepper](https://github.com/PawprintPrototyping/arm-game/tree/main/target_controller/target_stepper).

Also pretty dead-nuts stupid simple.  The two internal states are `flail` and `stop`.

## Subscribes to `/target_movement/#`

### `/target_movement/start`

Starts the target platform movement (sends `flail` command to the stepper controller).  No arguments.

### `/target_movement/stop`

Stops the target platform movement.  No arguments.
