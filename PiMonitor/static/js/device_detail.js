"use strict";

const DEVICE_ID = document.body.dataset.deviceId || "";
const MAX_TREND_SAMPLES = 60;
const COLORS = {
  grid: "rgba(143, 155, 171, .13)",
  text: "#8f9bab",
  cyan: "#4fd1c5",
  yellow: "#f2c94c",
  green: "#65d49a",
  red: "#ff7b86",
  violet: "#a99cff",
};

let trendChart;
let lastMessageId;
let sampleCount = 0;

if (window.Chart) {
  Chart.defaults.color = COLORS.text;
  Chart.defaults.borderColor = COLORS.grid;
  Chart.defaults.font.family = "Inter, ui-sans-serif, system-ui, sans-serif";
}

function element(id) {
  return document.getElementById(id);
}

function text(id, value) {
  const target = element(id);
  if (target) target.textContent = value;
}

function isNumber(value) {
  return typeof value === "number" && Number.isFinite(value);
}

function number(value, digits = 1, suffix = "") {
  return isNumber(value) ? `${value.toFixed(digits)}${suffix}` : "—";
}

function meter(id, value) {
  const target = element(id);
  if (!target) return;
  target.style.width = `${isNumber(value) ? Math.max(0, Math.min(100, value)) : 0}%`;
}

function formatBytes(value) {
  if (!isNumber(value)) return "—";
  const units = ["B", "KB", "MB", "GB"];
  let amount = value;
  let unit = 0;
  while (amount >= 1024 && unit < units.length - 1) {
    amount /= 1024;
    unit += 1;
  }
  return `${amount.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`;
}

function formatDuration(milliseconds) {
  if (!isNumber(milliseconds)) return "—";
  let seconds = Math.floor(milliseconds / 1000);
  const days = Math.floor(seconds / 86400);
  seconds %= 86400;
  const hours = Math.floor(seconds / 3600);
  seconds %= 3600;
  const minutes = Math.floor(seconds / 60);
  seconds %= 60;
  const parts = [];
  if (days) parts.push(`${days}g`);
  if (hours || days) parts.push(`${hours}h`);
  if (minutes || hours || days) parts.push(`${minutes}m`);
  parts.push(`${seconds}s`);
  return parts.join(" ");
}

function enumLabel(value, prefix = "") {
  if (typeof value !== "string" || !value) return "—";
  const normalized = prefix && value.startsWith(prefix) ? value.slice(prefix.length) : value;
  return normalized.toLowerCase().replaceAll("_", " ");
}

function booleanLabel(value) {
  if (value === true) return "sì";
  if (value === false) return "no";
  return "—";
}

