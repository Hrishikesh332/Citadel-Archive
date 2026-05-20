const state = {
  snapshot: null,
  nodes: new Map(),
  edges: [],
  selectedId: null,
  paused: false,
  draggingId: null,
  eventSource: null,
  animationFrame: null,
};

const canvas = document.getElementById("graphCanvas");
const ctx = canvas.getContext("2d");
const connectionLabel = document.getElementById("connectionLabel");
const graphMeta = document.getElementById("graphMeta");
const selectedNode = document.getElementById("selectedNode");
const indexList = document.getElementById("indexList");
const eventList = document.getElementById("eventList");
const eventCount = document.getElementById("eventCount");
const upgradeStatus = document.getElementById("upgradeStatus");

const colors = {
  dataset: "#74e0bd",
  document: "#d99b55",
  tag: "#b6b0a4",
  index: "#8ac7ff",
  query: "#f1c46b",
  feedback: "#ff9aa4",
  upgrade: "#62d58e",
};

function api(path, options = {}) {
  return fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  }).then(async (response) => {
    const text = await response.text();
    const data = text ? JSON.parse(text) : null;
    if (!response.ok) {
      const message = data?.detail || data?.message || "Request failed";
      throw new Error(message);
    }
    return data;
  });
}

function setBusy(button, busy, label) {
  button.disabled = busy;
  button.setAttribute("aria-busy", busy ? "true" : "false");
  if (label) {
    button.textContent = busy ? label.loading : label.idle;
  }
}

function resizeCanvas() {
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.max(1, Math.floor(rect.width * dpr));
  canvas.height = Math.max(1, Math.floor(rect.height * dpr));
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
}

function mergeGraph(snapshot) {
  state.snapshot = snapshot;
  const rect = canvas.getBoundingClientRect();
  const centerX = Math.max(rect.width / 2, 320);
  const centerY = Math.max(rect.height / 2, 240);
  const nextIds = new Set();

  snapshot.nodes.forEach((node, index) => {
    nextIds.add(node.id);
    const existing = state.nodes.get(node.id);
    if (existing) {
      Object.assign(existing, node);
      return;
    }
    const angle = (index / Math.max(snapshot.nodes.length, 1)) * Math.PI * 2;
    const radius = 110 + (index % 4) * 34;
    state.nodes.set(node.id, {
      ...node,
      x: centerX + Math.cos(angle) * radius,
      y: centerY + Math.sin(angle) * radius,
      vx: 0,
      vy: 0,
    });
  });

  for (const id of state.nodes.keys()) {
    if (!nextIds.has(id)) {
      state.nodes.delete(id);
    }
  }

  state.edges = snapshot.edges;
  renderSnapshot(snapshot);
}

function renderSnapshot(snapshot) {
  graphMeta.textContent = `${snapshot.default_dataset} - rev ${snapshot.revision} - ${snapshot.generated_at}`;
  document.getElementById("statNodes").textContent = snapshot.stats.nodes;
  document.getElementById("statEdges").textContent = snapshot.stats.edges;
  document.getElementById("statDocuments").textContent = snapshot.stats.documents;
  document.getElementById("statUpgrades").textContent = snapshot.stats.upgrades;
  eventCount.textContent = String(snapshot.events.length);

  indexList.innerHTML = "";
  snapshot.indexes.forEach((index) => {
    const item = document.createElement("div");
    item.className = "index-item";
    item.innerHTML = `
      <div>
        <div class="index-name">${escapeHtml(index.name)}</div>
        <div class="index-meta">${index.records} records</div>
      </div>
      <span class="status-chip status-${escapeHtml(index.status)}">${escapeHtml(index.status)}</span>
    `;
    indexList.append(item);
  });

  eventList.innerHTML = "";
  snapshot.events.slice(0, 24).forEach((event) => {
    const item = document.createElement("li");
    item.className = "event-item";
    item.innerHTML = `
      <div class="event-message">${escapeHtml(event.message)}</div>
      <div class="event-details">${escapeHtml(formatDetails(event.details))}</div>
      <time class="event-time">${escapeHtml(event.created_at)}</time>
    `;
    eventList.append(item);
  });

  if (!snapshot.events.length) {
    const empty = document.createElement("li");
    empty.className = "event-item";
    empty.textContent = "No events yet.";
    eventList.append(empty);
  }
}

