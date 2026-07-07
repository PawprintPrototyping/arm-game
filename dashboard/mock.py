from __future__ import annotations

import os
import random
import threading
import time
from collections import defaultdict

from .config import GAME_DURATION_SECONDS, TARGET_COUNT
from .mqtt_state import MqttStateWorker
from .systemctl import CommandResult


def mock_enabled() -> bool:
    return os.getenv("DASHBOARD_MOCK", "").lower() in ("1", "true", "yes", "on")


class FakeSystemctlBackend:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        # (host, unit) -> ActiveState string
        self._state: dict[tuple[str, str], str] = defaultdict(lambda: "active")
        # (host, unit) -> list[str] representing journal lines
        self._logs: dict[tuple[str, str], list[str]] = defaultdict(list)
        self._seeded = False

    def _seed(self, host: str, unit: str) -> None:
        if self._seeded:
            return
        # Only seed the very first time we see any unit so we don't reset.
        self._seeded = True
        # Randomly mark ~1 unit as inactive to make the UI more interesting.
        random.seed(42)

    def _log(self, host: str, unit: str, line: str) -> None:
        ts = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        self._logs[(host, unit)].append(f"{ts} {host} mock[{unit}]: {line}")
        # Trim to last 500 lines.
        if len(self._logs[(host, unit)]) > 500:
            self._logs[(host, unit)] = self._logs[(host, unit)][-500:]


    def is_active(self, host: str, unit: str) -> str:
        with self._lock:
            self._seed(host, unit)
            return self._state[(host, unit)]

    def status_summary(self, host: str, unit: str) -> dict[str, str]:
        state = self.is_active(host, unit)
        return {
            "ActiveState": state,
            "SubState": "running" if state == "active" else "dead",
            "LoadState": "loaded",
            "UnitFileState": "enabled",
            "ExecMainPID": str(random.randint(1000, 9999)) if state == "active" else "0",
            "ExecMainStartTimestamp": time.strftime("%a %Y-%m-%d %H:%M:%S %Z"),
        }

    def systemctl(self, host: str, verb: str, unit: str):
        with self._lock:
            self._state[(host, unit)] = "active"
        self._log(host, unit, "Started (mock).")
        return CommandResult(0, "", "")


    def start(self, host: str, unit: str):
        return self.systemctl(host, "start", unit)

    def stop(self, host: str, unit: str):
        return self.systemctl(host, "stop", unit)

    def restart(self, host: str, unit: str):
        return self.systemctl(host, "restart", unit)

    def tail_logs(self, host: str, unit: str, lines: int = 200) -> str:
        with self._lock:
            entries = list(self._logs[(host, unit)])
        if not entries:
            entries = [
                f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} {host} mock[{unit}]: (no events yet)"
            ]
        return "\n".join(entries[-lines:])


# Module-level singleton to persist state across Streamlit reruns.
_backend: FakeSystemctlBackend | None = None


def get_systemctl_backend() -> FakeSystemctlBackend:
    global _backend
    if _backend is None:
        _backend = FakeSystemctlBackend()
    return _backend


class FakeMqttStateWorker(MqttStateWorker):
    """A ``MqttStateWorker`` that never connects to a broker.

    - ``publish()`` short-circuits through the state accumulator so buttons
      produce the same UI effects as if a broker echoed them back.
    - A background thread drives a synthetic game so live state animates.
    """

    def __init__(self) -> None:
        super().__init__()
        self._sim_thread: threading.Thread | None = None
        self._sim_stop = threading.Event()

    def start(self) -> None:  # type: ignore[override]
        if self._started:
            return
        self._started = True
        with self._lock:
            self.state.connected = True
        self._sim_thread = threading.Thread(
            target=self._simulate_loop,
            name="mock-mqtt-sim",
            daemon=True,
        )
        self._sim_thread.start()

    def stop(self) -> None:  # pragma: no cover
        self._sim_stop.set()

    # publish routes through the accumulator directly (no broker involved).
    def publish(self, topic: str, payload: str = "") -> None:  # type: ignore[override]
        with self._lock:
            self.state.last_message_at = time.time()
            self.state.recent_messages.append((self.state.last_message_at, topic, payload))
            self._apply(topic, payload)

    def publish_json(self, topic: str, payload: dict) -> None:  # type: ignore[override]
        import json
        self.publish(topic, json.dumps(payload))

    def _simulate_loop(self) -> None:
        """Emit plausible game events on a slow cadence."""
        while not self._sim_stop.is_set():
            time.sleep(1.0)

            with self._lock:
                timer_state = self.state.timer_state
                started = self.state.timer_started_at
                current_score = self.state.score

            # If a game is running, dole out random hits & score bumps until timer expires.
            if timer_state == "running" and started is not None:
                if time.time() - started >= GAME_DURATION_SECONDS:
                    # Auto-fire game over like the real scoreboard would.
                    self.publish("scoreboard/timer/game_over", "GAME OVER")
                    continue

                if random.random() < 0.4:
                    tid = random.randint(1, TARGET_COUNT)
                    self.publish(f"targets/{tid}/hit", f"hit {tid}")
                    bump = 75 if tid == 2 else 69
                    self.publish_json(
                        "scoreboard/digits/set_number",
                        {"number": current_score + bump},
                    )
