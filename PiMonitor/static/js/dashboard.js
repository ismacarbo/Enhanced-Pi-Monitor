"use strict";

const COLORS = {
  grid: "rgba(143, 155, 171, .13)",
  text: "#8f9bab",
  cyan: "#4fd1c5",
  yellow: "#f2c94c",
};

let networkChart;
let sensorChart;
let heatmapChart;
let previousNetworkSample;
const sourceHealth = new Map();

Chart.defaults.color = COLORS.text;
Chart.defaults.borderColor = COLORS.grid;
Chart.defaults.font.family = "Inter, ui-sans-serif, system-ui, sans-serif";

async function apiFetch(path) {
  const response = await fetch(path, {
    headers: { Accept: "application/json" },
    credentials: "same-origin",
  });
  if (response.status === 401) {
    window.location.assign(`/login?next=${encodeURIComponent(window.location.pathname)}`);
    throw new Error("session expired");
  }
  if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
  return response.json();
}

function text(id, value) {
  const element = document.getElementById(id);
  if (element) element.textContent = value;
}

function meter(id, value) {
  const element = document.getElementById(id);
  if (element) element.style.width = `${Math.max(0, Math.min(100, value || 0))}%`;
}

function formatBytes(value, suffix = "") {
  if (!Number.isFinite(value)) return "—";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let amount = Math.max(0, value);
  let index = 0;
  while (amount >= 1024 && index < units.length - 1) {
    amount /= 1024;
    index += 1;
  }
  const digits = amount >= 100 || index === 0 ? 0 : amount >= 10 ? 1 : 2;
  return `${amount.toFixed(digits)} ${units[index]}${suffix}`;
}

function setRefreshState(source, ok) {
  sourceHealth.set(source, ok);
  const refreshFailed = Array.from(sourceHealth.values()).some((value) => !value);
  const state = document.getElementById("refresh-state");
  const dot = state?.querySelector(".status-dot");
  if (dot) dot.className = `status-dot ${refreshFailed ? "offline" : "online"}`;
  text(
    "last-refresh",
    refreshFailed ? "Alcuni dati non sono disponibili" : `Aggiornato ${new Date().toLocaleTimeString("it-IT")}`,
  );
}

async function fetchSystemInfo() {
  try {
    const data = await apiFetch("/api/system");
    const cpu = Number.isFinite(data.cpu_temperature) ? data.cpu_temperature : null;
    text("cpu-value", cpu === null ? "—" : `${cpu.toFixed(1)}°`);
    text("cpu-detail", cpu === null ? "Sensore temperatura non disponibile" : cpu >= 70 ? "Temperatura elevata" : "Temperatura nella norma");
    meter("cpu-meter", cpu === null ? 0 : cpu);

    const memoryPercent = Number(data.memory?.percent) || 0;
    text("memory-value", `${memoryPercent.toFixed(0)}%`);
    text("memory-detail", `${formatBytes(data.memory?.used)} di ${formatBytes(data.memory?.total)}`);
    meter("memory-meter", memoryPercent);

    const diskPercent = Number(data.disk?.percent) || 0;
    text("disk-value", `${diskPercent.toFixed(0)}%`);
    text("disk-detail", `${formatBytes(data.disk?.used)} di ${formatBytes(data.disk?.total)}`);
    meter("disk-meter", diskPercent);

    const voltage = Number.isFinite(data.voltage) ? data.voltage : null;
    text("voltage-value", voltage === null ? "N/D" : `${voltage.toFixed(2)} V`);
    text("voltage-detail", voltage === null ? "Sensore ADC non rilevato" : voltage < 4.8 ? "Tensione sotto soglia" : "Alimentazione nella norma");
    setRefreshState("system", true);
  } catch (error) {
    console.error(error);
    setRefreshState("system", false);
  }
}

function serviceState(service) {
  if (!service?.loaded) return "non installato";
  const pid = service.main_pid ? ` · PID ${service.main_pid}` : "";
  return `${service.active_state}/${service.sub_state}${pid}`;
}

