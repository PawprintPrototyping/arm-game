"""
    streamlit run dashboard/app.py --server.port=8501 --server.address=0.0.0.0
"""
from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import datetime as dt  # noqa: E402
import time  # noqa: E402

import streamlit as st  # noqa: E402
from streamlit_autorefresh import st_autorefresh  # noqa: E402

from dashboard import game_control, systemctl  # noqa: E402
from dashboard.config import (  # noqa: E402
    GAME_DURATION_SECONDS,
    MQTT_HOST,
    TARGET_COUNT,
    UNITS,
    units_by_host,
)
from dashboard.mock import FakeMqttStateWorker, mock_enabled  # noqa: E402
from dashboard.mqtt_state import MqttStateWorker  # noqa: E402


st.set_page_config(
    page_title="Arm Game Dashboard",
    page_icon="🎯",
    layout="wide",
)

def _fmt_ts(ts: float | None) -> str:
    if ts is None:
        return "—"
    return dt.datetime.fromtimestamp(ts).strftime("%H:%M:%S")


def _report(result: systemctl.CommandResult, action: str) -> None:
    if result.ok:
        st.toast(f"{action}: ok")
    else:
        st.toast(f"{action}: failed (rc={result.returncode})", icon="⚠️")
        if result.stderr:
            st.error(result.stderr.strip())


@st.cache_resource
def _worker() -> MqttStateWorker:
    worker: MqttStateWorker = FakeMqttStateWorker() if mock_enabled() else MqttStateWorker()
    worker.start()
    # Give the initial CONNECT a beat before the first render.
    for _ in range(20):
        if worker.snapshot().connected:
            break
        time.sleep(0.05)
    return worker


worker = _worker()

if mock_enabled():
    st.warning(
        "🧪 Running in **mock mode** (no MQTT broker or systemctl is connected.) ",
        icon="🧪",
    )

snap = worker.snapshot()

col_a, col_b, col_c, col_d = st.columns([1.2, 1, 1, 1])
col_a.subheader("🎯  ARMature")
col_b.metric(
    "MQTT",
    "connected" if snap.connected else "disconnected",
    help=f"broker: {MQTT_HOST}",
)
col_c.metric("Score", snap.score)
col_d.metric("Player", snap.player_name or "—")

st.divider()

tab_control, tab_state, tab_services, tab_logs, tab_mqtt = st.tabs(
    ["Game control", "Live state", "Services", "Logs", "MQTT"],
)


with tab_control:
    st.markdown("#### Game")

    with st.form("start_game"):
        player = st.text_input("Player name", value="", placeholder="optional")
        started = st.form_submit_button("▶️ Start game", type="primary")
        if started:
            game_control.start_game(worker, player or None)
            st.toast("Started game")

    row = st.columns(3)
    if row[0].button("⏹️ Game over"):
        game_control.game_over(worker)
        st.toast("Sent game_over")
    if row[1].button("🧹 Clear scoreboard"):
        game_control.scoreboard_clear(worker)
        game_control.digits_clear(worker)
        st.toast("Cleared scoreboards")
    if row[2].button("🚨 Emergency stop", type="secondary"):
        game_control.stop_all(worker, target_count=TARGET_COUNT)
        st.toast("Emergency stop sent")

    st.markdown("#### Arm")
    r = st.columns(3)
    if r[0].button("Arm: start"):
        game_control.arm_start(worker)
    if r[1].button("Arm: stop / park"):
        game_control.arm_stop(worker)
    if r[2].button("Arm: idle"):
        game_control.arm_idle(worker)

    st.markdown("#### Side target platform")
    r = st.columns(2)
    if r[0].button("Movement: start (flail)"):
        game_control.target_movement_start(worker)
    if r[1].button("Movement: stop"):
        game_control.target_movement_stop(worker)

    st.markdown("#### Targets")
    st.caption(
        "Per-target manual control. Toggle enable/disable, raise, lower, or home individually."
    )
    header = st.columns([0.5, 1, 1, 1, 1, 1])
    header[0].caption("ID")
    header[1].caption("Enable")
    header[2].caption("Disable")
    header[3].caption("Up")
    header[4].caption("Down")
    header[5].caption("Home")
    for tid in range(1, TARGET_COUNT + 1):
        row = st.columns([0.5, 1, 1, 1, 1, 1])
        row[0].markdown(f"**#{tid}**")
        if row[1].button("Enable", key=f"t{tid}_en"):
            game_control.target_enable(worker, tid)
        if row[2].button("Disable", key=f"t{tid}_dis"):
            game_control.target_disable(worker, tid)
        if row[3].button("Up", key=f"t{tid}_up"):
            game_control.target_up(worker, tid)
        if row[4].button("Down", key=f"t{tid}_dn"):
            game_control.target_down(worker, tid)
        if row[5].button("Home", key=f"t{tid}_hm"):
            game_control.target_home(worker, tid)


