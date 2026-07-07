from __future__ import annotations

import os
from dataclasses import dataclass


MQTT_HOST: str = os.getenv("MQTT_HOST", "arm-display")
MQTT_PORT: int = int(os.getenv("MQTT_PORT", "1883"))
SSH_USER: str = os.getenv("SSH_USER", "pi")
TARGET_COUNT: int = int(os.getenv("TARGET_COUNT", "8"))
GAME_DURATION_SECONDS: int = int(os.getenv("GAME_DURATION_SECONDS", "60"))


@dataclass(frozen=True)
class Unit:
    """A systemd --user unit that lives on a specific host."""

    name: str
    host: str
    description: str


# ``host="localhost"`` means the dashboard runs on this host and can invoke
# ``systemctl --user`` directly. Any other host is reached over ssh.
UNITS: tuple[Unit, ...] = (
    # arm-control (local)
    Unit("opensauce23-arm.service", "localhost", "Robot arm motion controller"),
    Unit("opensauce23-cowbell.service", "localhost", "More Cowbell"),
    Unit("opensauce23-dingding.service", "localhost", "Winner bell"),
    Unit("opensauce23-target-blinkies.service", "localhost", "Target enable sequencer"),
    Unit("opensauce23-target-movement.service", "localhost", "Side target stepper platform"),
    Unit("opensauce23-target-scoring.service", "localhost", "Hit detection + scoring"),
    # arm-display (over ssh)
    Unit("opensauce23-flippies.service", "arm-display", "Flip-digit scoreboard"),
    Unit("opensauce23-scoreboard.service", "arm-display", "RGB matrix scoreboard"),
)


def units_by_host() -> dict[str, list[Unit]]:
    grouped: dict[str, list[Unit]] = {}
    for unit in UNITS:
        grouped.setdefault(unit.host, []).append(unit)
    return grouped