function addDeviceMetric(container, label, value, suffix = "", tone = "") {
  if (value === undefined || value === null || value === "") return;
  const item = document.createElement("span");
  const normalized = typeof value === "number" ? Math.round(value * 10) / 10 : value;
  item.textContent = `${label} ${normalized}${suffix}`;
  if (tone) item.classList.add(`metric-${tone}`);
  container.append(item);
}

function renderDevices(snapshot) {
  const container = document.getElementById("gdp-devices");
  container.replaceChildren();
  const devices = Array.isArray(snapshot?.devices) ? snapshot.devices : [];
  text("gdp-device-count", `${snapshot?.online_count || 0} / ${devices.length}`);
  if (!devices.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = snapshot?.available ? "Nessun device ha ancora pubblicato uno status." : "Snapshot device non ancora disponibile.";
    container.append(empty);
    return;
  }

  devices.forEach((device) => {
    const card = document.createElement("a");
    card.className = "device-card device-card-link";
    card.href = `/devices/${encodeURIComponent(device.device_id)}`;
    card.setAttribute("aria-label", `Apri diagnostica di ${device.device_id}`);
    const header = document.createElement("header");
    const title = document.createElement("h3");
    title.textContent = device.device_id || "device sconosciuto";
    const badge = document.createElement("span");
    badge.className = `status-badge ${device.online ? "status-online" : "status-offline"}`;
    badge.textContent = device.online ? "online" : "offline";
    header.append(title, badge);

    const meta = document.createElement("p");
    meta.className = "device-meta";
    const model = [device.device_type, device.firmware_version].filter(Boolean).join(" · ");
    const age = Number.isFinite(device.age_seconds) ? `${device.age_seconds}s fa` : "mai visto";
    meta.textContent = `${model || "Generic device"} · ${age}`;

    const metrics = document.createElement("div");
    metrics.className = "device-metrics";
    const telemetry = device.telemetry || {};
    const state = device.state || {};
    addDeviceMetric(metrics, "Temp", telemetry.temperature_c, " °C");
    addDeviceMetric(metrics, "Umidità", telemetry.humidity_percent, "%");
    addDeviceMetric(metrics, "Suolo", telemetry.soil_moisture_percent, "%");
    addDeviceMetric(metrics, "Serbatoio", telemetry.tank_percent, "%", "water");
    addDeviceMetric(metrics, "Distanza", telemetry.tank_distance_cm, " cm");
    addDeviceMetric(metrics, "Batteria", telemetry.battery_percent, "%", "power");
    addDeviceMetric(metrics, "Tensione", telemetry.battery_voltage_v, " V");
    addDeviceMetric(metrics, "Luce", telemetry.light_lux, " lx");
    const pumpState = state.pump?.replace("PUMP_STATE_", "").toLowerCase();
    addDeviceMetric(metrics, "Pompa", pumpState, "", pumpState === "on" ? "active" : "");
    addDeviceMetric(metrics, "Modo", state.mode?.replace("IRRIGATION_MODE_", "").toLowerCase());
    if (state.auto_irrigation_running) addDeviceMetric(metrics, "Auto", "in esecuzione", "", "active");
    if (!metrics.childElementCount) addDeviceMetric(metrics, "Health", device.health?.replace("DEVICE_HEALTH_", "").toLowerCase() || "in attesa");

    const capabilities = document.createElement("p");
    capabilities.className = "device-capabilities";
    const capabilityCount = Array.isArray(device.capabilities) ? device.capabilities.length : 0;
    capabilities.textContent = `${capabilityCount} capacità dichiarate`;
    const open = document.createElement("span");
    open.className = "device-open";
    open.textContent = "Apri diagnostica →";
    card.append(header, meta, metrics, capabilities, open);
    container.append(card);
  });
}

