# Ops Dashboard

A lightweight web UI for running the arm-game. Backend is [FastAPI], frontend is [Alpine.js] + [mqtt.js] served as static files. No build step, no bundler. Both frontend libraries are vendored under [`dashboard/static/vendor/`](./static/vendor/) so the dashboard runs on a LAN-only pi with no internet access — see the README there for update steps.

The UI has four tabs:

* **Services** — list all `opensauce23-*` systemd user services with their
  live state; start/stop/restart with one click.
* **Logs** — follow `journalctl --user -u <unit> -f` over a WebSocket.
* **MQTT** — subscribe to any topic pattern, watch messages roll in, publish
  ad-hoc messages for debugging.
* **Game** — one-click shortcuts that mirror what
  [`real-game-with-feeling.sh`](../real-game-with-feeling.sh) does over
  `mosquitto_pub`: start / stop the game, clear the scoreboard, ring the
  cowbell, set the player name, control each of the eight targets.

## MQTT transports

The dashboard can reach the broker two ways:

1. **Relay via backend** (default) — the browser opens a WebSocket to
   `/ws/mqtt`; the FastAPI process runs a paho-mqtt client on the pi and
   proxies pub/sub messages both ways over JSON envelopes. Works even if the
   browser has no direct network path to mosquitto (which is the common
   case for anyone on Amazon guest wifi).
2. **Direct to mosquitto** — the browser connects straight to the mosquitto
   WebSockets listener on `:9001` using mqtt.js. Enable the second listener
   with the config in [`conf/mosquitto/opensauce23.conf`](../conf/mosquitto/opensauce23.conf).

Toggle the transport in the **Settings** tab; the choice is persisted in
`localStorage`.

## Running locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

MQTT_HOST=arm-display python -m dashboard
# open http://localhost:8000
```

Useful env vars (see `dashboard/config.py`):

| Variable                     | Default       | Notes                                      |
| ---------------------------- | ------------- | ------------------------------------------ |
| `MQTT_HOST`                  | `localhost`   | Broker the backend relay connects to       |
| `MQTT_PORT`                  | `1883`        | TCP MQTT port                              |
| `MQTT_WS_HOST`               | *(empty)*     | Overrides broker host advertised to the UI |
| `MQTT_WS_PORT`               | `9001`        | Mosquitto WebSockets listener port         |
| `MQTT_WS_PATH`               | `/mqtt`       | WebSockets URL path                        |
| `DASHBOARD_HOST`             | `0.0.0.0`     | uvicorn bind host                          |
| `DASHBOARD_PORT`             | `8000`        | uvicorn bind port                          |
| `DASHBOARD_SERVICES`         | *(baked-in)*  | Comma-separated systemd units to expose    |
| `DASHBOARD_SYSTEMCTL_SCOPE`  | `user`        | Set to `system` for system-scope units     |

## Deploying on the pi

Install the service unit from [`conf/systemd-units/arm-display/opensauce23-dashboard.service`](../conf/systemd-units/arm-display/opensauce23-dashboard.service):

```bash
mkdir -p ~/.config/systemd/user
cp conf/systemd-units/arm-display/opensauce23-dashboard.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now opensauce23-dashboard.service
```

Enable the mosquitto WebSockets listener by dropping
[`conf/mosquitto/opensauce23.conf`](../conf/mosquitto/opensauce23.conf) into
`/etc/mosquitto/conf.d/` and restarting `mosquitto`.

[FastAPI]: https://fastapi.tiangolo.com/
[Alpine.js]: https://alpinejs.dev/
[mqtt.js]: https://github.com/mqttjs/MQTT.js
