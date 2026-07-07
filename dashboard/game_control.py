from __future__ import annotations

import time

from .mqtt_state import MqttStateWorker


def start_game(worker: MqttStateWorker, player_name: str | None = None) -> None:
    worker.publish("scoreboard/digits/clear")
    worker.publish("scoreboard/rgb/start_timer")
    worker.publish("motion/motion/start")
    worker.publish("target_movement/start")
    if player_name and player_name.strip():
        worker.publish_json("scoreboard/player_info", {"name": player_name.strip()})


def game_over(worker: MqttStateWorker, message: str = "GAME OVER") -> None:
    worker.publish_json("scoreboard/rgb/game_over", {"text": message})
    worker.publish("motion/motion/stop")
    worker.publish("target_movement/stop")


def stop_all(worker: MqttStateWorker, target_count: int = 8) -> None:
    worker.publish("motion/motion/stop")
    worker.publish("target_movement/stop")
    for tid in range(1, target_count + 1):
        worker.publish(f"targets/{tid}/disable")
        worker.publish(f"targets/{tid}/home")


def set_player(worker: MqttStateWorker, name: str) -> None:
    worker.publish_json("scoreboard/player_info", {"name": name})


def arm_start(worker: MqttStateWorker) -> None:
    worker.publish("motion/motion/start")


def arm_stop(worker: MqttStateWorker) -> None:
    worker.publish("motion/motion/stop")


def arm_idle(worker: MqttStateWorker) -> None:
    worker.publish("motion/motion/idle")


def target_movement_start(worker: MqttStateWorker) -> None:
    worker.publish("target_movement/start")


def target_movement_stop(worker: MqttStateWorker) -> None:
    worker.publish("target_movement/stop")


def target_enable(worker: MqttStateWorker, target_id: int) -> None:
    worker.publish(f"targets/{target_id}/enable")


def target_disable(worker: MqttStateWorker, target_id: int) -> None:
    worker.publish(f"targets/{target_id}/disable")


def target_up(worker: MqttStateWorker, target_id: int) -> None:
    worker.publish(f"targets/{target_id}/up")


def target_down(worker: MqttStateWorker, target_id: int) -> None:
    worker.publish(f"targets/{target_id}/down")


def target_home(worker: MqttStateWorker, target_id: int) -> None:
    worker.publish(f"targets/{target_id}/home")


def target_clear(worker: MqttStateWorker, target_id: int) -> None:
    worker.publish(f"targets/{target_id}/clear")


def scoreboard_clear(worker: MqttStateWorker) -> None:
    worker.publish("scoreboard/rgb/clear")


def digits_clear(worker: MqttStateWorker) -> None:
    worker.publish("scoreboard/digits/clear")


def digits_snake(worker: MqttStateWorker, delay: float = 0.1) -> None:
    worker.publish_json("scoreboard/digits/snake", {"delay": delay})


def digits_set_number(worker: MqttStateWorker, number: int, delay: float = 0.0) -> None:
    worker.publish_json(
        "scoreboard/digits/set_number",
        {"number": number, "delay": delay},
    )


def publish_raw(worker: MqttStateWorker, topic: str, payload: str = "") -> None:
    worker.publish(topic, payload)
    # We love load-bearing sleeps
    time.sleep(0.05)