async function fetchGdpStatus() {
  try {
    const data = await apiFetch("/api/services/gdp");
    const badge = document.getElementById("gdp-overall-badge");
    badge.className = `status-badge ${data.healthy ? "status-online" : "status-offline"}`;
    badge.textContent = data.healthy ? "Operativo" : "Degradato";
    text("gdp-server-status", serviceState(data.gdp_server));
    text("gdp-mqtt-service-status", serviceState(data.mqtt_service));
    text("gdp-broker-status", data.broker?.reachable ? `${data.broker.host}:${data.broker.port} online` : "non raggiungibile");
    renderDevices(data.device_snapshot);
    text("gdp-status-detail", `Ultimo controllo ${new Date(data.checked_at).toLocaleString("it-IT")}`);
    setRefreshState("gdp", true);
  } catch (error) {
    console.error(error);
    const badge = document.getElementById("gdp-overall-badge");
    badge.className = "status-badge status-offline";
    badge.textContent = "Non disponibile";
    text("gdp-status-detail", "Impossibile leggere lo stato dello stack GDP.");
    setRefreshState("gdp", false);
  }
}

function networkOptions() {
  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 250 },
    interaction: { intersect: false, mode: "index" },
    scales: {
      x: { grid: { display: false }, ticks: { maxTicksLimit: 7 } },
      y: { beginAtZero: true, ticks: { callback: (value) => formatBytes(value, "/s") } },
    },
    plugins: { legend: { display: false }, tooltip: { callbacks: { label: (context) => `${context.dataset.label}: ${formatBytes(context.raw, "/s")}` } } },
  };
}

async function fetchNetworkData() {
  try {
    const data = await apiFetch("/api/network");
    const candidates = Object.entries(data).filter(([name]) => name !== "lo" && !name.startsWith("docker") && !name.startsWith("veth") && !name.startsWith("br-"));
    const [iface, current] = (candidates.length ? candidates : Object.entries(data)).sort((a, b) => (b[1].bytes_recv + b[1].bytes_sent) - (a[1].bytes_recv + a[1].bytes_sent))[0] || [];
    if (!iface || !current) throw new Error("no network interfaces");
    const now = performance.now();
    let rx = 0;
    let tx = 0;
    if (previousNetworkSample?.iface === iface) {
      const elapsed = Math.max(.1, (now - previousNetworkSample.at) / 1000);
      rx = Math.max(0, current.bytes_recv - previousNetworkSample.rx) / elapsed;
      tx = Math.max(0, current.bytes_sent - previousNetworkSample.tx) / elapsed;
    }
    previousNetworkSample = { iface, rx: current.bytes_recv, tx: current.bytes_sent, at: now };
    text("network-interface", iface);
    text("network-rx", formatBytes(rx, "/s"));
    text("network-tx", formatBytes(tx, "/s"));
    const label = new Date().toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    if (!networkChart) {
      networkChart = new Chart(document.getElementById("networkChart"), {
        type: "line",
        data: { labels: [], datasets: [
          { label: "RX", data: [], borderColor: COLORS.cyan, backgroundColor: "rgba(79,209,197,.1)", tension: .35, pointRadius: 0, fill: true },
          { label: "TX", data: [], borderColor: COLORS.yellow, backgroundColor: "rgba(242,201,76,.06)", tension: .35, pointRadius: 0, fill: true },
        ] },
        options: networkOptions(),
      });
    }
    networkChart.data.labels.push(label);
    networkChart.data.datasets[0].data.push(rx);
    networkChart.data.datasets[1].data.push(tx);
    if (networkChart.data.labels.length > 24) {
      networkChart.data.labels.shift();
      networkChart.data.datasets.forEach((dataset) => dataset.data.shift());
    }
    networkChart.update();
    setRefreshState("network", true);
  } catch (error) {
    console.error(error);
    setRefreshState("network", false);
  }
}