# Live state tab

with tab_state:
    # Autorefresh so the timer + scores tick in real time.
    st_autorefresh(interval=1000, key="state_autorefresh")
    snap = worker.snapshot()

    top = st.columns(4)
    top[0].metric("Timer state", snap.timer_state)
    remaining = snap.timer_remaining()
    if remaining is not None:
        top[1].metric("Time remaining", f"{remaining:0.1f}s")
    else:
        top[1].metric("Time remaining", "—", help=f"nominal {GAME_DURATION_SECONDS}s")
    top[2].metric("Arm", snap.arm_state)
    top[3].metric("Target platform", snap.target_movement)

    if snap.game_over_message:
        st.info(f"Last game-over message: **{snap.game_over_message}**")

    st.markdown("#### Targets")
    rows = []
    for tid in sorted(snap.targets):
        t = snap.targets[tid]
        rows.append({
            "id": t.target_id,
            "enabled": "✅" if t.enabled else "⛔",
            "raised": "⬆️ up" if t.raised else ("⬇️ down" if t.raised is False else "-"),
            "hits": t.hits,
            "last hit": _fmt_ts(t.last_hit_at),
            "errors": t.error_count,
        })
    st.dataframe(rows, hide_index=True, width="stretch")

    st.markdown("#### Recent MQTT traffic")
    msg_rows = [
        {
            "time": _fmt_ts(ts),
            "topic": topic,
            "payload": (payload[:120] + "…") if len(payload) > 120 else payload,
        }
        for ts, topic, payload in reversed(snap.recent_messages)
    ]
    st.dataframe(msg_rows, hide_index=True, width="stretch", height=300)


# systemd services tab

with tab_services:
    st_autorefresh(interval=3000, key="services_autorefresh")

    for host, unit_list in units_by_host().items():
        st.markdown(f"### `{host}`")
        for unit in unit_list:
            state = systemctl.is_active(host, unit.name)
            colour = {
                "active": "🟢",
                "activating": "🟡",
                "reloading": "🟡",
                "deactivating": "🟡",
                "inactive": "⚪",
                "failed": "🔴",
            }.get(state, "❓")

            row = st.columns([0.4, 3, 1, 1, 1])
            row[0].markdown(colour)
            row[1].markdown(f"**{unit.name}**  \n*{unit.description}* — `{state}`")
            if row[2].button("Start", key=f"start_{host}_{unit.name}"):
                _report(systemctl.start(host, unit.name), f"start {unit.name}")
            if row[3].button("Stop", key=f"stop_{host}_{unit.name}"):
                _report(systemctl.stop(host, unit.name), f"stop {unit.name}")
            if row[4].button("Restart", key=f"restart_{host}_{unit.name}"):
                _report(systemctl.restart(host, unit.name), f"restart {unit.name}")


# Logs

with tab_logs:
    unit_choices = [(u.host, u.name) for u in UNITS]
    labels = [f"{host} · {name}" for host, name in unit_choices]
    idx = st.selectbox(
        "Unit",
        options=range(len(unit_choices)),
        format_func=lambda i: labels[i],
    )
    host, unit_name = unit_choices[idx]
    lines = st.slider("Lines", min_value=50, max_value=1000, value=200, step=50)
    auto = st.checkbox("Auto-refresh every 3s", value=False)
    if auto:
        st_autorefresh(interval=3000, key="logs_autorefresh")
    if st.button("Refresh now") or auto:
        pass  # rerun already happened
    logs = systemctl.tail_logs(host, unit_name, lines=lines)
    st.code(logs or "(no output)", language="log")


# MQTT Debug Tab

with tab_mqtt:
    st.caption(
        "Publish an arbitrary topic. Useful for debugging — check the API docs "
        "under `docs/` for supported topics."
    )
    with st.form("mqtt_publish"):
        topic = st.text_input("Topic", value="scoreboard/digits/snake")
        payload = st.text_area("Payload (raw string, often JSON)", value="")
        submitted = st.form_submit_button("Publish")
        if submitted and topic.strip():
            game_control.publish_raw(worker, topic.strip(), payload)
            st.toast(f"Published to {topic}")

    st_autorefresh(interval=1000, key="mqtt_feed_autorefresh")
    st.markdown("#### Live topic feed")
    snap = worker.snapshot()
    feed_rows = [
        {
            "time": _fmt_ts(ts),
            "topic": topic,
            "payload": payload,
        }
        for ts, topic, payload in reversed(snap.recent_messages)
    ]
    st.dataframe(feed_rows, hide_index=True, width="stretch", height=500)
