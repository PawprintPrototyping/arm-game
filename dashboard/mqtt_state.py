from __future__ import annotations

import collections
import json
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

import paho.mqtt.client as mqtt
import structlog

from .config import GAME_DURATION_SECONDS, MQTT_HOST, MQTT_PORT, TARGET_COUNT


log = structlog.get_logger()


TARGET_TOPIC_RE = re.compile(r"^targets/(?P<id>\d+)/(?P<command>[^/]+)$")
TARGET_ERROR_RE = re.compile(r"^target/(?P<id>\d+)/errors$")


@dataclass
class TargetState:
    target_id: int
    enabled: bool = False
    raised: Optional[bool] = None  # None = unknown, True = up, False = down
    last_hit_at: Optional[float] = None
    hits: int = 0
    error_count: int = 0


@dataclass
class GameState:
    connected: bool = False
    last_message_at: Optional[float] = None
    score: int = 0
    player_name: Optional[str] = None
    arm_state: str = "unknown"  # active, park, idle
    target_movement: str = "unknown"  # flail, stop
    timer_state: str = "idle"  # idle, running, game_over
    timer_started_at: Optional[float] = None
    game_over_message: Optional[str] = None
    targets: dict[int, TargetState] = field(default_factory=dict)
    recent_messages: collections.deque = field(
        default_factory=lambda: collections.deque(maxlen=200)
    )

    def timer_remaining(self) -> Optional[float]:
        if self.timer_state != "running" or self.timer_started_at is None:
            return None
        remaining = GAME_DURATION_SECONDS - (time.time() - self.timer_started_at)
        return max(0.0, remaining)


class MqttStateWorker:
    def __init__(
        self,
        host: str = MQTT_HOST,
        port: int = MQTT_PORT,
        target_count: int = TARGET_COUNT,
    ) -> None:
        self._lock = threading.Lock()
        self.state = GameState()
        for target_id in range(1, target_count + 1):
            self.state.targets[target_id] = TargetState(target_id=target_id)

        self._client = mqtt.Client(
            client_id=f"arm-game-dashboard-{int(time.time())}",
            clean_session=True,
        )
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message
        self._host = host
        self._port = port
        self._started = False


    def start(self) -> None:
        if self._started:
            return
        self._started = True
        try:
            self._client.connect_async(self._host, self._port, keepalive=30)
        except Exception as exc:  # pragma: no cover - defensive
            log.error("mqtt_connect_failed", host=self._host, error=str(exc))
        self._client.loop_start()

    def stop(self) -> None:  # pragma: no cover - lifecycle
        self._client.loop_stop()
        try:
            self._client.disconnect()
        except Exception:
            pass


    def publish(self, topic: str, payload: str = "") -> None:
        """Publish a raw payload (already a string) to ``topic``."""
        self._client.publish(topic, payload=payload, qos=0, retain=False)

    def publish_json(self, topic: str, payload: dict) -> None:
        self._client.publish(topic, payload=json.dumps(payload), qos=0, retain=False)

    def snapshot(self) -> GameState:
        """Return the current state (a shallow-ish copy safe to read)."""
        with self._lock:
            snap = GameState(
                connected=self.state.connected,
                last_message_at=self.state.last_message_at,
                score=self.state.score,
                player_name=self.state.player_name,
                arm_state=self.state.arm_state,
                target_movement=self.state.target_movement,
                timer_state=self.state.timer_state,
                timer_started_at=self.state.timer_started_at,
                game_over_message=self.state.game_over_message,
                targets={tid: TargetState(**t.__dict__) for tid, t in self.state.targets.items()},
                recent_messages=collections.deque(self.state.recent_messages, maxlen=200),
            )
        return snap

    def _on_connect(self, client, _userdata, _flags, rc):
        log.info("mqtt_connected", rc=rc, host=self._host)
        with self._lock:
            self.state.connected = (rc == 0)
        client.subscribe("#", qos=0)

    def _on_disconnect(self, _client, _userdata, rc):
        log.warning("mqtt_disconnected", rc=rc)
        with self._lock:
            self.state.connected = False

    def _on_message(self, _client, _userdata, msg):
        try:
            payload_str = msg.payload.decode(errors="replace") if msg.payload else ""
        except Exception:
            payload_str = repr(msg.payload)

        with self._lock:
            self.state.last_message_at = time.time()
            self.state.recent_messages.append(
                (self.state.last_message_at, msg.topic, payload_str)
            )
            self._apply(msg.topic, payload_str)


    def _apply(self, topic: str, payload: str) -> None:
        """Update state based on a single MQTT message. Called with lock held."""
        # Scoring
        if topic == "scoreboard/digits/set_number":
            data = _safe_json(payload)
            if isinstance(data, dict) and "number" in data:
                try:
                    self.state.score = int(data["number"])
                except (TypeError, ValueError):
                    pass
            return

        if topic == "scoreboard/player_info":
            data = _safe_json(payload)
            if isinstance(data, dict) and data.get("name"):
                self.state.player_name = str(data["name"])
            return

        # Timer / game lifecycle
        if topic == "scoreboard/rgb/start_timer":
            self.state.timer_state = "running"
            self.state.timer_started_at = time.time()
            self.state.game_over_message = None
            self.state.score = 0
            for target in self.state.targets.values():
                target.hits = 0
            return

        if topic == "scoreboard/timer/game_over" or topic == "scoreboard/rgb/game_over":
            self.state.timer_state = "game_over"
            data = _safe_json(payload)
            if isinstance(data, dict) and data.get("text"):
                self.state.game_over_message = str(data["text"])
            elif isinstance(payload, str) and payload.strip():
                self.state.game_over_message = payload.strip().strip('"')
            return

        if topic == "scoreboard/rgb/clear":
            self.state.timer_state = "idle"
            self.state.game_over_message = None
            return

        # Arm motion
        if topic == "motion/motion/start":
            self.state.arm_state = "active"
            return
        if topic == "motion/motion/stop":
            self.state.arm_state = "park"
            return
        if topic == "motion/motion/idle":
            self.state.arm_state = "idle"
            return

        # Side target platform
        if topic == "target_movement/start":
            self.state.target_movement = "flail"
            return
        if topic == "target_movement/stop":
            self.state.target_movement = "stop"
            return

        # Per-target commands and hits
        m = TARGET_TOPIC_RE.match(topic)
        if m:
            tid = int(m.group("id"))
            cmd = m.group("command")
            target = self.state.targets.setdefault(tid, TargetState(target_id=tid))
            if cmd == "enable":
                target.enabled = True
            elif cmd == "disable":
                target.enabled = False
            elif cmd == "up":
                target.raised = True
            elif cmd == "down":
                target.raised = False
            elif cmd == "home":
                target.raised = False
            elif cmd == "hit":
                target.hits += 1
                target.last_hit_at = time.time()
            elif cmd == "clear":
                pass
            return

        m = TARGET_ERROR_RE.match(topic)
        if m:
            tid = int(m.group("id"))
            data = _safe_json(payload)
            if isinstance(data, dict) and "error_count" in data:
                target = self.state.targets.setdefault(tid, TargetState(target_id=tid))
                try:
                    target.error_count = int(data["error_count"])
                except (TypeError, ValueError):
                    pass


def _safe_json(payload: str):
    if not payload:
        return None
    try:
        return json.loads(payload)
    except (ValueError, TypeError):
        return None