async function fetchSensorData() {
  try {
    const samples = await apiFetch("/api/irrigation_data");
    const data = Array.isArray(samples) ? samples : [];
    text("sensor-count", `${data.length} campion${data.length === 1 ? "e" : "i"}`);
    text("sensor-empty", data.length ? `Ultimo campione ${new Date(data.at(-1).time).toLocaleTimeString("it-IT")}` : "In attesa dei primi campioni.");
    const chartData = {
      labels: data.map((sample) => new Date(sample.time).toLocaleTimeString("it-IT")),
      datasets: [
        { label: "Umidità suolo (%)", data: data.map((sample) => sample.moisture), yAxisID: "moisture", borderColor: COLORS.yellow, tension: .3, pointRadius: 1 },
        { label: "Luce (lux)", data: data.map((sample) => sample.light), yAxisID: "light", borderColor: COLORS.cyan, tension: .3, pointRadius: 1 },
      ],
    };
    if (!sensorChart) {
      sensorChart = new Chart(document.getElementById("sensorChart"), {
        type: "line",
        data: chartData,
        options: { responsive: true, maintainAspectRatio: false, interaction: { mode: "index", intersect: false }, plugins: { legend: { labels: { boxWidth: 8, usePointStyle: true } } }, scales: { x: { grid: { display: false }, ticks: { maxTicksLimit: 7 } }, moisture: { type: "linear", position: "left", suggestedMin: 0, suggestedMax: 100 }, light: { type: "linear", position: "right", beginAtZero: true, grid: { drawOnChartArea: false } } } },
      });
    } else {
      sensorChart.data = chartData;
      sensorChart.update();
    }
    setRefreshState("sensors", true);
  } catch (error) {
    console.error(error);
    setRefreshState("sensors", false);
  }
}

async function fetchHeatmap() {
  try {
    const matrix = await apiFetch("/api/occupancy_map.json");
    if (!Array.isArray(matrix) || !matrix.length || !Array.isArray(matrix[0])) throw new Error("invalid occupancy matrix");
    const rows = matrix.length;
    const columns = matrix[0].length;
    const values = [];
    for (let row = 0; row < rows; row += 1) {
      if (!Array.isArray(matrix[row]) || matrix[row].length !== columns) throw new Error("ragged occupancy matrix");
      for (let column = 0; column < columns; column += 1) values.push({ x: column, y: rows - 1 - row, v: Number(matrix[row][column]) || 0 });
    }
    const dataset = { data: values, borderWidth: 0, width: ({ chart }) => (chart.chartArea?.width || 300) / columns, height: ({ chart }) => (chart.chartArea?.height || 300) / rows, backgroundColor: (context) => {
      const value = context.dataset.data[context.dataIndex]?.v || 0;
      const red = Math.round(60 + 195 * value);
      const blue = Math.round(190 - 130 * value);
      return `rgba(${red}, ${Math.round(180 - value * 120)}, ${blue}, .88)`;
    } };
    if (!heatmapChart) {
      heatmapChart = new Chart(document.getElementById("heatmapChart"), {
        type: "matrix",
        data: { datasets: [dataset] },
        options: { responsive: true, maintainAspectRatio: false, animation: false, scales: { x: { display: false, min: -.5, max: columns - .5 }, y: { display: false, min: -.5, max: rows - .5 } }, plugins: { legend: { display: false }, tooltip: { callbacks: { label: (context) => `Occupazione ${(context.raw.v * 100).toFixed(1)}%` } } } },
      });
    } else {
      heatmapChart.data.datasets[0].data = values;
      heatmapChart.update("none");
    }
    text("heatmap-state", `${columns} × ${rows}`);
    setRefreshState("heatmap", true);
  } catch (error) {
    console.error(error);
    text("heatmap-state", "Non disponibile");
    setRefreshState("heatmap", false);
  }
}

async function refreshAll() {
  await Promise.allSettled([fetchSystemInfo(), fetchGdpStatus(), fetchNetworkData(), fetchSensorData(), fetchHeatmap()]);
}

refreshAll();
setInterval(fetchSystemInfo, 30_000);
setInterval(fetchGdpStatus, 10_000);
setInterval(fetchNetworkData, 10_000);
setInterval(fetchSensorData, 10_000);
setInterval(fetchHeatmap, 15_000);
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") refreshAll();
});
