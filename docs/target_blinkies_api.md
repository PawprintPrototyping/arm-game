# MQTT API for target blinkies (target light sequencer)

The target blinkies service orchestrates enabling targets during gameplay.  It randomly selects targets to raise and enable, then disables and lowers them after a dwell period.

## Subscribes

### `/scoreboard/rgb/start_timer`

Enables the target sequencer.  When received, the service begins randomly raising and enabling targets.  No arguments.

### `/scoreboard/timer/game_over`

Disables the target sequencer.  All targets are disabled and homed.  No arguments.

## Publishes

The service publishes to the following topics to control individual targets via the target scoring service:

### `/targets/{id}/enable`

Activates hit detection on the specified target.

### `/targets/{id}/disable`

Deactivates hit detection on the specified target.

### `/targets/{id}/up`

Raises the specified target into view.

### `/targets/{id}/down`

Lowers the specified target out of view.

### `/targets/{id}/home`

Sends the specified target to its home position.