async function apiFetch(path) {
  const response = await fetch(path, {
    credentials: "same-origin",
    headers: { Accept: "application/json" },
    cache: "no-store",
  });
  if (response.status === 401) {
    window.location.assign(`/login?next=${encodeURIComponent(window.location.pathname)}`);
    throw new Error("session expired");
  }
  if (!response.ok) {
    const error = new Error(`${path}: HTTP ${response.status}`);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

function setConnectionState(ok, message) {
  const state = element("device-refresh-state");
  const dot = state?.querySelector(".status-dot");
  if (dot) dot.className = `status-dot ${ok ? "online" : "offline"}`;
  text("device-last-refresh", message);
}

function setBadge(id, label, tone) {
  const badge = element(id);
  if (!badge) return;
  badge.className = `status-badge status-${tone}`;
  badge.textContent = label;
}

function renderIdentity(device) {
  const identity = [device.device_type, device.hardware_version, device.firmware_version]
    .filter(Boolean)
    .join(" · ");
  text("device-identity", identity || "Generic GDP device");
  setBadge(
    "device-online-badge",
    device.online ? "online" : "offline",
    device.online ? "online" : "offline",
  );
}

function renderTelemetry(device) {
  const telemetry = device.telemetry || {};

  text("soil-value", number(telemetry.soil_moisture_percent, 1, "%"));
  meter("soil-meter", telemetry.soil_moisture_percent);
  const soilRaw = isNumber(telemetry.soil_raw) ? `ADC ${telemetry.soil_raw}` : "ADC —";
  const calibration = telemetry.soil_calibrated === true ? "calibrato" : "non calibrato";
  text("soil-detail", `${soilRaw} · ${calibration}`);

  text("temperature-value", number(telemetry.temperature_c, 1, " °C"));
  text("humidity-value", `Umidità ${number(telemetry.humidity_percent, 1, "%")}`);
  text(
    "environment-detail",
    isNumber(telemetry.temperature_c) || isNumber(telemetry.humidity_percent)
      ? "Dati ambientali ricevuti"
      : "DHT22 senza un campione valido",
  );

  text("tank-value", number(telemetry.tank_percent, 1, "%"));
  meter("tank-meter", telemetry.tank_percent);
  text(
    "tank-detail",
    telemetry.tank_valid === true
      ? `Distanza ${number(telemetry.tank_distance_cm, 1, " cm")}`
      : "Misura serbatoio non valida",
  );

  text("battery-value", number(telemetry.battery_percent, 1, "%"));
  meter("battery-meter", telemetry.battery_percent);
  const voltage = number(telemetry.battery_voltage_v, 2, " V");
  const batteryRaw = isNumber(telemetry.battery_raw) ? `ADC ${telemetry.battery_raw}` : "ADC —";
  text(
    "battery-detail",
    telemetry.battery_valid === true ? `${voltage} · ${batteryRaw}` : "Misura batteria non valida",
  );
}

function renderIrrigationState(device) {
  const state = device.state || {};
  const pump = enumLabel(state.pump, "PUMP_STATE_");
  const pumpTone = pump === "on" ? "online" : pump === "fault" ? "offline" : "neutral";
  setBadge("pump-badge", `pompa ${pump}`, pumpTone);
  text("state-mode", enumLabel(state.mode, "IRRIGATION_MODE_"));
  text("state-pump", pump);
  text("state-auto", booleanLabel(state.auto_irrigation_running));
  text("state-remaining", formatDuration(state.remaining_ms));
  text("state-tank-safety", booleanLabel(state.tank_safety_enabled));
  text("state-command-id", String(state.active_command_id || "nessuno"));
}

function renderRuntime(device) {
  const health = enumLabel(device.health, "DEVICE_HEALTH_");
  const healthOk = device.health === "DEVICE_HEALTH_OK";
  setBadge(
    "health-badge",
    health,
    healthOk ? "online" : device.health ? "offline" : "neutral",
  );
  const lastSeen = device.last_seen ? new Date(device.last_seen) : null;
  text(
    "runtime-last-seen",
    lastSeen && !Number.isNaN(lastSeen.valueOf())
      ? `${lastSeen.toLocaleString("it-IT")} · ${device.age_seconds ?? "—"}s fa`
      : "—",
  );
  text("runtime-uptime", formatDuration(device.uptime_ms));
  text("runtime-heap", formatBytes(device.free_heap_bytes));
  text("runtime-firmware", device.firmware_version || "—");
  text("runtime-hardware", device.hardware_version || "—");
  text("runtime-status-message", device.status_message || "—");
}

function renderProtocol(payload) {
  const message = payload.device.last_message || {};
  const domains = { 0: "core (0)", 100: "environment (100)", 101: "irrigation (101)", 102: "power (102)" };
  text("protocol-message-id", message.message_id || "—");
  text("protocol-category", enumLabel(message.category, "MESSAGE_CATEGORY_"));
  text("protocol-domain", domains[message.domain_id] || `domain ${message.domain_id ?? "—"}`);
  text("protocol-domain-version", message.domain_version ?? "—");
  text("protocol-message-type", message.message_type ?? "—");
  text(
    "protocol-broker",
    payload.broker?.reachable
      ? `${payload.broker.host}:${payload.broker.port} online`
      : "non raggiungibile",
  );
}

function renderCapabilities(capabilities) {
  const container = element("capability-list");
  if (!container) return;
  container.replaceChildren();
  const values = Array.isArray(capabilities) ? capabilities : [];
  text("capability-count", String(values.length));
  if (!values.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "Nessuna capability dichiarata.";
    container.append(empty);
    return;
  }
  values.forEach((capability) => {
    const item = document.createElement("span");
    item.textContent = capability;
    container.append(item);
  });
}

function fieldLabel(key) {
  return key.replaceAll("_", " ");
}

function fieldValue(value) {
  if (value === null || value === undefined) return "N/D";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : String(Math.round(value * 100) / 100);
  return String(value);
}

function renderFields(id, values) {
  const container = element(id);
  if (!container) return;
  container.replaceChildren();
  const entries = Object.entries(values || {}).sort(([left], [right]) => left.localeCompare(right));
  if (!entries.length) {
    const row = document.createElement("div");
    const term = document.createElement("dt");
    const description = document.createElement("dd");
    term.textContent = "Stato";
    description.textContent = "Nessun dato";
    row.append(term, description);
    container.append(row);
    return;
  }
  entries.forEach(([key, value]) => {
    const row = document.createElement("div");
    const term = document.createElement("dt");
    const description = document.createElement("dd");
    term.textContent = fieldLabel(key);
    description.textContent = fieldValue(value);
    row.append(term, description);
    container.append(row);
  });
}

function renderDiagnostics(payload) {
  renderFields("telemetry-fields", payload.device.telemetry);
  renderFields("state-fields", payload.device.state);
  const snapshotTime = payload.snapshot_updated_at ? new Date(payload.snapshot_updated_at) : null;
  text(
    "snapshot-time",
    snapshotTime && !Number.isNaN(snapshotTime.valueOf())
      ? snapshotTime.toLocaleTimeString("it-IT")
      : "—",
  );
  text("device-json", JSON.stringify(payload, null, 2));
}

function createTrendChart() {
  if (!window.Chart) return null;
  return new Chart(element("deviceTrendChart"), {
    type: "line",
    data: {
      labels: [],
      datasets: [
        { label: "Suolo %", key: "soil_moisture_percent", data: [], borderColor: COLORS.yellow, yAxisID: "percentage" },
        { label: "Umidità %", key: "humidity_percent", data: [], borderColor: COLORS.cyan, yAxisID: "percentage" },
        { label: "Serbatoio %", key: "tank_percent", data: [], borderColor: COLORS.violet, yAxisID: "percentage" },
        { label: "Batteria %", key: "battery_percent", data: [], borderColor: COLORS.green, yAxisID: "percentage" },
        { label: "Temperatura °C", key: "temperature_c", data: [], borderColor: COLORS.red, yAxisID: "temperature" },
      ].map((dataset) => ({ ...dataset, tension: .3, pointRadius: 1, spanGaps: true })),
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 180 },
      interaction: { mode: "index", intersect: false },
      plugins: { legend: { labels: { boxWidth: 8, usePointStyle: true } } },
      scales: {
        x: { grid: { display: false }, ticks: { maxTicksLimit: 8 } },
        percentage: { type: "linear", position: "left", min: 0, max: 100 },
        temperature: { type: "linear", position: "right", suggestedMin: 0, suggestedMax: 45, grid: { drawOnChartArea: false } },
      },
    },
  });
}

function appendTrendSample(device) {
  const messageId = device.last_message?.message_id;
  if (messageId && messageId === lastMessageId) return;
  lastMessageId = messageId;
  if (!trendChart) trendChart = createTrendChart();
  if (!trendChart) return;

  trendChart.data.labels.push(new Date().toLocaleTimeString("it-IT"));
  trendChart.data.datasets.forEach((dataset) => {
    const value = device.telemetry?.[dataset.key];
    dataset.data.push(isNumber(value) ? value : null);
  });
  if (trendChart.data.labels.length > MAX_TREND_SAMPLES) {
    trendChart.data.labels.shift();
    trendChart.data.datasets.forEach((dataset) => dataset.data.shift());
  }
  sampleCount += 1;
  text("trend-count", `${Math.min(sampleCount, MAX_TREND_SAMPLES)} campioni`);
  trendChart.update();
}

function render(payload) {
  const device = payload.device;
  element("device-not-found").hidden = true;
  renderIdentity(device);
  renderTelemetry(device);
  renderIrrigationState(device);
  renderRuntime(device);
  renderProtocol(payload);
  renderCapabilities(device.capabilities);
  renderDiagnostics(payload);
  appendTrendSample(device);
}

async function refreshDevice() {
  try {
    const payload = await apiFetch(`/api/services/gdp/devices/${encodeURIComponent(DEVICE_ID)}`);
    render(payload);
    setConnectionState(true, `Aggiornato ${new Date().toLocaleTimeString("it-IT")}`);
  } catch (error) {
    console.error(error);
    if (error.status === 404) {
      element("device-not-found").hidden = false;
      setBadge("device-online-badge", "non trovato", "offline");
      setConnectionState(false, "Device non trovato");
      return;
    }
    setConnectionState(false, "Dati non disponibili");
  }
}

refreshDevice();
setInterval(() => {
  if (document.visibilityState === "visible") refreshDevice();
}, 3_000);
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") refreshDevice();
});
