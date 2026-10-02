// triaina dashboard. Plain JS, no build step.
"use strict";

const params = new URLSearchParams(location.search);
// Optional auth token: ?token=... once, then remembered for this browser.
let token = params.get("token");
try {
  if (token) localStorage.setItem("triaina-token", token);
  else token = localStorage.getItem("triaina-token");
} catch (_) { /* storage blocked: token only lives in the URL */ }

const $ = (id) => document.getElementById(id);
const headers = () => (token ? { Authorization: `Bearer ${token}` } : {});

function toast(text) {
  const t = $("toast");
  t.textContent = text;
  t.classList.add("show");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => t.classList.remove("show"), 4000);
}

async function api(method, path, body) {
  const opts = { method, headers: headers() };
  if (body instanceof FormData) opts.body = body;
  else if (body !== undefined) {
    opts.body = JSON.stringify(body);
    opts.headers["Content-Type"] = "application/json";
  }
  const res = await fetch(path, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `${res.status} ${res.statusText}`);
  return data;
}

const fmtTemp = (h) => (h && h.temperature !== undefined
  ? `${h.temperature.toFixed(1)} / ${Math.round(h.target || 0)} C` : "-");

function renderStatus(s) {
  $("conn").textContent = s.online ? "online" : "offline";
  $("conn").className = `pill ${s.online ? "on" : "off"}`;
  $("klippy").textContent = s.online ? s.klippy : "-";
  $("state").textContent = s.online ? s.state : "-";
  $("mode").textContent = s.mode ?? (s.online ? "macros not installed" : "-");
  $("blade").textContent = s.blade_down == null ? "-" : (s.blade_down ? "down" : "up");
  $("nozzle").textContent = fmtTemp(s.extruder);
  $("bed").textContent = fmtTemp(s.heater_bed);
  $("homed").textContent = s.homed_axes || "-";
  $("file").textContent = s.filename || "-";
  const pct = Math.round((s.progress || 0) * 100);
  $("bar").style.width = `${pct}%`;
  $("message").textContent = s.online ? (s.message || (s.state === "printing" ? `${pct}%` : ""))
    : `Printer unreachable: ${s.error || ""}`;
  const busy = ["printing", "paused"].includes(s.state);
  document.querySelectorAll("[data-mode]").forEach((b) => { b.disabled = !s.online || busy; });
  document.querySelector('[data-action="pause"]').disabled = s.state !== "printing";
  document.querySelector('[data-action="resume"]').disabled = s.state !== "paused";
  document.querySelector('[data-action="cancel"]').disabled = !busy;
}

function renderJobs(jobs) {
  const tbody = $("jobs");
  tbody.replaceChildren();
  for (const j of jobs) {
    const tr = document.createElement("tr");
    const cells = [j.id, j.name, j.kind_label];
    for (const c of cells) {
      const td = document.createElement("td");
      td.textContent = c;
      if (c === j.name) td.className = "name";
      tr.append(td);
    }
    const st = document.createElement("td");
    st.textContent = j.state + (j.error ? `: ${j.error}` : "");
    st.className = `state-${j.state}`;
    tr.append(st);
    const act = document.createElement("td");
    if (j.state === "ready") {
      const go = document.createElement("button");
      go.textContent = "Start";
      go.className = "primary";
      go.onclick = () => confirmStart(j);
      const drop = document.createElement("button");
      drop.textContent = "Discard";
      drop.onclick = () => api("DELETE", `api/jobs/${j.id}`).catch((e) => toast(e.message));
      act.append(go, " ", drop);
    }
    if (j.has_output) {
      const a = document.createElement("a");
      a.href = `api/jobs/${j.id}/output${token ? `?token=${encodeURIComponent(token)}` : ""}`;
      a.textContent = "G-code";
      act.append(" ", a);
    }
    tr.append(act);
    tbody.append(tr);
  }
}

function confirmStart(job) {
  const dlg = $("confirm");
  $("confirmName").textContent = `#${job.id} ${job.name}`;
  $("confirmText").textContent = job.confirm_text;
  $("confirmBox").checked = false;
  $("confirmOk").disabled = true;
  dlg.onclose = async () => {
    if (dlg.returnValue !== "ok") return;
    try {
      await api("POST", `api/jobs/${job.id}/start`, { confirm: true });
      toast(`Started #${job.id}`);
    } catch (e) { toast(e.message); }
  };
  dlg.showModal();
}
$("confirmBox").onchange = (e) => { $("confirmOk").disabled = !e.target.checked; };

document.querySelectorAll("[data-mode]").forEach((b) => {
  b.onclick = () => api("POST", `api/mode/${b.dataset.mode}`)
    .then(() => toast(`${b.textContent} sent`)).catch((e) => toast(e.message));
});
document.querySelectorAll("[data-action]").forEach((b) => {
  b.onclick = () => api("POST", `api/print/${b.dataset.action}`).catch((e) => toast(e.message));
});
$("estop").onclick = () => {
  if (confirm("Emergency stop halts Klipper immediately. A firmware restart is needed after.")) {
    api("POST", "api/estop").then(() => toast("Emergency stop sent")).catch((e) => toast(e.message));
  }
};

const drop = $("drop");
const input = $("fileinput");
input.onchange = () => { $("dropText").textContent = input.files[0]?.name || "Drop a G-code file"; };
drop.ondragover = (e) => { e.preventDefault(); drop.classList.add("over"); };
drop.ondragleave = () => drop.classList.remove("over");
drop.ondrop = (e) => {
  e.preventDefault();
  drop.classList.remove("over");
  input.files = e.dataTransfer.files;
  input.onchange();
};
$("upload").onsubmit = async (e) => {
  e.preventDefault();
  try {
    const job = await api("POST", "api/jobs", new FormData(e.target));
    toast(job.state === "failed" ? `Failed: ${job.error}` : `Job #${job.id} ready`);
    e.target.reset();
    $("dropText").textContent = "Drop a G-code file or click to choose";
  } catch (err) { toast(err.message); }
};

// Fallback when the websocket is down (proxy, old browser): poll the REST API.
let pollTimer = null;
function poll() {
  Promise.all([api("GET", "api/status"), api("GET", "api/jobs")])
    .then(([s, jobs]) => { renderStatus(s); renderJobs(jobs); })
    .catch(() => {});
}

function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const base = location.pathname.replace(/[^/]*$/, "");
  const ws = new WebSocket(`${proto}://${location.host}${base}ws${token ? `?token=${encodeURIComponent(token)}` : ""}`);
  ws.onopen = () => { clearInterval(pollTimer); pollTimer = null; };
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    renderStatus(msg.status);
    renderJobs(msg.jobs);
  };
  ws.onclose = () => {
    if (!pollTimer) { poll(); pollTimer = setInterval(poll, 2000); }
    setTimeout(connect, 5000);
  };
}

api("GET", "api/info").then((info) => {
  $("fluidd").href = info.printer_web_url;
  const kind = $("kind");
  for (const [value, label] of Object.entries(info.kinds)) kind.append(new Option(label, value));
  if (info.camera_url) {
    $("camera").src = info.camera_url;
    $("camera-card").hidden = false;
  }
  connect();
}).catch((e) => toast(`Cannot load: ${e.message}`));
