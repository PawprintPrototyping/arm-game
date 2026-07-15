"""Async wrappers around ``systemctl`` for the ops dashboard.

The dashboard shells out to ``systemctl`` rather than talking to dbus so that
the same code works whether it is running as the pi user (matching
``init.sh`` / ``restart.sh``) or as root during recovery.
"""

from __future__ import annotations

import asyncio
import shlex
from dataclasses import asdict, dataclass
from typing import AsyncIterator, Iterable

from .config import settings

ALLOWED_ACTIONS = {"start", "stop", "restart", "reload", "status"}


@dataclass
class ServiceStatus:
    unit: str
    load: str = "unknown"  # loaded / not-found
    active: str = "unknown"  # active / inactive / failed
    sub: str = "unknown"  # running / dead / failed / ...
    description: str = ""
    error: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


def _base_cmd() -> list[str]:
    cmd = ["systemctl", "--no-pager"]
    if settings.systemctl_user_scope:
        cmd.append("--user")
    return cmd


async def _run(cmd: list[str]) -> tuple[int, str, str]:
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        # systemctl / journalctl aren't installed - surface an error rather than 500.
        return 127, "", f"{cmd[0]}: {exc}"
    stdout, stderr = await proc.communicate()
    return (
        proc.returncode if proc.returncode is not None else -1,
        stdout.decode("utf-8", errors="replace"),
        stderr.decode("utf-8", errors="replace"),
    )


async def show(unit: str) -> ServiceStatus:
    cmd = _base_cmd() + [
        "show",
        unit,
        "--property=LoadState,ActiveState,SubState,Description",
    ]
    rc, out, err = await _run(cmd)
    status = ServiceStatus(unit=unit)
    if rc != 0:
        status.error = err.strip() or f"systemctl show exited {rc}"
        return status

    for line in out.splitlines():
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if key == "LoadState":
            status.load = value or "unknown"
        elif key == "ActiveState":
            status.active = value or "unknown"
        elif key == "SubState":
            status.sub = value or "unknown"
        elif key == "Description":
            status.description = value
    return status


async def show_many(units: Iterable[str]) -> list[ServiceStatus]:
    return await asyncio.gather(*(show(u) for u in units))


async def action(unit: str, verb: str) -> dict:
    """Run one of the allow-listed systemctl verbs against a unit."""
    if verb not in ALLOWED_ACTIONS:
        raise ValueError(f"Action {verb!r} is not allowed")
    if unit not in set(settings.services):
        raise ValueError(f"Unit {unit!r} is not managed by this dashboard")

    cmd = _base_cmd() + [verb, unit]
    rc, out, err = await _run(cmd)
    return {
        "unit": unit,
        "action": verb,
        "cmd": " ".join(shlex.quote(c) for c in cmd),
        "returncode": rc,
        "stdout": out,
        "stderr": err,
        "ok": rc == 0,
    }


async def stream_journal(unit: str, lines: int = 200) -> AsyncIterator[str]:
    """Yield ``journalctl -f`` output lines for a unit until cancelled."""
    if unit not in set(settings.services):
        raise ValueError(f"Unit {unit!r} is not managed by this dashboard")

    cmd = ["journalctl", "--no-pager", "-o", "short-iso"]
    if settings.systemctl_user_scope:
        cmd.append("--user")
    cmd += ["-u", unit, "-n", str(lines), "-f"]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
    except FileNotFoundError as exc:
        yield f"[dashboard] journalctl unavailable: {exc}"
        return
    assert proc.stdout is not None
    try:
        while True:
            raw = await proc.stdout.readline()
            if not raw:
                # journalctl exited?
                break
            yield raw.decode("utf-8", errors="replace").rstrip("\n")
    finally:
        if proc.returncode is None:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=2)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
