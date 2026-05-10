let isRecording = false;
let timerInterval = null;
let elapsedSeconds = 0;
let activeMeetingId = null;

// ── Boot ──────────────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  loadConfig();
  loadMeetings();
  loadDevices();
  setInterval(syncStatus, 3000);
});

// ── Config & provider ─────────────────────────────────────────────────────────

async function loadConfig() {
  try {
    const cfg = await api("/api/config");
    const bar = document.getElementById("providerBar");
    const label = document.getElementById("providerLabel");

    const providerNames = { anthropic: "Anthropic", ollama: "Ollama", openrouter: "OpenRouter" };
    label.textContent = `${providerNames[cfg.provider] || cfg.provider} · ${cfg.model}`;
    bar.classList.add("ready");

    // Populate settings modal
    document.getElementById("settingProvider").textContent = providerNames[cfg.provider] || cfg.provider;
    document.getElementById("settingModel").textContent = cfg.model;
    document.getElementById("settingWhisper").textContent = cfg.whisper_model;
  } catch (e) {
    const bar = document.getElementById("providerBar");
    bar.classList.add("error");
    document.getElementById("providerLabel").textContent = "provider error";
  }
}

async function testProvider() {
  const btn = document.getElementById("btnTest");
  const result = document.getElementById("testResult");
  btn.disabled = true;
  btn.textContent = "Testing...";
  result.style.display = "none";

  try {
    const data = await api("/api/provider/test", "POST");
    result.className = "test-result ok";
    result.textContent = `✓ Connected to ${data.provider} · ${data.model}`;
  } catch (e) {
    result.className = "test-result err";
    result.textContent = `✗ ${e.message}`;
  } finally {
    result.style.display = "block";
    btn.disabled = false;
    btn.textContent = "Test";
  }
}

// ── Devices ───────────────────────────────────────────────────────────────────

async function loadDevices() {
  try {
    const devices = await api("/api/devices");
    const sel = document.getElementById("deviceSelect");
    sel.innerHTML = `<option value="">Default microphone</option>`;
    for (const d of devices) {
      const opt = document.createElement("option");
      opt.value = d.name;
      opt.textContent = d.is_blackhole ? `${d.name} (system audio)` : d.name;
      opt.selected = d.active;
      sel.appendChild(opt);
    }
  } catch (_) {}
}

async function setDevice(name) {
  try {
    await api("/api/config/device", "POST", { device: name || null });
    const bar = document.getElementById("providerBar");
    const label = document.getElementById("providerLabel");
    const cfg = await api("/api/config");
    const providerNames = { anthropic: "Anthropic", ollama: "Ollama", openrouter: "OpenRouter" };
    label.textContent = `${providerNames[cfg.provider] || cfg.provider} · ${cfg.model}`;
  } catch (e) {
    alert(`Could not set device: ${e.message}`);
  }
}

// ── Settings modal ────────────────────────────────────────────────────────────

function openSettings() {
  document.getElementById("settingsOverlay").style.display = "block";
  document.getElementById("settingsModal").style.display = "block";
  document.getElementById("testResult").style.display = "none";
  loadDevices();
}

function closeSettings() {
  document.getElementById("settingsOverlay").style.display = "none";
  document.getElementById("settingsModal").style.display = "none";
}

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeSettings();
});

// ── Meetings ──────────────────────────────────────────────────────────────────

async function loadMeetings() {
  try {
    const meetings = await api("/api/meetings");
    renderMeetingList(meetings);
  } catch (e) {
    console.error("Failed to load meetings", e);
  }
}

function renderMeetingList(meetings) {
  const list = document.getElementById("meetingList");
  if (!meetings.length) {
    list.innerHTML = `<div class="empty-list">No meetings yet.<br>Start one above.</div>`;
    return;
  }
  list.innerHTML = meetings.map(m => `
    <div class="meeting-item${m.id === activeMeetingId ? " active" : ""}"
         onclick="openMeeting(${m.id})">
      <div class="meeting-item-title">${esc(m.title)}</div>
      <div class="meeting-item-meta">${m.date} · ${fmtDuration(m.duration)}</div>
    </div>
  `).join("");
}

async function openMeeting(id) {
  try {
    const m = await api(`/api/meetings/${id}`);
    activeMeetingId = id;
    renderMeeting(m);
    loadMeetings();
  } catch (_) {
    alert("Could not load meeting.");
  }
}

