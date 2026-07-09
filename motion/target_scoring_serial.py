import collections
import json
import logging
import os
import queue
import time
import structlog

from paho.mqtt import publish as mqtt
from serial_base import SerialBase

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
logger = structlog.get_logger()


class TargetHealth:
    """
    Sliding-window health tracker for a target.

    Records the outcome of a poll (success/failure), flips `healthy` off when 
    the recent error rate exceeds error_threshold after collecting at least `min_samples`).
    Unhealthy targets are skipped by the polling loop, with a lightweight retry issued 
    every `retry_interval` seconds.
    """

    def __init__(self, target_id, window_size=20, error_threshold=0.5,
                 min_samples=5, retry_interval=5.0):
        self.target_id = target_id
        self.window = collections.deque(maxlen=window_size)
        self.error_threshold = error_threshold
        self.min_samples = min_samples
        self.retry_interval = retry_interval
        self.healthy = True
        self.total_errors = 0
        self.total_polls = 0
        self.next_retry_at = 0.0

    def record(self, success):
        """Record a poll outcome. Returns True if health state changed."""
        self.window.append(1 if success else 0)
        self.total_polls += 1
        if not success:
            self.total_errors += 1
        return self._update_health()

    def _update_health(self):
        if len(self.window) < self.min_samples:
            return False
        rate = self.error_rate
        if self.healthy and rate >= self.error_threshold:
            self.healthy = False
            self.next_retry_at = time.monotonic() + self.retry_interval
            # Clear the window so recovery is judged on fresh samples rather
            # than the accumulated failures that got us disabled.
            self.window.clear()
            return True
        if not self.healthy and rate < self.error_threshold:
            self.healthy = True
            return True
        return False

    @property
    def error_rate(self):
        if not self.window:
            return 0.0
        return 1.0 - (sum(self.window) / len(self.window))

    def should_poll(self, now):
        """Return True if the polling loop should probe this target now."""
        if self.healthy:
            return True
        if now >= self.next_retry_at:
            # Schedule the next probe regardless of this outcome so a failing target doesn't hog the loop.
            self.next_retry_at = now + self.retry_interval
            return True
        return False

    def snapshot(self):
        return {
            "target": self.target_id,
            "healthy": self.healthy,
            "error_rate": round(self.error_rate, 3),
            "error_count": self.total_errors,
            "poll_count": self.total_polls,
            "window_size": len(self.window),
        }


