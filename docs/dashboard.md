# Operator Dashboard

A Streamlit-based operator dashboard for running the game. Runs on `arm-control` (so it doesn't compete with the RGB matrix processing on `arm-display`).

## Requirements

- Python packages: `streamlit`, `streamlit-autorefresh`, `paho-mqtt`.
- SSH key so `arm-control` can login to `arm-display` as user `pi`.
- On `arm-display`, `loginctl enable-linger pi` so `systemctl --user` works w/ non-interactive SSH session.

## Running locally

```bash
pip install -r requirements.txt
streamlit run dashboard/app.py --server.port=8501 --server.address=0.0.0.0
```

Then open <http://arm-control:8501>.

## Running as a service

Install the packaged unit and enable it:

```bash
mkdir -p ~/.config/systemd/user
cp conf/systemd-units/arm-control/opensauce23-dashboard.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now opensauce23-dashboard.service
```

## Local testing (mock mode)

For development without the ARM at paw, set `DASHBOARD_MOCK=1`.

```bash
python3 -m venv .venv
.venv/bin/pip install streamlit streamlit-autorefresh 'paho-mqtt>=1.6,<2' structlog
DASHBOARD_MOCK=1 .venv/bin/streamlit run dashboard/app.py
```

