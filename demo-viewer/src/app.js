const $ = id => document.getElementById(id);
const stageIds = ["routine", "agent", "validation", "queue", "job", "report"];
const cards = [...document.querySelectorAll(".stage")];
const modes = {
  replay: { label: "RECORDED AZURE EVIDENCE", description: "Saved September 30, 2026. Loading does not start a new Azure execution.", action: "Load recording" },
  local: { label: "LOCAL PYTHON EXECUTION", description: "Real checks with SQLite and local files. Routine and agent selection are simulated.", action: "Run locally" },
  azure: { label: "AZURE LIVE", description: "Server reads Azure evidence. Dispatch starts new work; Check only inspects an existing request.", action: "Dispatch to Azure" },
};
const labels = { waiting: "Not observed", running: "Observing", completed: "Observed", recorded: "Recorded", inferred: "Inferred", simulated: "Local simulation", unverified: "Unverified", failed: "Failed" };
const actionNames = { check_links: "Check broken internal links", check_translation_drift: "Check source baseline drift" };
let mode = "replay", current = null, selected = 0, timer, generation = 0, busy = false, health = null;
const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({ 38: "&amp;", 60: "&lt;", 62: "&gt;", 34: "&quot;", 39: "&#39;" })[c.charCodeAt(0)]);
const stamp = value => value ? new Date(value).toISOString().slice(0, 19).replace("T", " ") + " UTC" : "Not recorded";
const evidenceLabel = evidence => evidence?.label === "Azure evidence read now" ? "Azure Blob evidence" : evidence?.label;
const save = value => { try { if (value) localStorage.setItem("docops-observation", value); else localStorage.removeItem("docops-observation"); } catch {} };
async function api(path, options = {}) {
  const response = await fetch(path, { ...options, signal: AbortSignal.timeout(20000), headers: { "Content-Type": "application/json" }, cache: "no-store" });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}
