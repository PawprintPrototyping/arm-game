"""
Run with:

    uvicorn dashboard.app:app --host 0.0.0.0 --port 8000

or:

    python -m dashboard
"""

from __future__ import annotations

import json
import logging
import pathlib
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import systemctl
from .config import DEFAULT_SERVICES, settings
from .mqtt_bridge import bridge

log = logging.getLogger(__name__)

STATIC_DIR = pathlib.Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await bridge.start()
    try:
        yield
    finally:
        await bridge.stop()


app = FastAPI(title="arm-game ops dashboard", lifespan=lifespan)


if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=500, detail="dashboard static assets missing")
    return FileResponse(index_file)


@app.get("/api/config")
async def api_config() -> dict:
    return {
        "services": list(settings.services),
        "known_services": list(DEFAULT_SERVICES),
        "mqtt": {
            "backend_host": settings.mqtt_host,
            "backend_port": settings.mqtt_port,
            "ws_host": settings.mqtt_ws_host,
            "ws_port": settings.mqtt_ws_port,
            "ws_path": settings.mqtt_ws_path,
            "ws_tls": settings.mqtt_ws_tls,
        },
    }


@app.get("/api/services")
async def api_services() -> dict:
    statuses = await systemctl.show_many(settings.services)
    return {"services": [s.as_dict() for s in statuses]}


@app.get("/api/services/{unit}")
async def api_service(unit: str) -> dict:
    if unit not in set(settings.services):
        raise HTTPException(status_code=404, detail=f"unit {unit!r} is not managed")
    status = await systemctl.show(unit)
    return status.as_dict()


@app.post("/api/services/{unit}/{verb}")
async def api_service_action(unit: str, verb: str) -> dict:
    try:
        return await systemctl.action(unit, verb)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.websocket("/ws/logs/{unit}")
async def ws_logs(ws: WebSocket, unit: str) -> None:
    if unit not in set(settings.services):
        await ws.close(code=4404, reason=f"unit {unit!r} is not managed")
        return
    await ws.accept()
    try:
        async for line in systemctl.stream_journal(unit):
            await ws.send_text(line)
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # pragma: no cover
        log.exception("log stream failed for %s", unit)
        try:
            await ws.send_text(f"[dashboard] log stream error: {exc}")
        except Exception:
            pass
    finally:
        try:
            await ws.close()
        except Exception:
            pass


@app.websocket("/ws/mqtt")
async def ws_mqtt(ws: WebSocket) -> None:
    await ws.accept()
    await bridge.attach(ws)
    try:
        while True:
            raw = await ws.receive_text()
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json({"type": "error", "message": "invalid JSON"})
                continue
            if not isinstance(message, dict):
                await ws.send_json({"type": "error", "message": "expected JSON object"})
                continue
            await bridge.handle(ws, message)
    except WebSocketDisconnect:
        pass
    except Exception:  # pragma: no cover
        log.exception("MQTT WS handler failed")
    finally:
        await bridge.detach(ws)