function formatDetails(details = {}) {
  return Object.entries(details)
    .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(", ") : value}`)
    .join(" | ");
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function simulate() {
  if (!state.paused) {
    const nodes = Array.from(state.nodes.values());
    const rect = canvas.getBoundingClientRect();
    const centerX = rect.width / 2;
    const centerY = rect.height / 2;

    for (let i = 0; i < nodes.length; i += 1) {
      const a = nodes[i];
      for (let j = i + 1; j < nodes.length; j += 1) {
        const b = nodes[j];
        const dx = a.x - b.x;
        const dy = a.y - b.y;
        const distance = Math.max(Math.hypot(dx, dy), 1);
        const force = 900 / (distance * distance);
        const fx = (dx / distance) * force;
        const fy = (dy / distance) * force;
        a.vx += fx;
        a.vy += fy;
        b.vx -= fx;
        b.vy -= fy;
      }
    }

    state.edges.forEach((edge) => {
      const source = state.nodes.get(edge.source);
      const target = state.nodes.get(edge.target);
      if (!source || !target) return;
      const dx = target.x - source.x;
      const dy = target.y - source.y;
      const distance = Math.max(Math.hypot(dx, dy), 1);
      const desired = source.type === "dataset" || target.type === "dataset" ? 150 : 112;
      const force = (distance - desired) * 0.004;
      const fx = (dx / distance) * force;
      const fy = (dy / distance) * force;
      source.vx += fx;
      source.vy += fy;
      target.vx -= fx;
      target.vy -= fy;
    });

    nodes.forEach((node) => {
      if (node.id === state.draggingId) return;
      node.vx += (centerX - node.x) * 0.0009;
      node.vy += (centerY - node.y) * 0.0009;
      node.vx *= 0.88;
      node.vy *= 0.88;
      node.x = clamp(node.x + node.vx, 32, rect.width - 32);
      node.y = clamp(node.y + node.vy, 32, rect.height - 32);
    });
  }

  draw();
  state.animationFrame = window.requestAnimationFrame(simulate);
}

function draw() {
  const rect = canvas.getBoundingClientRect();
  ctx.clearRect(0, 0, rect.width, rect.height);
  ctx.lineWidth = 1;
  ctx.font = "12px Inter, system-ui, sans-serif";

  state.edges.forEach((edge) => {
    const source = state.nodes.get(edge.source);
    const target = state.nodes.get(edge.target);
    if (!source || !target) return;
    ctx.strokeStyle = "rgba(244, 240, 232, 0.16)";
    ctx.beginPath();
    ctx.moveTo(source.x, source.y);
    ctx.lineTo(target.x, target.y);
    ctx.stroke();
  });

  for (const node of state.nodes.values()) {
    const radius = Math.max(8, Math.min(node.size || 22, 56) / 2);
    const color = colors[node.type] || "#b6b0a4";
    ctx.beginPath();
    ctx.fillStyle = color;
    ctx.globalAlpha = node.id === state.selectedId ? 1 : 0.88;
    ctx.arc(node.x, node.y, radius, 0, Math.PI * 2);
    ctx.fill();
    ctx.globalAlpha = 1;

    if (node.id === state.selectedId) {
      ctx.strokeStyle = "#f1c46b";
      ctx.lineWidth = 2;
      ctx.stroke();
      ctx.lineWidth = 1;
    }

    ctx.fillStyle = "#f4f0e8";
    ctx.textAlign = "center";
    ctx.fillText(truncate(node.label, 20), node.x, node.y + radius + 16);
  }
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function truncate(value, length) {
  return value.length > length ? `${value.slice(0, length - 1)}.` : value;
}

function nearestNode(event) {
  const rect = canvas.getBoundingClientRect();
  const x = event.clientX - rect.left;
  const y = event.clientY - rect.top;
  let nearest = null;
  let best = Infinity;
  for (const node of state.nodes.values()) {
    const distance = Math.hypot(node.x - x, node.y - y);
    if (distance < best && distance < 42) {
      nearest = node;
      best = distance;
    }
  }
  return nearest;
}

function selectNode(node) {
  state.selectedId = node?.id || null;
  if (!node) {
    selectedNode.textContent = "Select a node to inspect it.";
    return;
  }
  selectedNode.textContent = `${node.label} - ${node.type} - ${node.status}`;
}

async function loadMesh(showConnection = true) {
  try {
    const snapshot = await api("/api/mesh");
    mergeGraph(snapshot);
    if (showConnection) {
      connectionLabel.textContent = "Live";
    }
  } catch (error) {
    connectionLabel.textContent = "Offline";
    console.error(error);
  }
}

function connectEvents() {
  if (!window.EventSource) {
    window.setInterval(() => loadMesh(false), 5000);
    return;
  }

  state.eventSource = new EventSource("/events");
  state.eventSource.addEventListener("open", () => {
    connectionLabel.textContent = "Live";
  });
  state.eventSource.addEventListener("snapshot", (event) => {
    mergeGraph(JSON.parse(event.data));
  });
  state.eventSource.addEventListener("mesh-event", () => {
    loadMesh(false);
  });
  state.eventSource.addEventListener("error", () => {
    connectionLabel.textContent = "Reconnecting";
  });
}

document.getElementById("refreshButton").addEventListener("click", () => loadMesh());
document.getElementById("fitButton").addEventListener("click", () => {
  state.nodes.clear();
  if (state.snapshot) mergeGraph(state.snapshot);
});
document.getElementById("pauseButton").addEventListener("click", (event) => {
  state.paused = !state.paused;
  event.currentTarget.textContent = state.paused ? "Resume" : "Pause";
});

canvas.addEventListener("pointerdown", (event) => {
  const node = nearestNode(event);
  selectNode(node);
  if (!node) return;
  state.draggingId = node.id;
  canvas.classList.add("dragging");
  canvas.setPointerCapture(event.pointerId);
});

canvas.addEventListener("pointermove", (event) => {
  if (!state.draggingId) return;
  const node = state.nodes.get(state.draggingId);
  const rect = canvas.getBoundingClientRect();
  node.x = event.clientX - rect.left;
  node.y = event.clientY - rect.top;
  node.vx = 0;
  node.vy = 0;
});

canvas.addEventListener("pointerup", (event) => {
  state.draggingId = null;
  canvas.classList.remove("dragging");
  canvas.releasePointerCapture(event.pointerId);
});

document.getElementById("ingestForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const formData = new FormData(form);
  const button = document.getElementById("ingestSubmit");
  const error = document.getElementById("ingestError");
  const data = String(formData.get("data") || "").trim();
  const tags = String(formData.get("tags") || "")
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean);
  error.textContent = "";
  setBusy(button, true, { idle: "Ingest memory", loading: "Indexing" });
  try {
    await api("/ingest", {
      method: "POST",
      body: JSON.stringify({
        data,
        dataset: String(formData.get("dataset") || "").trim() || null,
        tags,
      }),
    });
    form.querySelector("[name='data']").value = "";
    await loadMesh(false);
  } catch (err) {
    error.textContent = err.message;
  } finally {
    setBusy(button, false, { idle: "Ingest memory", loading: "Indexing" });
  }
});

document.getElementById("searchForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const formData = new FormData(form);
  const button = document.getElementById("searchSubmit");
  const error = document.getElementById("searchError");
  const results = document.getElementById("searchResults");
  error.textContent = "";
  results.innerHTML = "";
  setBusy(button, true, { idle: "Search mesh", loading: "Searching" });
  try {
    const response = await api("/search", {
      method: "POST",
      body: JSON.stringify({
        query: String(formData.get("query") || "").trim(),
        dataset: String(formData.get("dataset") || "").trim() || null,
        top_k: Number.parseInt(String(formData.get("topK") || "10"), 10) || 10,
      }),
    });
    renderSearchResults(response.results || []);
    await loadMesh(false);
  } catch (err) {
    error.textContent = err.message;
  } finally {
    setBusy(button, false, { idle: "Search mesh", loading: "Searching" });
  }
});

document.getElementById("upgradeButton").addEventListener("click", async (event) => {
  const button = event.currentTarget;
  const error = document.getElementById("upgradeError");
  error.textContent = "";
  upgradeStatus.textContent = "Running";
  upgradeStatus.className = "status-chip status-standby";
  setBusy(button, true, { idle: "Run improvement", loading: "Improving" });
  try {
    await api("/api/self-upgrade", {
      method: "POST",
      body: JSON.stringify({}),
    });
    upgradeStatus.textContent = "Complete";
    upgradeStatus.className = "status-chip status-enabled";
    await loadMesh(false);
  } catch (err) {
    error.textContent = err.message;
    upgradeStatus.textContent = "Failed";
    upgradeStatus.className = "status-chip";
  } finally {
    setBusy(button, false, { idle: "Run improvement", loading: "Improving" });
  }
});

function renderSearchResults(results) {
  const container = document.getElementById("searchResults");
  container.innerHTML = "";
  if (!results.length) {
    const empty = document.createElement("div");
    empty.className = "result-item";
    empty.textContent = "No results.";
    container.append(empty);
    return;
  }
  results.slice(0, 5).forEach((result, index) => {
    const item = document.createElement("div");
    item.className = "result-item";
    item.innerHTML = `
      <div class="result-meta">Result ${index + 1}</div>
      <div class="result-body">${escapeHtml(JSON.stringify(result, null, 2))}</div>
    `;
    container.append(item);
  });
}

window.addEventListener("resize", () => {
  resizeCanvas();
  if (state.snapshot) mergeGraph(state.snapshot);
});

resizeCanvas();
loadMesh();
connectEvents();
simulate();
