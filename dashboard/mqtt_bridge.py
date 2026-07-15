"""
MQTT-to-WebSocket relay.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from collections import defaultdict
from typing import Any

import paho.mqtt.client as mqtt
from fastapi import WebSocket

from .config import settings

log = logging.getLogger(__name__)


def _payload_to_json_safe(payload: bytes) -> str:
    """Return payload as a UTF-8 string, falling back to hex for binary blobs."""
    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError:
        return "0x" + payload.hex()


class MqttBridge:
    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"arm-game-dashboard-{int(time.time())}",
            clean_session=True,
        )
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

        # Per-client state.
        self._clients: set[WebSocket] = set()
        self._subs_by_client: dict[WebSocket, set[str]] = defaultdict(set)
        self._subscribers_by_topic: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = threading.Lock()
        self._connected = False

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        try:
            self._client.connect_async(
                host=settings.mqtt_host,
                port=settings.mqtt_port,
                keepalive=settings.mqtt_keepalive,
            )
        except Exception as exc:
            log.exception("Failed to schedule MQTT connect: %s", exc)
        self._client.loop_start()

    async def stop(self) -> None:
        try:
            self._client.disconnect()
        finally:
            self._client.loop_stop()

    def _on_connect(
        self, client, userdata, flags, reason_code, properties=None
    ) -> None:
        # `reason_code` is a ReasonCode object in v2; `.is_failure` and `str()`
        # both do the right thing.
        connected = not getattr(reason_code, "is_failure", bool(int(reason_code)))
        self._connected = connected
        log.info("MQTT connect reason=%s connected=%s", reason_code, connected)

        # Re-subscribe to every topic any client still cares about (handles
        # broker reconnects transparently).
        with self._lock:
            topics = list(self._subscribers_by_topic.keys())
        for topic in topics:
            try:
                client.subscribe(topic)
            except Exception as exc:
                log.warning("Re-subscribe to %s failed: %s", topic, exc)

        self._broadcast_status(connected=connected, reason=str(reason_code))

    def _on_disconnect(
        self, client, userdata, disconnect_flags=None, reason_code=None, properties=None
    ) -> None:
        self._connected = False
        log.info("MQTT disconnect reason=%s", reason_code)
        self._broadcast_status(connected=False, reason=str(reason_code))

    def _on_message(self, client, userdata, msg) -> None:
        event = {
            "type": "message",
            "topic": msg.topic,
            "payload": _payload_to_json_safe(msg.payload),
            "retain": bool(msg.retain),
            "qos": int(msg.qos),
            "ts": time.time(),
        }
        with self._lock:
            targets = [
                ws
                for topic, subs in self._subscribers_by_topic.items()
                if mqtt.topic_matches_sub(topic, msg.topic)
                for ws in subs
            ]
        for ws in set(targets):
            self._send_soon(ws, event)

    async def attach(self, ws: WebSocket) -> None:
        with self._lock:
            self._clients.add(ws)
        await ws.send_json(
            {
                "type": "hello",
                "broker": {
                    "host": settings.mqtt_host,
                    "port": settings.mqtt_port,
                },
                "connected": self._connected,
                "ws_broker": {
                    "host": settings.mqtt_ws_host,
                    "port": settings.mqtt_ws_port,
                    "path": settings.mqtt_ws_path,
                    "tls": settings.mqtt_ws_tls,
                },
            }
        )

    async def detach(self, ws: WebSocket) -> None:
        topics_to_check: list[str] = []
        with self._lock:
            self._clients.discard(ws)
            for topic in self._subs_by_client.pop(ws, set()):
                self._subscribers_by_topic[topic].discard(ws)
                if not self._subscribers_by_topic[topic]:
                    del self._subscribers_by_topic[topic]
                    topics_to_check.append(topic)
        for topic in topics_to_check:
            try:
                self._client.unsubscribe(topic)
            except Exception as exc:
                log.warning("Unsubscribe from %s failed: %s", topic, exc)

    async def handle(self, ws: WebSocket, message: dict[str, Any]) -> None:
        op = message.get("op")
        if op == "subscribe":
            await self._subscribe(ws, message)
        elif op == "unsubscribe":
            await self._unsubscribe(ws, message)
        elif op == "publish":
            await self._publish(ws, message)
        elif op == "ping":
            await ws.send_json({"type": "pong", "ts": time.time()})
        else:
            await ws.send_json({"type": "error", "message": f"unknown op {op!r}"})

    async def _subscribe(self, ws: WebSocket, message: dict[str, Any]) -> None:
        topic = message.get("topic")
        if not isinstance(topic, str) or not topic:
            await ws.send_json(
                {"type": "error", "message": "subscribe: topic required"}
            )
            return
        qos = int(message.get("qos", 0))
        subscribed_now = False
        with self._lock:
            if topic not in self._subs_by_client[ws]:
                self._subs_by_client[ws].add(topic)
                if not self._subscribers_by_topic[topic]:
                    subscribed_now = True
                self._subscribers_by_topic[topic].add(ws)

        if subscribed_now:
            try:
                self._client.subscribe(topic, qos=qos)
            except Exception as exc:
                await ws.send_json(
                    {"type": "error", "message": f"subscribe failed: {exc}"}
                )
                return
        await ws.send_json(
            {"type": "ack", "op": "subscribe", "topic": topic, "ok": True}
        )

    async def _unsubscribe(self, ws: WebSocket, message: dict[str, Any]) -> None:
        topic = message.get("topic")
        if not isinstance(topic, str) or not topic:
            await ws.send_json(
                {"type": "error", "message": "unsubscribe: topic required"}
            )
            return
        drop_from_broker = False
        with self._lock:
            self._subs_by_client[ws].discard(topic)
            self._subscribers_by_topic[topic].discard(ws)
            if not self._subscribers_by_topic[topic]:
                del self._subscribers_by_topic[topic]
                drop_from_broker = True
        if drop_from_broker:
            try:
                self._client.unsubscribe(topic)
            except Exception as exc:
                log.warning("Unsubscribe from %s failed: %s", topic, exc)
        await ws.send_json(
            {"type": "ack", "op": "unsubscribe", "topic": topic, "ok": True}
        )

    async def _publish(self, ws: WebSocket, message: dict[str, Any]) -> None:
        topic = message.get("topic")
        if not isinstance(topic, str) or not topic:
            await ws.send_json({"type": "error", "message": "publish: topic required"})
            return
        payload = message.get("payload", "")
        if isinstance(payload, (dict, list)):
            payload_bytes = json.dumps(payload).encode("utf-8")
        elif isinstance(payload, (int, float, bool)):
            payload_bytes = str(payload).encode("utf-8")
        elif isinstance(payload, str):
            payload_bytes = payload.encode("utf-8")
        elif payload is None:
            payload_bytes = b""
        else:
            await ws.send_json(
                {
                    "type": "error",
                    "message": f"publish: unsupported payload type {type(payload).__name__}",
                }
            )
            return

        qos = int(message.get("qos", 0))
        retain = bool(message.get("retain", False))
        info = self._client.publish(topic, payload_bytes, qos=qos, retain=retain)
        # rc==MQTT_ERR_SUCCESS (0) means the publish was queued locally.
        await ws.send_json(
            {
                "type": "ack",
                "op": "publish",
                "topic": topic,
                "ok": info.rc == mqtt.MQTT_ERR_SUCCESS,
                "rc": info.rc,
            }
        )

    def _broadcast_status(self, *, connected: bool, reason: str) -> None:
        event = {"type": "status", "connected": connected, "reason": reason}
        with self._lock:
            clients = list(self._clients)
        for ws in clients:
            self._send_soon(ws, event)

    def _send_soon(self, ws: WebSocket, event: dict) -> None:
        """Schedule ``ws.send_json`` on the asyncio loop from any thread."""
        loop = self._loop
        if loop is None or loop.is_closed():
            return

        async def _send() -> None:
            try:
                await ws.send_json(event)
            except Exception:
                # Client already gone; detach so we stop trying to reach them.
                await self.detach(ws)

        try:
            asyncio.run_coroutine_threadsafe(_send(), loop)
        except RuntimeError:
            # Loop is shutting down.
            pass


bridge = MqttBridge()
