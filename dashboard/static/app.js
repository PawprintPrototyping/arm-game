
const STORAGE_KEY = "arm-game-dashboard-settings";

function loadSettings() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {};
  } catch {
    return {};
  }
}

function saveSettings(state) {
  const payload = {
    mqttMode: state.mqttMode,
    brokerWs: state.brokerWs,
    subscriptions: state.subscriptions,
    autoRefreshServices: state.autoRefreshServices,
    logAutoscroll: state.logAutoscroll,
    messagesAutoscroll: state.messagesAutoscroll,
  };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
}

function nextId() { return Math.random().toString(36).slice(2) + Date.now().toString(36); }


class RelayTransport {
  constructor(handlers) {
    this.handlers = handlers;
    this.ws = null;
    this.reconnectTimer = null;
    this.desired = new Map(); // topic -> qos
    this.closed = false;
  }
  connect() {
    this.closed = false;
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const url = `${proto}://${location.host}/ws/mqtt`;
    this.ws = new WebSocket(url);
    this.ws.onopen = () => {
      // Re-send subscriptions after reconnect.
      for (const [topic, qos] of this.desired.entries()) {
        this._send({ op: "subscribe", topic, qos });
      }
    };
    this.ws.onclose = () => {
      this.handlers.onStatus?.({ connected: false, reason: "relay socket closed" });
      if (!this.closed) {
        this.reconnectTimer = setTimeout(() => this.connect(), 2000);
      }
    };
    this.ws.onerror = () => {
      this.handlers.onStatus?.({ connected: false, reason: "relay socket error" });
    };
    this.ws.onmessage = (ev) => {
      let data;
      try { data = JSON.parse(ev.data); } catch { return; }
      switch (data.type) {
        case "hello":
          this.handlers.onHello?.(data);
          this.handlers.onStatus?.({ connected: !!data.connected, reason: "hello" });
          break;
        case "status":
          this.handlers.onStatus?.({ connected: !!data.connected, reason: data.reason });
          break;
        case "message":
          this.handlers.onMessage?.({
            topic: data.topic,
            payload: data.payload,
            retain: data.retain,
            qos: data.qos,
            ts: (data.ts || Date.now() / 1000) * 1000,
          });
          break;
        case "error":
          this.handlers.onError?.(data.message);
          break;
      }
    };
  }
  close() {
    this.closed = true;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    if (this.ws) this.ws.close();
  }
  _send(payload) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(payload));
    }
  }
  subscribe(topic, qos = 0) {
    this.desired.set(topic, qos);
    this._send({ op: "subscribe", topic, qos });
  }
  unsubscribe(topic) {
    this.desired.delete(topic);
    this._send({ op: "unsubscribe", topic });
  }
  publish(topic, payload, opts = {}) {
    this._send({
      op: "publish",
      topic,
      payload: payload ?? "",
      qos: opts.qos ?? 0,
      retain: !!opts.retain,
    });
  }
  get label() { return "relay"; }
}

/**
 * Direct transport: connects to the mosquitto websockets listener using mqtt.js.
 */
class DirectTransport {
  constructor(handlers, config) {
    this.handlers = handlers;
    this.config = config;
    this.client = null;
    this.desired = new Map();
  }
  connect() {
    const scheme = this.config.tls ? "wss" : "ws";
    const host = this.config.host || location.hostname;
    const path = this.config.path?.startsWith("/") ? this.config.path : `/${this.config.path || ""}`;
    const url = `${scheme}://${host}:${this.config.port}${path}`;
    // eslint-disable-next-line no-undef
    this.client = mqtt.connect(url, {
      reconnectPeriod: 2000,
      keepalive: 30,
      clean: true,
    });
    this.client.on("connect", () => {
      this.handlers.onStatus?.({ connected: true, reason: `direct ${url}` });
      for (const [topic, qos] of this.desired.entries()) {
        this.client.subscribe(topic, { qos });
      }
    });
    this.client.on("reconnect", () => {
      this.handlers.onStatus?.({ connected: false, reason: "reconnecting" });
    });
    this.client.on("close", () => {
      this.handlers.onStatus?.({ connected: false, reason: "direct socket closed" });
    });
    this.client.on("error", (err) => {
      this.handlers.onError?.(String(err?.message || err));
    });
    this.client.on("message", (topic, payload, packet) => {
      let text;
      try { text = new TextDecoder("utf-8", { fatal: false }).decode(payload); }
      catch { text = `0x${[...payload].map((b) => b.toString(16).padStart(2, "0")).join("")}`; }
      this.handlers.onMessage?.({
        topic,
        payload: text,
        retain: !!packet.retain,
        qos: packet.qos,
        ts: Date.now(),
      });
    });
  }
  close() {
    if (this.client) this.client.end(true);
  }
  subscribe(topic, qos = 0) {
    this.desired.set(topic, qos);
    if (this.client && this.client.connected) this.client.subscribe(topic, { qos });
  }
  unsubscribe(topic) {
    this.desired.delete(topic);
    if (this.client) this.client.unsubscribe(topic);
  }
  publish(topic, payload, opts = {}) {
    if (!this.client) return;
    this.client.publish(topic, payload ?? "", {
      qos: opts.qos ?? 0,
      retain: !!opts.retain,
    });
  }
  get label() { return "direct"; }
}


