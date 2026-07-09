# MQTT API for target scoring

Manages physical target hit detection, scoring, and high score tracking over serial.  Targets are addressed by numeric ID.

The `target_scoring_serial.py` service discovers connected targets at startup by probing every valid address (0-15) once and keeping the responders.  It then regularly polls that live set to check for hits.

Each target's poll outcomes are tracked in a sliding window.  If the recent error rate exceeds the configured threshold, the target is temporarily skipped by the polling loop and probed again every few seconds so it can be re-enabled automatically once it recovers.

All arguments are passed as a JSON-encoded payload.

## Subscribes

### `targets/{id}/enable`

Enables hit detection on the specified target.  No arguments.

### `targets/{id}/disable`

Disables hit detection on the specified target.  No arguments.

### `targets/{id}/clear`

Clears the hit state on the specified target.  No arguments.

### `targets/{id}/home`

Sends the specified target to its home position.  No arguments.

### `targets/{id}/up`

Raises the specified target.  No arguments.

### `targets/{id}/down`

Lowers the specified target.  No arguments.

### `scoreboard/rgb/start_timer`

Resets the current score to 0 for a new game.  No arguments.

### `scoreboard/timer/game_over`

Records the final score to the database (if a player name is set) and rings the bell if a high score was achieved.  Resets player info afterwards.  No arguments.

### `scoreboard/player_info`

Sets the current player's info for score recording.

**Required**: `name (string)` — player name

## Publishes

### `targets/{id}/hit`

Published when a target registers a hit.  Payload: `"hit {id}"`.

### `scoreboard/digits/set_number`

Published after each hit to update the flipdigit score display.  Payload: JSON `{"number": <score>}`.

Scoring: target 2 awards 75 points, all other targets award 69 points.

### `target/{id}/errors`

Published when a target poll response cannot be parsed.  Payload: JSON `{"target": <id>, "error_count": <count>}`.

### `targets/available`

Published (retained) after startup discovery with the list of target IDs that responded.  Payload: JSON `{"targets": [<id>, ...]}`.

### `target/{id}/health`

Published (retained) when a target transitions between healthy and unhealthy.  Payload: JSON snapshot of the target's sliding-window stats:

```json
{
  "target": 3,
  "healthy": false,
  "error_rate": 0.85,
  "error_count": 42,
  "poll_count": 118,
  "window_size": 20
}
```
