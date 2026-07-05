# MQTT API for RGB matrix scoreboard

All arguments are passed as a JSON-encoded payload.

## Subscribes to `/scoreboard/rgb/#`

### `/scoreboard/rgb/clear`

Clears the RGB matrix display.  No arguments.

### `/scoreboard/rgb/start_timer`

Starts the game countdown timer on the display.  No arguments.

The timer counts down from a configurable duration (default: 1 minute).
When the timer expires, the scoreboard automatically transitions to the `GAME_OVER` state.

### `/scoreboard/rgb/game_over`

Displays a game over screen on the RGB matrix.

**Optional**: `text (string)`: `"GAME OVER"` — custom message to display

**Optional**: `x (int)`: `12` — horizontal text position

**Optional**: `y (int)`: `25` — vertical text position

### `/scoreboard/rgb/stop_gracefully`

Stops the scoreboard processing thread gracefully.  No arguments.

## Publishes

### `/scoreboard/timer/game_over`

Published when the game over screen is displayed (either from timer expiry or an explicit `/scoreboard/rgb/game_over` message).  Payload: `"GAME OVER"`.
