# Serial protocol reference

Wire protocol for the target scoring bus (RS-485, multi-drop, baud 14400) between
[`TargetScoringSerial`](../motion/target_scoring_serial.py) and the target boards
([`target_controller/target_stepper`](../target_controller/target_stepper/src/main.cpp)). Boards
are addressed by id (0-15), discovered at startup.

Two protocols coexist on the bus during migration; discovery auto-detects which each board speaks.

## Legacy ASCII

| Command | Response |
|---|---|
| `poll {id}\n` | `{id} poll {enabled} {hit} {position}\n` |
| `enable {id}\n` | `{id} enable ok\n` |
| `disable {id}\n` | `{id} disable ok\n` |
| `clear {id}\n` | `{id} clear ok\n` |
| `home {id}\n` | `{id} home start\n` |
| `up {id}\n` | `{id} up start\n` |
| `down {id}\n` | `{id} down start\n` |

`enabled`/`hit` are `0`/`1`. `position` is `0` (unknown), `1` (home), `2` (up).

## Binary

Header byte:

```
 bit:   7   6 5 4 3   2 1 0
      +---+-------+-------+
      | R |  id   | opcode|
      +---+-------+-------+
```

`R` = 1 on a response frame (echoed back), 0 on a command. `id` is 0-15, `opcode` per the table below.

Command frame (3 bytes):

```
 byte:    0        1        2
      +------+--------+--------+
      | 0xAA | header |  crc8  |
      +------+--------+--------+
```

Response frame (4 bytes):

```
 byte:    0        1        2        3
      +------+--------+--------+--------+
      | 0xAA | header | status |  crc8  |
      +------+--------+--------+--------+
```

| Opcode | Command |
|---|---|
| 1 | poll |
| 2 | enable |
| 3 | disable |
| 4 | clear |
| 5 | home |
| 6 | up |
| 7 | down |

Poll status byte: `bit0=enabled bit1=hit bits2-3=position`. Other opcodes: `0x00=OK`.

CRC-8 is poly `0x07`, init `0x00`. A board that gets a bad CRC, or a frame for a different id,
stays silent — the host retries.