function setBusy(value) {
  busy = value;
  $("run-button").disabled = value || (mode === "azure" && !health?.modes.azure.available);
  $("run-button").textContent = value ? "Observing…" : modes[mode].action;
  $("lookup-button").disabled = value || !health?.modes.azure.available;
  document.querySelectorAll("[data-mode]").forEach(button => button.disabled = value);
  $("recent-runs").disabled = value;
}
function showError(title, message, recovery, retry = false) {
  $("error-panel").hidden = false;
  $("error-title").textContent = title; $("error-message").textContent = message;
  $("error-recovery").textContent = recovery; $("retry-observation").hidden = !retry;
}
function changeMode(nextMode, clear = true) {
  mode = nextMode;
  document.querySelectorAll("[data-mode]").forEach(button => button.setAttribute("aria-pressed", String(button.dataset.mode === mode)));
  $("mode-label").textContent = modes[mode].label; $("mode-description").textContent = modes[mode].description;
  $("lookup-form").hidden = mode !== "azure";
  if (clear) { generation++; clearTimeout(timer); current = null; selected = 0; save(null); $("error-panel").hidden = true; render(); }
  setBusy(false);
  if (mode === "azure" && health && !health.modes.azure.available) showError("Azure observer unavailable", health.modes.azure.reason, "Start the viewer with start.ps1, then reload. No new work has been dispatched.");
}
function render() {
  const run = current, evidence = run?.evidence || {};
  const statusText = run?.status === "completed" ? (mode === "replay" ? "Recording loaded" : "Report verified") : run?.status === "observation_error" ? "Observation unavailable" : run?.status === "failed" ? "Local / recording error" : run ? "Observing evidence" : "Ready";
  $("run-state").textContent = statusText; $("run-state").dataset.status = run?.status || "ready";
  $("request-id").textContent = run?.request_id || "No request loaded";
  $("request-context").textContent = !run ? "Inspect one request from start to result." : mode === "replay" ? "Saved Azure execution · September 30, 2026" : mode === "local" ? "This machine · Python + SQLite + retained files" : run.monitor_only ? "Existing Azure request · read-only inspection" : "New Azure dispatch · server-side credentials";
  if (run?.monitor_only && mode === "azure") { $("mode-label").textContent = "AZURE · EXISTING REQUEST"; $("mode-description").textContent = run.status === "completed" ? `Evidence read ${stamp(evidence.observed_at || run.finished_at)} · Check again to refresh.` : "Existing request inspection. No new work is dispatched by this lookup."; }
  else { $("mode-label").textContent = modes[mode].label; $("mode-description").textContent = modes[mode].description; }
  const seconds = run ? Math.max(0, (new Date(run.finished_at || Date.now()) - new Date(run.started_at)) / 1000) : 0;
  $("duration").textContent = !run || mode === "replay" ? "" : `${run.status === "running" ? "Observing" : "Observed in"} ${seconds.toFixed(1)}s`;
  cards.forEach((card, index) => {
    const stage = run?.stages[index]; card.dataset.status = stage?.status || "waiting";
    card.setAttribute("aria-pressed", String(index === selected)); card.querySelector("[data-status]").textContent = mode === "local" && stage?.status === "completed" ? "Observed locally" : labels[stage?.status] || "Not observed";
  });
  $("decisions").innerHTML = run?.actions.length ? run.actions.map(action => `<div class="decision">${esc(actionNames[action] || action)}</div>`).join("") : `<p class="muted">Actions appear when evidence is available.</p>`;
  $("decision-note").textContent = !run?.actions.length ? "" : mode === "local" ? "Scripted selection from samples/request.json." : "Selection recovered from stored evidence.";
  $("finding-count").hidden = !run?.report; $("finding-count").textContent = `${run?.report?.finding_count ?? 0} findings`;
  $("result").innerHTML = run?.report ? findings(run.report) : `<p class="muted">${run?.status === "observation_error" ? "The viewer could not confirm the outcome. This does not mean the Azure Job failed." : "Completion requires a stored report for this request."}</p>`;
  $("receipt").innerHTML = `<dt>Source</dt><dd>${esc(evidenceLabel(evidence) || "Not loaded")}</dd><dt>Worker</dt><dd>${esc(evidence.job_execution || "Not observed")}</dd><dt>Report</dt><dd>${esc(evidence.blob_path ? (mode === "replay" ? "Saved Azure report.json" : "Azure Blob · report.json") : evidence.report_path ? "Retained locally · report.json" : "Not observed")}</dd>`;
  ["open-report", "raw-json"].forEach(id => $(id).disabled = !run?.report);
  const source = run?.azure_source, azureLink = $("open-azure");
  let portalUrl = null;
  try {
    const candidate = new URL(source?.url);
    if (mode === "azure" && run?.status === "completed" && candidate.origin === "https://portal.azure.com"
        && !candidate.username && !candidate.password && !candidate.search
        && candidate.hash.startsWith("#view/Microsoft_Azure_Storage/ContainerMenuBlade/")) portalUrl = candidate.href;
  } catch {}
  azureLink.removeAttribute("href");
  if (portalUrl) azureLink.href = portalUrl;
  azureLink.setAttribute("aria-disabled", String(!portalUrl));
  azureLink.tabIndex = portalUrl ? 0 : -1;
  $("azure-source-note").textContent = source?.note || (mode === "local" ? "Local files only · no Azure resource." : mode === "replay" ? "This recording has no live Azure account reference." : "Available after an Azure report is verified.");
  $("azure-report-path").hidden = !portalUrl;
  $("azure-report-path").textContent = portalUrl ? source.report_path : "";
  $("show-receipt").disabled = !run; $("show-events").disabled = !run?.events.length;
  if (run?.error) {
    showError(run.status === "observation_error" ? "Observer error · worker outcome unknown" : "Execution / recording error", run.error, run.recovery, mode === "azure");
    if (mode === "azure") $("lookup-id").value = run.request_id;
  }
  renderInspector(); requestAnimationFrame(drawConnectors);
}
function findings(report) {
  const entries = Object.values(report.findings || {}).flat();
  if (!entries.length) return `<p class="muted">Both checks completed. No issues found.</p>`;
  return entries.map(item => `<div class="finding"><strong>${esc(item.kind === "broken_internal_link" ? "Broken internal link" : item.kind === "source_changed" ? "Source baseline changed" : item.kind)}</strong><p class="file">${esc(item.file)}${item.line ? `:${esc(item.line)}` : ""}</p><p>${esc(item.target ? `Missing target: ${item.target}` : `Compare with ${item.source}`)}</p></div>`).join("");
}
function renderInspector() {
  const stage = current?.stages[selected];
  $("inspector-title").textContent = stage?.name || cards[selected].querySelector(".stage-name").textContent;
  $("stage-detail").textContent = stage?.detail || "Select a mode and load evidence. Click any stage to explain it at your own pace.";
  $("stage-source").textContent = `Source: ${stage?.source || "none yet"}`;
  $("stage-time").textContent = stage?.updated_at ? `Evidence time: ${stamp(stage.updated_at)}` : "";
  const events = current?.events.filter(entry => entry.stage === stageIds[selected]) || [];
  $("event-preview").textContent = events.length ? `${events.length} stage event${events.length > 1 ? "s" : ""} · ${events.at(-1).message}` : "Events stay available after execution completes.";
  $("previous").disabled = selected === 0; $("next").disabled = selected === 5;
}
function selectStage(index) { selected = index; cards.forEach((card, i) => card.setAttribute("aria-pressed", String(i === index))); renderInspector(); }
function drawConnectors() {
  const root = $("flow").getBoundingClientRect();
  const rectangles = cards.map(card => card.getBoundingClientRect());
  const points = rectangles.slice(0, -1).map((a, i) => {
    const b = rectangles[i + 1];
    if (Math.abs(a.top - b.top) < 5) {
      const right = b.left > a.left; const start = (right ? a.right + 6 : a.left - 6) - root.left; const end = (right ? b.left - 8 : b.right + 8) - root.left;
      return `M ${start} ${a.top + a.height / 2 - root.top} L ${end} ${b.top + b.height / 2 - root.top}`;
    }
    return `M ${a.left + a.width / 2 - root.left} ${a.bottom + 6 - root.top} L ${b.left + b.width / 2 - root.left} ${b.top - 8 - root.top}`;
  });
  $("paths").innerHTML = points.map(d => `<path d="${d}" marker-end="url(#arrow)"/>`).join("");
}
function openDialog(title, html) { $("dialog-title").textContent = title; $("dialog-body").innerHTML = html; $("dialog").showModal(); }
function details() {
  const e = { ...current.evidence, label: evidenceLabel(current.evidence) };
  const values = { "Request ID": current.request_id, "Mode": modes[current.mode].label, "Observation started": stamp(current.started_at), "Observation finished": current.finished_at ? stamp(current.finished_at) : "Still observing", "Read-only lookup": current.monitor_only ? "Yes · no dispatch" : "No", ...e };
  openDialog("Evidence receipt", `<p class="intro">These identifiers describe this observation. An unavailable execution ID is not inferred from timing. A hash identifies the report bytes; it does not independently prove where they ran.</p><dl>${Object.entries(values).map(([key,value]) => `<dt>${esc(key.replaceAll("_", " "))}</dt><dd class="mono">${esc(typeof value === "object" ? JSON.stringify(value, null, 2) : value ?? "Not returned")}</dd>`).join("")}</dl>`);
}
async function refreshHistory() {
  try { const data = await api("/api/runs"); $("recent-runs").innerHTML = `<option value="">Choose a previous observation</option>` + data.runs.map(run => `<option value="${esc(run.id)}">${esc(run.mode)} · ${esc(run.request_id)} · ${esc(run.status)}</option>`).join(""); if (current) $("recent-runs").value = current.id; } catch {}
}
async function poll(id, token) {
  try {
    const data = await api(`/api/runs/${id}`); if (token !== generation) return;
    current = data; $("error-panel").hidden = true; render();
    if (data.status === "running") timer = setTimeout(() => poll(id, token), 1200);
    else { setBusy(false); refreshHistory(); }
  } catch (error) {
    if (token !== generation) return; setBusy(false);
    showError("Viewer connection interrupted", error.message, "Previously read evidence is retained. Retry to resume this same observation; no new work will be dispatched.", true);
  }
}
async function start(monitorOnly = false) {
  if (busy) return; generation++; const token = generation; clearTimeout(timer); current = null; selected = 0; $("error-panel").hidden = true; render(); setBusy(true);
  const payload = { mode, monitor_only: monitorOnly }; if (monitorOnly) payload.request_id = $("lookup-id").value.trim();
  try {
    const data = await api("/api/runs", { method: "POST", body: JSON.stringify(payload) });
    if (token !== generation) return; current = data; save(data.id); render();
    if (data.status === "running") poll(data.id, token); else { setBusy(false); refreshHistory(); }
  } catch (error) {
    setBusy(false); showError("Could not start observation", error.message, "If a dispatch response was lost, reload saved observations before starting again."); refreshHistory();
  }
}
async function restore(id) {
  const token = ++generation; clearTimeout(timer); setBusy(true);
  try {
    const data = await api(`/api/runs/${id}`); if (token !== generation) return;
    changeMode(data.mode, false); current = data; selected = 0; $("error-panel").hidden = true; save(id); render(); $("recent-runs").value = data.id;
    if (data.status === "running") { setBusy(true); poll(id, token); }
  } catch (error) { setBusy(false); save(null); showError("Saved observation unavailable", error.message, "Choose a saved observation or load recorded Azure evidence."); }
}
document.querySelectorAll("[data-mode]").forEach(button => button.addEventListener("click", () => changeMode(button.dataset.mode)));
cards.forEach((card, index) => card.addEventListener("click", () => selectStage(index)));
$("previous").addEventListener("click", () => selectStage(Math.max(0, selected - 1)));
$("next").addEventListener("click", () => selectStage(Math.min(5, selected + 1)));
$("run-button").addEventListener("click", () => start(false));
$("lookup-form").addEventListener("submit", event => { event.preventDefault(); start(true); });
$("recent-runs").addEventListener("change", event => { if (event.target.value) restore(event.target.value); });
$("retry-observation").addEventListener("click", () => {
  if (!current) return;
  $("error-panel").hidden = true;
  if (current.status === "observation_error" && mode === "azure") { $("lookup-id").value = current.request_id; start(true); }
  else { const token = ++generation; setBusy(true); poll(current.id, token); }
});
$("show-receipt").addEventListener("click", details);
$("open-report").addEventListener("click", () => openDialog("Committed report", `<p class="intro">Request <strong class="mono">${esc(current.request_id)}</strong><br>Repository: ${esc(current.report.repository_id)} · ${esc(current.report.finding_count)} findings<br>Source: ${esc(evidenceLabel(current.evidence))}</p>${findings(current.report)}`));
$("raw-json").addEventListener("click", () => openDialog("Report · raw JSON", `<pre>${esc(JSON.stringify(current.report, null, 2))}</pre>`));
$("show-events").addEventListener("click", () => openDialog("Evidence events", `<p class="intro">Observer events describe what the viewer read. Entries explicitly marked Recorded Azure console log are saved worker logs. Inferred entries are interpretations, not direct service events. All timestamps are UTC.</p>${current.events.map(entry => `<article class="event-row"><div class="event-meta"><span>${esc(stamp(entry.timestamp))}</span><span>${esc(entry.stage)} · ${esc(entry.kind)}</span></div><p>${esc(entry.message)}</p><div class="event-meta">Source: ${esc(entry.source)} · Read by viewer: ${esc(stamp(entry.observed_at))}</div></article>`).join("")}`));
$("close-dialog").addEventListener("click", () => $("dialog").close());
$("dialog").addEventListener("click", event => { if (event.target === $("dialog") && event.clientX < $("dialog").getBoundingClientRect().left) $("dialog").close(); });
new ResizeObserver(drawConnectors).observe($("flow"));
async function init() {
  render(); setBusy(true);
  try { health = await api("/api/health"); } catch (error) { showError("Viewer server unavailable", error.message, "Start with start.ps1 and reload this page."); }
  setBusy(false); await refreshHistory();
  let previous; try { previous = localStorage.getItem("docops-observation"); } catch {}
  if (previous && /^[a-f0-9]{32}$/.test(previous)) await restore(previous);
}
init();