function dashboardFactory() {
  const saved = loadSettings();

  return {
    // UI state
    tab: "services",
    config: {},

    // services
    services: [],
    loadingServices: false,
    autoRefreshServices: saved.autoRefreshServices ?? true,
    _refreshTimer: null,
    lastActionResult: "",

    // logs
    logUnit: "",
    logLines: [],
    logStreamActive: false,
    _logWs: null,
    logAutoscroll: saved.logAutoscroll ?? true,

    // mqtt
    mqttMode: saved.mqttMode || "relay",
    brokerWs: saved.brokerWs || { host: "", port: 9001, path: "/mqtt", tls: false },
    transport: null,
    mqttConnected: false,
    mqttStatusReason: "",
    mqttTransport: "relay",
    subscriptions: saved.subscriptions || ["#"],
    subTopicInput: "",
    pubTopic: "",
    pubPayload: "",
    pubRetain: false,
    pubQos: 0,
    messages: [],
    messagesAutoscroll: saved.messagesAutoscroll ?? true,

    playerName: "",

    // Target health / availability, populated from the score handler's retained
    // messages on `target/{id}/health` and `targets/available` (see
    // motion/target_scoring_serial.py). Both topics are always-on subscriptions
    // so the info stays fresh regardless of which MQTT tab subs the user set.
    targetHealth: {},        // { [id: number]: snapshot }
    targetHealthUpdated: {}, // { [id: number]: epoch ms }
    targetsAvailable: null,  // number[] once discovery has published, else null

    // Always-on subscription set — distinct from `subscriptions` (which the
    // user controls in the MQTT tab). Messages on these topics are surfaced
    // to the MQTT message list too, so operators can still see them.
    SYSTEM_SUBSCRIPTIONS: ["target/+/health", "targets/available"],

    async init() {
      await this.fetchConfig();
      await this.refreshServices();
      this.startMqtt();

      this._refreshTimer = setInterval(() => {
        if (this.autoRefreshServices && this.tab === "services") {
          this.refreshServices();
        }
      }, 5000);

      // Tick relative-age labels once a second so "12s ago" stays honest.
      this._ageTimer = setInterval(() => { this._nowTick = Date.now(); }, 1000);

      // Persist state changes.
      this.$watch("mqttMode", () => this.persist());
      this.$watch("brokerWs", () => this.persist(), { deep: true });
      this.$watch("subscriptions", () => this.persist(), { deep: true });
      this.$watch("autoRefreshServices", () => this.persist());
      this.$watch("logAutoscroll", () => this.persist());
      this.$watch("messagesAutoscroll", () => this.persist());

      // Auto-scroll log panels.
      this.$watch("messages", () => {
        if (!this.messagesAutoscroll) return;
        this.$nextTick(() => {
          const el = this.$refs.messageView;
          if (el) el.scrollTop = el.scrollHeight;
        });
      }, { deep: false });
      this.$watch("logLines", () => {
        if (!this.logAutoscroll) return;
        this.$nextTick(() => {
          const el = this.$refs.logView;
          if (el) el.scrollTop = el.scrollHeight;
        });
      }, { deep: false });
    },

    persist() { saveSettings(this); },

    async fetchConfig() {
      const r = await fetch("/api/config");
      if (r.ok) {
        this.config = await r.json();
        const mq = this.config.mqtt || {};
        // Only overwrite frontend broker config if the user hasn't customised.
        if (!this.brokerWs.host && mq.ws_host) this.brokerWs.host = mq.ws_host;
        if (mq.ws_port && !saved.brokerWs?.port) this.brokerWs.port = mq.ws_port;
        if (mq.ws_path && !saved.brokerWs?.path) this.brokerWs.path = mq.ws_path;
        if (typeof mq.ws_tls === "boolean" && saved.brokerWs?.tls === undefined) {
          this.brokerWs.tls = mq.ws_tls;
        }
      }
    },

    async refreshServices() {
      this.loadingServices = true;
      try {
        const r = await fetch("/api/services");
        if (r.ok) {
          const data = await r.json();
          this.services = data.services;
        }
      } finally {
        this.loadingServices = false;
      }
    },

    async doAction(unit, verb) {
      const r = await fetch(`/api/services/${encodeURIComponent(unit)}/${verb}`, {
        method: "POST",
      });
      const body = await r.json().catch(() => ({}));
      const stamp = new Date().toISOString();
      const outParts = [];
      outParts.push(`[${stamp}] ${verb} ${unit} → ${body.ok ? "ok" : "FAIL"} (rc=${body.returncode})`);
      if (body.stdout) outParts.push(body.stdout.trim());
      if (body.stderr) outParts.push(body.stderr.trim());
      this.lastActionResult = outParts.filter(Boolean).join("\n");
      // Small delay before refreshing so systemd has a chance to settle.
      setTimeout(() => this.refreshServices(), 500);
    },

    openLogs(unit) {
      this.logUnit = unit;
      this.tab = "logs";
      this.stopLogStream();
      this.logLines = [];
      this.startLogStream();
    },

    startLogStream() {
      if (!this.logUnit || this.logStreamActive) return;
      const proto = location.protocol === "https:" ? "wss" : "ws";
      const url = `${proto}://${location.host}/ws/logs/${encodeURIComponent(this.logUnit)}`;
      this._logWs = new WebSocket(url);
      this.logStreamActive = true;
      this._logWs.onmessage = (ev) => {
        this.logLines.push({ id: nextId(), text: ev.data });
        if (this.logLines.length > 2000) this.logLines.splice(0, this.logLines.length - 2000);
      };
      this._logWs.onclose = () => { this.logStreamActive = false; };
      this._logWs.onerror = () => { this.logStreamActive = false; };
    },

    stopLogStream() {
      if (this._logWs) this._logWs.close();
      this._logWs = null;
      this.logStreamActive = false;
    },

    // ─────────────────────────── mqtt ───────────────────────────
    startMqtt() {
      if (this.transport) this.transport.close();
      const handlers = {
        onHello: (m) => {
          // If backend advertises its ws broker, seed direct-config defaults.
          if (m.ws_broker) {
            if (!this.brokerWs.host && m.ws_broker.host) this.brokerWs.host = m.ws_broker.host;
          }
        },
        onStatus: ({ connected, reason }) => {
          this.mqttConnected = !!connected;
          this.mqttStatusReason = reason || "";
        },
        onMessage: (msg) => {
          this.messages.push({ id: nextId(), ...msg });
          if (this.messages.length > 500) this.messages.splice(0, this.messages.length - 500);
          this.routeSystemMessage(msg);
        },
        onError: (msg) => {
          this.mqttStatusReason = msg;
        },
      };
      if (this.mqttMode === "direct") {
        this.transport = new DirectTransport(handlers, this.brokerWs);
      } else {
        this.transport = new RelayTransport(handlers);
      }
      this.mqttTransport = this.transport.label;
      this.transport.connect();
      // Always-on system subscriptions (target health etc.) — these are not
      // user-visible in the MQTT tab's subscription list.
      for (const topic of this.SYSTEM_SUBSCRIPTIONS) this.transport.subscribe(topic);
      // Re-subscribe to persisted user topics.
      for (const topic of this.subscriptions) this.transport.subscribe(topic);
    },

    // Pick out the topics we care about ourselves and update state accordingly.
    // Everything still passes through to the MQTT tab's message log first.
    routeSystemMessage(msg) {
      const health = msg.topic.match(/^target\/(\d+)\/health$/);
      if (health) {
        const id = parseInt(health[1], 10);
        try {
          const snap = JSON.parse(msg.payload);
          this.targetHealth[id] = snap;
          this.targetHealthUpdated[id] = msg.ts || Date.now();
        } catch {
          // Ignore malformed payloads; leave last-known snapshot in place.
        }
        return;
      }
      if (msg.topic === "targets/available") {
        try {
          const data = JSON.parse(msg.payload);
          if (Array.isArray(data.targets)) {
            this.targetsAvailable = data.targets.slice().sort((a, b) => a - b);
          }
        } catch {
          /* ignore */
        }
      }
    },

    reconnectMqtt() {
      this.persist();
      this.startMqtt();
    },

    addSubscription() {
      const topic = this.subTopicInput.trim();
      if (!topic) return;
      if (!this.subscriptions.includes(topic)) {
        this.subscriptions.push(topic);
        this.transport?.subscribe(topic);
      }
      this.subTopicInput = "";
    },

    removeSubscription(topic) {
      this.subscriptions = this.subscriptions.filter((t) => t !== topic);
      this.transport?.unsubscribe(topic);
    },

    publishForm() {
      if (!this.pubTopic) return;
      this.transport?.publish(this.pubTopic, this.pubPayload, {
        qos: this.pubQos,
        retain: this.pubRetain,
      });
    },

    publishRaw(topic, payload = "", opts = {}) {
      this.transport?.publish(topic, payload, opts);
    },


    gameStart() {
      // TODO: This should send a 5-second countdown timer to the RGB board
      this.publishRaw("scoreboard/digits/clear", "");
      this.publishRaw("scoreboard/rgb/start_timer", "");
      this.publishRaw("motion/motion/start", "");
      this.publishRaw("target_movement/start", "");
    },
    gameStop() {
      this.publishRaw("scoreboard/rgb/game_over", JSON.stringify({ text: "STOPPED" }));
      this.publishRaw("motion/motion/stop", "");
      this.publishRaw("target_movement/stop", "");
      this.allTargets("disable");
    },
    clearScoreboard() {
      this.publishRaw("scoreboard/digits/clear", "");
      this.publishRaw("scoreboard/rgb/clear", "");
    },
    setPlayer() {
      const name = this.playerName.trim();
      if (!name) return;
      this.publishRaw("scoreboard/player_info", JSON.stringify({ name }));
    },
    allTargets(verb) {
      for (let i = 1; i <= 8; i++) this.publishRaw(`targets/${i}/${verb}`, "");
    },
    targetAction(id, verb) {
      this.publishRaw(`targets/${id}/${verb}`, "");
    },

    // Target list rendered in the Game tab. Prefers whatever discovery has
    // announced; falls back to 1..8 so the UI is usable before targets/available
    // arrives (or when no broker is up yet).
    get targetIds() {
      if (Array.isArray(this.targetsAvailable) && this.targetsAvailable.length) {
        return this.targetsAvailable;
      }
      return [1, 2, 3, 4, 5, 6, 7, 8];
    },

    // Was this target discovered? Used to dim UI for missing targets.
    isTargetAvailable(id) {
      if (!Array.isArray(this.targetsAvailable)) return true;
      return this.targetsAvailable.includes(id);
    },

    // Pretty-print `error_rate` (0..1) as a percentage.
    formatErrorRate(snap) {
      if (!snap || typeof snap.error_rate !== "number") return "—";
      return `${(snap.error_rate * 100).toFixed(1)}%`;
    },

    // "12s ago" style relative time, driven by a manual tick so Alpine
    // re-renders even though `targetHealthUpdated` values aren't changing.
    _nowTick: Date.now(),
    formatAge(ms) {
      if (!ms) return "never";
      const seconds = Math.max(0, Math.round((this._nowTick - ms) / 1000));
      if (seconds < 60) return `${seconds}s ago`;
      const minutes = Math.floor(seconds / 60);
      if (minutes < 60) return `${minutes}m ago`;
      return `${Math.floor(minutes / 60)}h ago`;
    },

    formatTs(ts) {
      if (!ts) return "";
      const d = new Date(ts);
      return d.toTimeString().slice(0, 8) + "." + String(d.getMilliseconds()).padStart(3, "0");
    },
  };
}

// Debug
window.dashboardFactory = dashboardFactory;

// Register with Alpine before it starts walking the DOM. Alpine.data() takes the factory directly and re-invokes it for each component instance.
document.addEventListener("alpine:init", () => {
  // eslint-disable-next-line no-undef
  Alpine.data("dashboard", dashboardFactory);
});