class TargetScoringSerial(SerialBase):
    # Scan this range at startup and only keeps addresses that respond.
    DISCOVERY_ADDRESS_RANGE = range(16)

    # Expected healthy timeout is around 40ms RTT, a little more for startup just in case
    DEFAULT_POLL_TIMEOUT = 0.1
    DISCOVERY_POLL_TIMEOUT = 0.15

    # target_blinkies used to source this value, but now picks up the discovered targets
    # from the `targets/available` topic.
    TARGET_IDS = []

    COMMAND_CLEAR = "clear {index}\n"
    COMMAND_ENABLE = "enable {index}\n"
    COMMAND_DISABLE = "disable {index}\n"
    COMMAND_POLL = "poll {index}\n"
    COMMAND_HOME = "home {index}\n"
    COMMAND_UP = "up {index}\n"
    COMMAND_DOWN = "down {index}\n"
    STATE_HIT = b"1"
    STATE_UNHIT = b"0"

    # New compact binary framing; discovery figures out
    # which is which per target id, so both can coexist on the same bus.
    PROTOCOL_BINARY = "binary"
    PROTOCOL_LEGACY = "legacy"

    SYNC_BYTE = 0xAA
    RESPONSE_FLAG = 0x80

    OPCODE_POLL = 1
    OPCODE_ENABLE = 2
    OPCODE_DISABLE = 3
    OPCODE_CLEAR = 4
    OPCODE_HOME = 5
    OPCODE_UP = 6
    OPCODE_DOWN = 7

    MAX_FRAME_RETRIES = 3

    _OPCODE_TO_LEGACY = {
        OPCODE_ENABLE: COMMAND_ENABLE,
        OPCODE_DISABLE: COMMAND_DISABLE,
        OPCODE_CLEAR: COMMAND_CLEAR,
        OPCODE_HOME: COMMAND_HOME,
        OPCODE_UP: COMMAND_UP,
        OPCODE_DOWN: COMMAND_DOWN,
    }

    def __init__(self, *args, poll_timeout=DEFAULT_POLL_TIMEOUT,
                 discovery_timeout=DISCOVERY_POLL_TIMEOUT,
                 health_window_size=20, health_error_threshold=0.5,
                 health_min_samples=5, health_retry_interval=5.0,
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.poll_timeout = poll_timeout
        self.discovery_timeout = discovery_timeout
        self.target_ids = list(TargetScoringSerial.TARGET_IDS)
        self.target_protocol = {}
        self.health = {}
        self._health_config = {
            "window_size": health_window_size,
            "error_threshold": health_error_threshold,
            "min_samples": health_min_samples,
            "retry_interval": health_retry_interval,
        }
        self.command_queue = queue.Queue(maxsize=20)
        self.command = None
        self.target_id = None
        self.score = 0
        self.player_info = {"name": "NO NAME"}

    def enqueue(self, command, target_id):
        if int(target_id) not in self.target_ids:
            logger.warn(f"Target ID {target_id} not found")
            return
        try:
            self.command_queue.put_nowait({"command": command, "target_id": target_id})
        except queue.Full:
            logging.warning("Target serial command queue is full!")

    def discover_targets(self, address_range=None, timeout=None):
        address_range = self.DISCOVERY_ADDRESS_RANGE if address_range is None else address_range
        timeout = self.discovery_timeout if timeout is None else timeout

        discovered = []
        protocols = {}
        previous_timeout = self.ser.timeout
        self.ser.timeout = timeout
        try:
            for idx in address_range:
                # Try the compact binary probe first (a single attempt - discovery isn't
                # the hot path, no need to retry here). Only fall back to the legacy ASCII
                # probe if that gets no valid response, so old and new boards can coexist.
                self.ser.reset_input_buffer()
                status = self._send_binary_command(idx, self.OPCODE_POLL, retries=1)
                if status is not None:
                    discovered.append(idx)
                    protocols[idx] = self.PROTOCOL_BINARY
                    logger.info("Discovered target (binary protocol)", target=idx)
                    continue

                # Drain stale bytes so delayed response to previous probe can't get attributed to this address.
                self.ser.reset_input_buffer()
                self.ser.write(f"poll {idx}\n".encode("latin1"))
                line = self.ser.readline()
                if self._response_matches_id(line, idx):
                    discovered.append(idx)
                    protocols[idx] = self.PROTOCOL_LEGACY
                    logger.info("Discovered target (legacy protocol)", target=idx, response=line)
                else:
                    logger.debug("No response from address", target=idx, response=line)
        finally:
            self.ser.timeout = previous_timeout

        self.target_ids = discovered
        self.target_protocol = protocols
        # Keep the class attribute in sync for anything that still reads it.
        TargetScoringSerial.TARGET_IDS = list(discovered)
        self.health = {
            idx: TargetHealth(idx, **self._health_config) for idx in discovered
        }
        self._publish_available(discovered)
        if not discovered:
            logger.warning("Target discovery found no responders",
                           address_range=list(address_range))
        return discovered

    @staticmethod
    def _response_matches_id(line, expected_id):
        if not line:
            return False
        parts = line.split()
        if len(parts) < 2:
            return False
        try:
            responder_id = int(parts[0])
        except ValueError:
            return False
        return responder_id == expected_id and parts[1] == b"poll"

    @staticmethod
    def _crc8(data):
        """CRC-8, poly 0x07, init 0x00 - must match the firmware's crc8() exactly."""
        crc = 0
        for byte in data:
            crc ^= byte
            for _ in range(8):
                crc = ((crc << 1) ^ 0x07) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
        return crc

    @classmethod
    def _encode_command_frame(cls, index, opcode):
        header = ((index & 0x0F) << 3) | (opcode & 0x07)
        return bytes([cls.SYNC_BYTE, header, cls._crc8(bytes([header]))])

    def _read_binary_response(self, expected_index, expected_opcode):
        sync = self.ser.read(1)
        if sync != bytes([self.SYNC_BYTE]):
            return None
        rest = self.ser.read(3)
        if len(rest) != 3:
            return None
        header, status, crc = rest
        if self._crc8(bytes([header, status])) != crc:
            return None
        if not (header & self.RESPONSE_FLAG):
            return None
        if (header >> 3) & 0x0F != expected_index or header & 0x07 != expected_opcode:
            return None
        return status

    def _send_binary_command(self, index, opcode, retries=None):
        retries = self.MAX_FRAME_RETRIES if retries is None else retries
        frame = self._encode_command_frame(index, opcode)
        for _ in range(retries):
            self.ser.reset_input_buffer()
            self.ser.write(frame)
            status = self._read_binary_response(index, opcode)
            if status is not None:
                return status
        return None

    def _publish_available(self, targets):
        try:
            mqtt.single(
                "targets/available",
                json.dumps({
                    "targets": targets,
                    "protocols": {str(idx): self.target_protocol.get(idx, self.PROTOCOL_LEGACY)
                                  for idx in targets},
                }),
                hostname=MQTT_HOST,
                retain=True,
            )
        except Exception as e:
            # Local discovery is still useful without MQTT; don't crash.
            logger.warn("Failed to publish targets/available", error=str(e))

    def run(self):
        # Run discovery on the serial thread
        if not self.health:
            self.discover_targets()

        # Drop into the hot-path poll timeout for the remainder of the run.
        self.ser.timeout = self.poll_timeout

        while not self.stop:
            try:
                cmd = self.command_queue.get_nowait()
            except queue.Empty:
                cmd = {"command": None}

            match cmd["command"]:
                case TargetScoringSerial.COMMAND_ENABLE:
                    self.enable(cmd["target_id"])
                case TargetScoringSerial.COMMAND_DISABLE:
                    self.disable(cmd["target_id"])
                case TargetScoringSerial.COMMAND_CLEAR:
                    self.clear(cmd["target_id"])
                case TargetScoringSerial.COMMAND_HOME:
                    self.home(cmd["target_id"])
                case TargetScoringSerial.COMMAND_UP:
                    self.up(cmd["target_id"])
                case TargetScoringSerial.COMMAND_DOWN:
                    self.down(cmd["target_id"])
            # Load bearing sleep: if we tell the microcontroller to do too many things back to back, we think it will
            # drop subsequent messages.  See also: `max485DriverEnableDuration` in target_controller/target_stepper/src/main.cpp
            time.sleep(0.02)

            now = time.monotonic()
            for idx in self.target_ids:
                if not self.command_queue.empty():
                    break
                health = self.health.get(idx)
                if health is not None and not health.should_poll(now):
                    continue
                state = self.poll(idx)
                if state:
                    self.publish_hit(idx)
                    self.clear(idx)
                time.sleep(0.03)

    def publish_hit(self, index):
        TargetScoringSerial.logger.info("Publish hit for target", target=index)
        mqtt.single(f"targets/{index}/hit", f"hit {index}", hostname=MQTT_HOST)
        if index == 1:
            self.score += 75
        else:
            self.score += 69
        logger.info("Current score", score=self.score)
        mqtt.single(f"scoreboard/digits/set_number", json.dumps({"number":self.score}), hostname=MQTT_HOST)

    def poll(self, index):
        if self.target_protocol.get(index) == self.PROTOCOL_BINARY:
            return self._poll_binary(index)
        return self._poll_legacy(index)

    def _poll_binary(self, index):
        health = self.health.get(index)
        status = self._send_binary_command(index, self.OPCODE_POLL)
        if status is None:
            logger.warn(f"No valid binary poll response from target {index}")
            self._record_poll_result(index, health, success=False)
            return False

        self._record_poll_result(index, health, success=True)
        hit = bool(status & 0x02)
        logger.debug("Target poll (binary)", index=index, status=status, hit=hit)
        return hit

    def _poll_legacy(self, index):
        TargetScoringSerial.logger.debug("Writing poll command", index=index)
        self.ser.write(f"poll {index}\n".encode("latin1"))
        line = self.ser.readline()
        TargetScoringSerial.logger.debug("poll response", index=index, line=line)

        health = self.health.get(index)

        try:
            idx, cmd, state, hit, pos = line.split()
        except ValueError:
            logger.warn(f"Unable to unpack values ('{line}') for target {index}")
            self._record_poll_result(index, health, success=False)
            return False

        if int(idx) != index:
            logger.warn(f"Poll response id {idx!r} does not match request {index}")
            self._record_poll_result(index, health, success=False)
            return None

        self._record_poll_result(index, health, success=True)
        logger.debug("Target poll", index=index, hit=hit, state=state, pos=pos)
        if hit == TargetScoringSerial.STATE_HIT:
            return True
        if hit == TargetScoringSerial.STATE_UNHIT:
            return False
        return None

    def _record_poll_result(self, index, health, success):
        if health is None:
            # Poll happened before discovery populated health tracking.
            # Fall back to the legacy per-error publish so operators still get a signal.
            if not success:
                self._publish_legacy_error(index, 1)
            return

        state_changed = health.record(success)
        if not success:
            # Keep the legacy topic populated on every error for existing dashboards.
            self._publish_legacy_error(index, health.total_errors)
        if state_changed:
            if health.healthy:
                logger.info("Target recovered", target=index,
                            error_rate=health.error_rate)
            else:
                logger.warning("Target marked unhealthy",
                               target=index,
                               error_rate=health.error_rate,
                               retry_in=health.retry_interval)
            self._publish_health(index, health)

    def _publish_health(self, index, health):
        try:
            mqtt.single(
                f"target/{index}/health",
                json.dumps(health.snapshot()),
                hostname=MQTT_HOST,
                retain=True,
            )
        except Exception as exc:
            logger.warn("Failed to publish target health", error=str(exc))

    def _publish_legacy_error(self, index, error_count):
        try:
            mqtt.single(
                f"target/{index}/errors",
                json.dumps({"target": index, "error_count": error_count}),
                hostname=MQTT_HOST,
            )
        except Exception as exc:
            logger.warn("Failed to publish target error", error=str(exc))

    def _dispatch(self, index, opcode):
        """Send a command via the binary protocol if this target speaks it, else fall
        back to the legacy ASCII command - see discover_targets()."""
        if self.target_protocol.get(index) == self.PROTOCOL_BINARY:
            status = self._send_binary_command(index, opcode)
            if status is None:
                logger.warn(f"No ack from target {index} for opcode {opcode}")
            return status
        legacy_command_template = self._OPCODE_TO_LEGACY[opcode]
        return self.write(legacy_command_template.format(index=index).encode("latin1"))

    def enable(self, index):
        return self._dispatch(index, self.OPCODE_ENABLE)

    def disable(self, index):
        return self._dispatch(index, self.OPCODE_DISABLE)

    def clear(self, index):
        return self._dispatch(index, self.OPCODE_CLEAR)

    def home(self, index):
        return self._dispatch(index, self.OPCODE_HOME)

    def up(self, index):
        return self._dispatch(index, self.OPCODE_UP)

    def down(self, index):
        return self._dispatch(index, self.OPCODE_DOWN)

    def poll_and_clear(self, index):
        state = self.poll(index)
        self.clear(index)
        return state
