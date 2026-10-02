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
  const klipperDown = s.online && s.klippy && s.klippy !== "ready";
  $("message").textContent = klipperDown ? `Klipper ${s.klippy}: ${s.klippy_message || ""}`
    : s.online ? (s.message || (s.state === "printing" ? `${pct}%` : ""))
    : `Printer unreachable: ${s.error || ""}`;
  const busy = ["printing", "paused"].includes(s.state);
  // Shown only when Klipper is not ready: after an emergency stop or an error.
  $("restart").hidden = !s.online || !s.klippy || s.klippy === "ready";
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
    const fmtTime = (s) => (s >= 60 ? `${Math.round(s / 60)} min` : `${s} s`);
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
    const det = document.createElement("td");
    if (j.summary) {
      const s = j.summary;
      // Design jobs have all fields; cut G-code jobs only size and warnings.
      const parts = [];
      if (s.width_mm != null) parts.push(`${s.width_mm} x ${s.height_mm} mm`);
      if (s.paths != null) parts.push(`${s.paths} paths`);
      if (s.estimate_s != null) parts.push(`~${fmtTime(s.estimate_s)}`);
      det.append(parts.join(", "));
      for (const w of s.warnings || []) {
        const p = document.createElement("div");
        p.className = "warn";
        p.textContent = w;
        det.append(p);
      }
    }
    tr.append(det);
    const act = document.createElement("td");
    if (j.state === "ready") {
      const go = document.createElement("button");
      go.textContent = "Start";
      go.className = "primary";
      go.onclick = () => confirmStart(j);
      act.append(go, " ");
    }
    if (!["converting", "sending", "running"].includes(j.state) && j.has_output) {
      const drop = document.createElement("button");
      drop.textContent = j.state === "ready" ? "Discard" : "Delete files";
      drop.onclick = () => api("DELETE", `api/jobs/${j.id}`).catch((e) => toast(e.message));
      act.append(drop);
    }
    if (j.summary && j.has_output && j.state !== "failed") {
      const pv = document.createElement("a");
      pv.href = `api/jobs/${j.id}/preview.svg${token ? `?token=${encodeURIComponent(token)}` : ""}`;
      pv.target = "_blank";
      pv.textContent = "Preview";
      act.append(" ", pv);
    }
    if (j.has_output && j.state !== "converting") {
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
$("restart").onclick = () => {
  api("POST", "api/firmware-restart").then(() => toast("Firmware restart sent")).catch((e) => toast(e.message));
};
$("estop").onclick = () => {
  if (confirm("Emergency stop halts Klipper immediately. A firmware restart is needed after.")) {
    api("POST", "api/estop").then(() => toast("Emergency stop sent")).catch((e) => toast(e.message));
  }
};

const drop = $("drop");
const input = $("fileinput");
const HELP = {
  "cut-design": "SVG, DXF, PDF, AI, EPS, PNG or JPG. Converted here with blade-offset compensation; check the preview before starting.",
  "cut-gcode": "G-code from Kiri:Moto, Inkcut, Inkscape or LightBurn, made safe by the preprocessor: heaters off, knife macros, feed cap.",
  "print-gcode": "Sliced G-code for a normal print, sent unchanged. Remove the knife holder first.",
};
const ACCEPT = {
  "cut-design": ".svg,.dxf,.pdf,.ai,.eps,.png,.jpg,.jpeg",
  "cut-gcode": ".gcode,.gco,.g,.nc,.ngc,.txt",
  "print-gcode": ".gcode,.gco,.g",
};
function kindChanged() {
  const k = $("kind").value;
  $("designOpts").hidden = k !== "cut-design";
  $("kindHelp").textContent = HELP[k] || "";
  input.accept = ACCEPT[k] || "";
  const name = input.files[0]?.name || "";
  const isImage = /\.(png|jpe?g)$/i.test(name);
  $("rasterOpts").hidden = !isImage;
  document.querySelector('[name="width"]').placeholder = isImage ? "required" : "file size";
}
input.onchange = () => {
  $("dropText").textContent = input.files[0]?.name || "Drop a file or click to choose";
  kindChanged();
};
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
    const form = new FormData(e.target);
    // Blank fields mean "use the configured default": send nothing for them.
    for (const [k, v] of [...form.entries()]) if (v === "") form.delete(k);
    const job = await api("POST", "api/jobs", form);
    const what = { failed: `Failed: ${job.error}`, converting: `Job #${job.id} converting...` };
    toast(what[job.state] || `Job #${job.id} ready`);
    const kind = $("kind").value;
    e.target.reset();
    $("kind").value = kind;
    $("dropText").textContent = "Drop a file or click to choose";
    kindChanged();
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
  kind.value = "cut-design";
  kind.onchange = kindChanged;
  kindChanged();
  if (info.camera_url) {
    $("camera").src = info.camera_url;
    $("camera-card").hidden = false;
  }
  connect();
}).catch((e) => toast(`Cannot load: ${e.message}`));
