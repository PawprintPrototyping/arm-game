# MQTT API for flipdigits display

All arguments are passed as a JSON-encoded payload.

# Command topics

## `/display/digits/clear`

Clear/blank the display.  No arguments.

## `/display/digits/set_number`

Sets a complete number to be displayed.
Optionally delays setting of each digit for ✨ dramatic ✨ effect.

**Requried**: `number (int)`

**Optional**: `delay (float)`: 0 seconds

## `/display/digits/set_digit`

Sets a single digit position's value.  Addressed from right to left, 0-indexed (LSD first).

**Required**: `digit (int)`, `address (int)`

## `/display/digits/snake`

Sends a worm around the perimeter of the digits.

**Optional**: `delay (float)`: 0.1 seconds
