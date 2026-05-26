const state = {
  ws: null,
  reconnectDelay: 500,
  samples: [],
  events: [],
  latestEventId: null,
  pollTimer: null,
};

const $ = (id) => document.getElementById(id);

const chart = new Chart($("chart"), {
  type: "line",
  data: {
    labels: [],
    datasets: [
      { label: "BFI variance", data: [], borderColor: "#34e7ff", tension: 0.3, yAxisID: "y" },
      { label: "Motion score", data: [], borderColor: "#ff4d6d", tension: 0.3, yAxisID: "y1" },
    ],
  },
  options: {
    responsive: true,
    animation: false,
    scales: {
      x: { ticks: { color: "#92a3b8", maxTicksLimit: 8 }, grid: { color: "rgba(255,255,255,0.06)" } },
      y: { ticks: { color: "#92a3b8" }, grid: { color: "rgba(255,255,255,0.06)" } },
      y1: { position: "right", min: 0, max: 1, ticks: { color: "#92a3b8" }, grid: { drawOnChartArea: false } },
    },
    plugins: { legend: { labels: { color: "#edf7ff" } } },
  },
});

function setConnection(status) {
  const el = $("connection");
  el.textContent = status;
  el.className = `connection ${status}`;
}

function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  state.ws = new WebSocket(`${proto}://${location.host}/ws/live`);
  state.ws.onopen = () => {
    state.reconnectDelay = 500;
    setConnection("connected");
    if (state.pollTimer) clearInterval(state.pollTimer);
  };
  state.ws.onmessage = (event) => handleMessage(JSON.parse(event.data));
  state.ws.onclose = () => scheduleReconnect();
  state.ws.onerror = () => {
    setConnection("disconnected");
    state.ws.close();
  };
}

function scheduleReconnect() {
  setConnection("reconnecting");
  setTimeout(connect, state.reconnectDelay);
  state.reconnectDelay = Math.min(state.reconnectDelay * 1.8, 8000);
  if (!state.pollTimer) state.pollTimer = setInterval(fetchStatus, 2000);
}

function handleMessage(message) {
  if (message.type === "sample") addSample(message);
  if (message.type === "event") fetchEvents();
  if (message.type === "event_label") fetchEvents();
  if (message.type === "baseline") updateBaseline(message.baseline);
}

function addSample(sample) {
  state.samples.unshift(sample);
  state.samples = state.samples.slice(0, 40);
  updateStatus(sample);
  renderSamples();
  const time = new Date(sample.timestamp).toLocaleTimeString();
  chart.data.labels.push(time);
  chart.data.datasets[0].data.push(sample.bfi_variance);
  chart.data.datasets[1].data.push(sample.motion_score);
  if (chart.data.labels.length > 80) {
    chart.data.labels.shift();
    chart.data.datasets.forEach((d) => d.data.shift());
  }
  chart.update();
}

function updateStatus(sample) {
  const status = sample.status || "quiet";
  $("statusText").textContent = status.toUpperCase();
  $("statusText").className = `status-text ${status}`;
  $("scoreText").textContent = Number(sample.motion_score || 0).toFixed(2);
  $("scoreMeter").style.width = `${Math.round((sample.motion_score || 0) * 100)}%`;
  $("sourceText").textContent = `source: ${sample.source || "unknown"}`;
  $("sampleTime").textContent = new Date(sample.timestamp).toLocaleString();
  $("radar").className = `radar ${status}`;
  $("pulse").style.inset = `${Math.max(8, 42 - (sample.motion_score || 0) * 30)}%`;
}

function renderSamples() {
  $("samples").innerHTML = state.samples.slice(0, 18).map((s) => `
    <tr>
      <td>${new Date(s.timestamp).toLocaleTimeString()}</td>
      <td class="${s.status}">${s.status}</td>
      <td>${Number(s.motion_score).toFixed(2)}</td>
      <td>${Number(s.bfi_variance).toFixed(3)}</td>
      <td>${s.rssi ? Number(s.rssi).toFixed(1) : "-"}</td>
    </tr>
  `).join("");
}

function renderEvents() {
  $("events").innerHTML = state.events.slice(0, 20).map((e) => `
    <div class="event-item ${e.status}">
      <strong>#${e.id} ${e.status}</strong>
      <div>${new Date(e.start_timestamp).toLocaleString()}${e.end_timestamp ? ` - ${new Date(e.end_timestamp).toLocaleTimeString()}` : ""}</div>
      <div>peak ${Number(e.peak_motion_score).toFixed(2)} | avg ${Number(e.avg_motion_score).toFixed(2)} | ${e.label || "unknown"}</div>
    </div>
  `).join("");
}

function updateBaseline(b) {
  if (!b) return;
  $("baselineCreated").textContent = new Date(b.created_at).toLocaleString();
  $("baselineMean").textContent = Number(b.mean_bfi_variance).toFixed(5);
  $("baselineStd").textContent = Number(b.std_bfi_variance).toFixed(5);
}

async function fetchStatus() {
  const res = await fetch("/api/status");
  const data = await res.json();
  if (data.latest_sample) addSample(data.latest_sample);
  if (data.latest_baseline) updateBaseline(data.latest_baseline);
  if (data.latest_event) {
    state.latestEventId = data.latest_event.id;
    fetchEvents();
  }
}

async function fetchEvents() {
  const res = await fetch("/api/events");
  state.events = await res.json();
  state.latestEventId = state.events[0]?.id || null;
  renderEvents();
}

async function post(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text);
  }
  return res.json();
}

$("baselineBtn").onclick = async () => {
  const baseline = await post("/api/baseline/create-from-recent", { duration_seconds: 300, notes: "quiet house" });
  updateBaseline(baseline);
};
$("startBtn").onclick = () => post("/api/simulate/start");
$("stopBtn").onclick = () => post("/api/simulate/stop");
document.querySelectorAll("[data-label]").forEach((btn) => {
  btn.onclick = async () => {
    if (!state.latestEventId) return;
    await post(`/api/events/${state.latestEventId}/label`, { label: btn.dataset.label, notes: "labeled from dashboard" });
    fetchEvents();
  };
});

connect();
fetchStatus();
fetchEvents();
