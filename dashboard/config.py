from __future__ import annotations

import os
from dataclasses import dataclass, field


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


ARM_DISPLAY_SERVICES = [
    "opensauce23-flippies.service",
    "opensauce23-scoreboard.service",
]

ARM_CONTROL_SERVICES = [
    "opensauce23-arm.service",
    "opensauce23-cowbell.service",
    "opensauce23-dingding.service",
    "opensauce23-target-blinkies.service",
    "opensauce23-target-movement.service",
    "opensauce23-target-scoring.service",
]

DEFAULT_SERVICES = ARM_DISPLAY_SERVICES + ARM_CONTROL_SERVICES


@dataclass(frozen=True)
class Settings:
    # Which systemd services to expose in the UI.
    services: list[str] = field(default_factory=lambda: list(DEFAULT_SERVICES))

    systemctl_user_scope: bool = True

    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    mqtt_keepalive: int = 30

    mqtt_ws_host: str = ""  # empty: frontend uses window.location.hostname
    mqtt_ws_port: int = 9001
    mqtt_ws_path: str = "/mqtt"
    mqtt_ws_tls: bool = False

    http_host: str = "0.0.0.0"
    http_port: int = 8000

    @classmethod
    def from_env(cls) -> "Settings":
        services_env = os.getenv("DASHBOARD_SERVICES", "")
        services = _split_csv(services_env) if services_env else list(DEFAULT_SERVICES)
        return cls(
            services=services,
            systemctl_user_scope=os.getenv("DASHBOARD_SYSTEMCTL_SCOPE", "user").lower()
            != "system",
            mqtt_host=os.getenv("MQTT_HOST", "localhost"),
            mqtt_port=int(os.getenv("MQTT_PORT", "1883")),
            mqtt_keepalive=int(os.getenv("MQTT_KEEPALIVE", "30")),
            mqtt_ws_host=os.getenv("MQTT_WS_HOST", ""),
            mqtt_ws_port=int(os.getenv("MQTT_WS_PORT", "9001")),
            mqtt_ws_path=os.getenv("MQTT_WS_PATH", "/mqtt"),
            mqtt_ws_tls=os.getenv("MQTT_WS_TLS", "false").lower()
            in ("1", "true", "yes"),
            http_host=os.getenv("DASHBOARD_HOST", "0.0.0.0"),
            http_port=int(os.getenv("DASHBOARD_PORT", "8000")),
        )


settings = Settings.from_env()