function renderMeeting(m) {
  document.getElementById("emptyState").style.display = "none";
  const view = document.getElementById("meetingView");
  view.style.display = "block";

  document.getElementById("meetingTitle").textContent = m.title;
  document.getElementById("meetingDate").textContent = m.date;
  document.getElementById("meetingDuration").textContent = fmtDuration(m.duration);

  const body = document.getElementById("notesBody");
  body.innerHTML = marked.parse(m.notes || "");
  body.querySelectorAll('input[type="checkbox"]').forEach(cb => { cb.disabled = true; });

  document.getElementById("transcriptText").textContent = m.transcript || "No transcript available.";
  document.getElementById("transcriptPanel").style.display = "none";
  document.getElementById("btnTranscript").textContent = "Show transcript";
}

// ── Recording ─────────────────────────────────────────────────────────────────

async function toggleRecord() {
  if (isRecording) await stopRecording();
  else await startRecording();
}

async function startRecording() {
  try {
    const res = await api("/api/record/start", "POST");
    isRecording = true;
    startTimer(0);
    showRecordingUI();
  } catch (e) {
    alert(`Could not start recording: ${e.message}`);
  }
}

async function stopRecording() {
  const btn = document.getElementById("btnRecord");
  btn.disabled = true;
  stopTimer();
  isRecording = false;

  document.getElementById("timer").style.display = "none";
  document.getElementById("notesInputPanel").style.display = "none";
  document.getElementById("processing").style.display = "flex";
  btn.classList.remove("recording");
  document.getElementById("btnLabel").textContent = "Start Meeting";

  const roughNotes = document.getElementById("roughNotes").value;

  try {
    const result = await api("/api/record/stop", "POST", { user_notes: roughNotes });
    document.getElementById("processing").style.display = "none";
    document.getElementById("roughNotes").value = "";
    btn.disabled = false;
    await loadMeetings();
    if (result.id) openMeeting(result.id);
  } catch (e) {
    document.getElementById("processing").style.display = "none";
    btn.disabled = false;
    alert(`Error processing recording: ${e.message}`);
  }
}

function showRecordingUI() {
  const btn = document.getElementById("btnRecord");
  btn.classList.add("recording");
  document.getElementById("btnLabel").textContent = "Stop & Summarize";
  document.getElementById("timer").style.display = "block";
  document.getElementById("notesInputPanel").style.display = "flex";
}

async function syncStatus() {
  try {
    const data = await api("/api/record/status");
    if (data.recording && !isRecording) {
      isRecording = true;
      startTimer(data.elapsed);
      showRecordingUI();
    }
  } catch (_) {}
}

// ── Timer ─────────────────────────────────────────────────────────────────────

function startTimer(initial = 0) {
  elapsedSeconds = Math.floor(initial);
  updateTimer();
  timerInterval = setInterval(() => { elapsedSeconds++; updateTimer(); }, 1000);
}

function stopTimer() {
  clearInterval(timerInterval);
  timerInterval = null;
}

function updateTimer() {
  const m = String(Math.floor(elapsedSeconds / 60)).padStart(2, "0");
  const s = String(elapsedSeconds % 60).padStart(2, "0");
  document.getElementById("timer").textContent = `${m}:${s}`;
}

// ── Transcript toggle ─────────────────────────────────────────────────────────

function toggleTranscript() {
  const panel = document.getElementById("transcriptPanel");
  const btn = document.getElementById("btnTranscript");
  const show = panel.style.display === "none";
  panel.style.display = show ? "block" : "none";
  btn.textContent = show ? "Hide transcript" : "Show transcript";
}

// ── Delete ────────────────────────────────────────────────────────────────────

async function deleteActiveMeeting() {
  if (!activeMeetingId) return;
  if (!confirm("Delete this meeting? This cannot be undone.")) return;
  try {
    await api(`/api/meetings/${activeMeetingId}`, "DELETE");
    activeMeetingId = null;
    document.getElementById("meetingView").style.display = "none";
    document.getElementById("emptyState").style.display = "flex";
    await loadMeetings();
  } catch (_) {
    alert("Could not delete meeting.");
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────────

async function api(url, method = "GET", body = null) {
  const res = await fetch(url, {
    method,
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

function esc(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function fmtDuration(sec) {
  if (!sec) return "";
  const m = Math.floor(sec / 60), s = Math.floor(sec % 60);
  if (m === 0) return `${s}s`;
  if (s === 0) return `${m}m`;
  return `${m}m ${s}s`;
}
