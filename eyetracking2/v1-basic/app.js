const CALIBRATION_POINTS = [
  { id: "p1", x: 15, y: 15 },
  { id: "p2", x: 50, y: 15 },
  { id: "p3", x: 85, y: 15 },
  { id: "p4", x: 15, y: 50 },
  { id: "p5", x: 50, y: 50 },
  { id: "p6", x: 85, y: 50 },
  { id: "p7", x: 15, y: 85 },
  { id: "p8", x: 50, y: 85 },
  { id: "p9", x: 85, y: 85 },
];

const ZONES = [
  { id: 0, label: "Yuqori chap", rect: [0, 0, 0.5, 0.5] },
  { id: 1, label: "Yuqori o'ng", rect: [0.5, 0, 1, 0.5] },
  { id: 2, label: "Pastki chap", rect: [0, 0.5, 0.5, 1] },
  { id: 3, label: "Pastki o'ng", rect: [0.5, 0.5, 1, 1] },
  { id: 4, label: "Markaz", rect: [0.33, 0.33, 0.67, 0.67] },
];

const POINT_REPETITIONS = 3;
const DWELL_MS = 1800;
const FIRE_COOLDOWN_MS = 3500;

const els = {
  stage: document.querySelector("#stage"),
  gazeDot: document.querySelector("#gaze-dot"),
  banner: document.querySelector("#banner"),
  statusChip: document.querySelector("#status-chip"),
  calibrationOverlay: document.querySelector("#calibration-overlay"),
  calibrationPoints: document.querySelector("#calibration-points"),
  calibrationProgress: document.querySelector("#calibration-progress"),
  btnStart: document.querySelector("#btn-start"),
  btnPause: document.querySelector("#btn-pause"),
  btnCalibrate: document.querySelector("#btn-calibrate"),
  btnReset: document.querySelector("#btn-reset"),
  btnPreview: document.querySelector("#btn-preview"),
  metricState: document.querySelector("#metric-state"),
  metricGaze: document.querySelector("#metric-gaze"),
  metricZone: document.querySelector("#metric-zone"),
  metricDwell: document.querySelector("#metric-dwell"),
  metricSamples: document.querySelector("#metric-samples"),
  metricCalibrated: document.querySelector("#metric-calibrated"),
  eventLog: document.querySelector("#event-log"),
  zoneCards: [...document.querySelectorAll("[data-zone-tile]")],
  zoneStage: [...document.querySelectorAll("[data-zone]")],
};

const state = {
  started: false,
  paused: false,
  calibrating: false,
  previewVisible: false,
  calibrated: false,
  samples: 0,
  gaze: null,
  activeZone: -1,
  zoneStartedAt: 0,
  lastFiredAt: new Map(),
  calibrationHits: new Map(CALIBRATION_POINTS.map((point) => [point.id, 0])),
  events: [],
};

let bannerTimer = 0;

function isLocalhostHost() {
  return ["localhost", "127.0.0.1", "::1"].includes(window.location.hostname);
}

function getStartupIssue() {
  if (!window.webgazer) {
    return "WebGazer skripti yuklanmadi.";
  }
  if (!window.isSecureContext && !isLocalhostHost()) {
    return "Bu sahifa localhost yoki https orqali ochilishi kerak.";
  }
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    return "Brauzer kameraga kirishni qo'llamayapti.";
  }
  return "";
}

function describeWebgazerError(error) {
  if (!error) {
    return "Noma'lum xato.";
  }
  const raw = String(error.message || error);
  const name = error.name || "";
  if (name === "NotAllowedError" || /Permission|denied|Allowed/.test(raw)) {
    return "Kamera ruxsati berilmadi.";
  }
  if (name === "NotFoundError" || /Requested device not found/i.test(raw)) {
    return "Kamera topilmadi.";
  }
  if (name === "NotReadableError" || /Could not start video source|TrackStartError/i.test(raw)) {
    return "Kamera band yoki boshqa dastur ishlatyapti.";
  }
  if (/secure context|https|localhost|getUserMedia/i.test(raw)) {
    return "Sahifani localhost yoki https orqali oching.";
  }
  return raw;
}

function safeWebgazerCall(label, fn) {
  if (!window.webgazer) {
    return;
  }
  try {
    fn();
  } catch (error) {
    console.warn(`WebGazer optional call failed: ${label}`, error);
    addEvent(`Optional call failed: ${label}`);
  }
}

function setStatus(label, cls = "idle") {
  els.statusChip.textContent = label;
  els.statusChip.className = `status-chip ${cls}`;
  els.metricState.textContent = label;
}

function showBanner(message, duration = 2200) {
  clearTimeout(bannerTimer);
  els.banner.textContent = message;
  els.banner.classList.remove("hidden");
  bannerTimer = window.setTimeout(() => {
    els.banner.classList.add("hidden");
  }, duration);
}

function addEvent(message) {
  const stamp = new Date().toLocaleTimeString("uz-UZ", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
  state.events.unshift({ stamp, message });
  state.events = state.events.slice(0, 8);
  renderEvents();
}

function renderEvents() {
  if (!state.events.length) {
    els.eventLog.innerHTML = '<p class="empty">Hali event yo\'q.</p>';
    return;
  }

  els.eventLog.innerHTML = state.events
    .map(
      (entry) => `
        <article class="event-item">
          <time>${entry.stamp}</time>
          <div>${entry.message}</div>
        </article>
      `,
    )
    .join("");
}

function resetZoneVisuals(firedZone = -1) {
  for (const node of els.zoneCards) {
    const zoneId = Number(node.dataset.zoneTile);
    node.classList.toggle("active", zoneId === state.activeZone);
    node.classList.toggle("fired", zoneId === firedZone);
  }

  for (const node of els.zoneStage) {
    const zoneId = Number(node.dataset.zone);
    node.classList.toggle("active", zoneId === state.activeZone);
    node.classList.toggle("fired", zoneId === firedZone);
  }
}

function resolveZone(x, y) {
  const nx = x / window.innerWidth;
  const ny = y / window.innerHeight;
  const matches = ZONES.filter(({ rect }) => {
    const [x1, y1, x2, y2] = rect;
    return nx >= x1 && nx <= x2 && ny >= y1 && ny <= y2;
  });

  if (!matches.length) {
    return null;
  }

  return matches.sort((a, b) => {
    const areaA = (a.rect[2] - a.rect[0]) * (a.rect[3] - a.rect[1]);
    const areaB = (b.rect[2] - b.rect[0]) * (b.rect[3] - b.rect[1]);
    return areaA - areaB;
  })[0];
}

function updateStageGaze(x, y) {
  const rect = els.stage.getBoundingClientRect();
  const left = (x / window.innerWidth) * rect.width;
  const top = (y / window.innerHeight) * rect.height;
  els.gazeDot.style.left = `${left}px`;
  els.gazeDot.style.top = `${top}px`;
  els.gazeDot.classList.remove("hidden");
}

function updateZoneState(zone) {
  if (!zone) {
    state.activeZone = -1;
    state.zoneStartedAt = performance.now();
    els.metricZone.textContent = "—";
    els.metricDwell.textContent = "0%";
    resetZoneVisuals();
    return;
  }

  if (zone.id !== state.activeZone) {
    state.activeZone = zone.id;
    state.zoneStartedAt = performance.now();
    els.metricZone.textContent = zone.label;
    els.metricDwell.textContent = "0%";
    resetZoneVisuals();
    return;
  }

  const elapsed = performance.now() - state.zoneStartedAt;
  const progress = Math.min(elapsed / DWELL_MS, 1);
  els.metricDwell.textContent = `${Math.round(progress * 100)}%`;

  const lastFired = state.lastFiredAt.get(zone.id) ?? 0;
  const canFire = performance.now() - lastFired >= FIRE_COOLDOWN_MS;
  if (progress >= 1 && canFire) {
    state.lastFiredAt.set(zone.id, performance.now());
    showBanner(`${zone.label} zona faollashdi`, 2600);
    addEvent(`${zone.label} dwell trigger`);
    resetZoneVisuals(zone.id);
  }
}

function refreshMetrics() {
  els.metricSamples.textContent = String(state.samples);
  els.metricCalibrated.textContent = state.calibrated ? "Ha" : "Yo'q";
  if (!state.gaze) {
    els.metricGaze.textContent = "—";
  } else {
    els.metricGaze.textContent = `${Math.round(state.gaze.x)}, ${Math.round(state.gaze.y)}`;
  }
}

function updatePreviewVisibility() {
  const visible = state.previewVisible;
  if (window.webgazer) {
    safeWebgazerCall(`showVideo(${visible})`, () => {
      window.webgazer.showVideo(visible);
    });
    safeWebgazerCall(`showFaceOverlay(${visible})`, () => {
      window.webgazer.showFaceOverlay(visible);
    });
    safeWebgazerCall(`showFaceFeedbackBox(${visible})`, () => {
      window.webgazer.showFaceFeedbackBox(visible);
    });
  }
  els.btnPreview.textContent = visible ? "Preview ON" : "Preview OFF";
}

function resetCalibrationUI() {
  state.calibrationHits = new Map(CALIBRATION_POINTS.map((point) => [point.id, 0]));
  els.calibrationProgress.textContent = "0 / 9 nuqta tayyor";
  for (const button of els.calibrationPoints.querySelectorAll(".calibration-point")) {
    button.classList.remove("done");
    button.disabled = false;
    button.textContent = "0/3";
  }
}

function finishCalibration() {
  state.calibrating = false;
  state.calibrated = true;
  els.calibrationOverlay.classList.add("hidden");
  setStatus("Tracking", "ready");
  addEvent("Calibration tugadi");
  showBanner("Calibration tugadi", 2400);
  refreshMetrics();
}

function handleCalibrationClick(pointId, button) {
  const nextCount = (state.calibrationHits.get(pointId) ?? 0) + 1;
  state.calibrationHits.set(pointId, nextCount);
  button.textContent = `${Math.min(nextCount, POINT_REPETITIONS)}/${POINT_REPETITIONS}`;

  if (nextCount >= POINT_REPETITIONS) {
    button.classList.add("done");
    button.disabled = true;
  }

  const doneCount = [...state.calibrationHits.values()].filter((value) => value >= POINT_REPETITIONS).length;
  els.calibrationProgress.textContent = `${doneCount} / ${CALIBRATION_POINTS.length} nuqta tayyor`;

  if (doneCount === CALIBRATION_POINTS.length) {
    finishCalibration();
  }
}

function createCalibrationPoints() {
  els.calibrationPoints.innerHTML = "";
  for (const point of CALIBRATION_POINTS) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "calibration-point";
    button.style.left = `${point.x}%`;
    button.style.top = `${point.y}%`;
    button.textContent = `0/${POINT_REPETITIONS}`;
    button.addEventListener("click", () => handleCalibrationClick(point.id, button));
    els.calibrationPoints.append(button);
  }
}

function startCalibration() {
  if (!state.started) {
    showBanner("Avval Start bosing", 2000);
    return;
  }
  state.calibrating = true;
  state.calibrated = false;
  state.activeZone = -1;
  state.zoneStartedAt = performance.now();
  resetZoneVisuals();
  resetCalibrationUI();
  els.calibrationOverlay.classList.remove("hidden");
  setStatus("Calibrating", "calibrating");
  addEvent("Calibration boshlandi");
}

async function startTracker() {
  if (state.started || !window.webgazer) {
    return;
  }

  const startupIssue = getStartupIssue();
  if (startupIssue) {
    setStatus("Xato", "idle");
    showBanner(startupIssue, 4200);
    addEvent(startupIssue);
    return;
  }

  if (typeof window.webgazer.detectCompatibility === "function" && !window.webgazer.detectCompatibility()) {
    const message = "Bu browser WebGazer uchun mos emas.";
    setStatus("Xato", "idle");
    showBanner(message, 3200);
    addEvent(message);
    return;
  }

  setStatus("Loading", "idle");

  try {
    window.webgazer.params.faceMeshSolutionPath = "https://webgazer.cs.brown.edu/mediapipe/face_mesh";
    window.webgazer.params.saveDataAcrossSessions = false;
    window.webgazer.params.showVideo = state.previewVisible;
    window.webgazer.params.showFaceOverlay = state.previewVisible;
    window.webgazer.params.showFaceFeedbackBox = state.previewVisible;
    window.webgazer.params.showGazeDot = false;

    window.webgazer.setGazeListener((data) => {
      if (!state.started || state.paused || !data) {
        return;
      }

      state.gaze = { x: data.x, y: data.y };
      state.samples += 1;
      updateStageGaze(data.x, data.y);
      const zone = resolveZone(data.x, data.y);
      updateZoneState(zone);
      refreshMetrics();
    });

    await window.webgazer.begin();

    safeWebgazerCall("showPredictionPoints(false)", () => {
      window.webgazer.showPredictionPoints(false);
    });
    safeWebgazerCall("applyKalmanFilter(true)", () => {
      window.webgazer.applyKalmanFilter(true);
    });

    state.started = true;
    state.paused = false;
    state.samples = 0;
    state.gaze = null;
    setStatus("Ready", "ready");
    refreshMetrics();

    els.btnStart.disabled = true;
    els.btnPause.disabled = false;
    els.btnCalibrate.disabled = false;
    els.btnReset.disabled = false;
    els.btnPreview.disabled = false;
    els.btnPause.textContent = "Pause";

    addEvent("Tracker ishga tushdi");
    showBanner("Tracker tayyor. Calibration qiling.", 2600);
  } catch (error) {
    console.error(error);
    const message = describeWebgazerError(error);
    setStatus("Xato", "idle");
    showBanner(message, 4200);
    addEvent(message);
  }
}

function togglePause() {
  if (!state.started || !window.webgazer) {
    return;
  }

  state.paused = !state.paused;
  if (state.paused) {
    window.webgazer.pause();
    setStatus("Paused", "paused");
    els.btnPause.textContent = "Resume";
    addEvent("Tracker pause");
  } else {
    window.webgazer.resume();
    setStatus(state.calibrated ? "Tracking" : "Ready", "ready");
    els.btnPause.textContent = "Pause";
    addEvent("Tracker resume");
  }
}

function resetSession() {
  showBanner("Session qayta yuklanmoqda...", 1600);
  addEvent("Hard reset");
  window.setTimeout(() => {
    window.location.reload();
  }, 250);
}

function bind() {
  createCalibrationPoints();
  renderEvents();
  refreshMetrics();
  resetZoneVisuals();
  const startupIssue = getStartupIssue();
  if (startupIssue) {
    setStatus("Xato", "idle");
    addEvent(startupIssue);
  }

  els.btnStart.addEventListener("click", startTracker);
  els.btnPause.addEventListener("click", togglePause);
  els.btnCalibrate.addEventListener("click", startCalibration);
  els.btnReset.addEventListener("click", resetSession);
  els.btnPreview.addEventListener("click", () => {
    state.previewVisible = !state.previewVisible;
    updatePreviewVisibility();
  });

  window.addEventListener("beforeunload", () => {
    if (window.webgazer) {
      window.webgazer.end();
    }
  });

  window.addEventListener("error", (event) => {
    const stack = event.error?.stack || event.message || "Noma'lum browser xatosi.";
    console.error(event.error || event.message);
    setStatus("Xato", "idle");
    addEvent(stack.split("\n")[0]);
  });

  window.addEventListener("unhandledrejection", (event) => {
    const message = String(event.reason?.message || event.reason || "Unhandled promise rejection");
    console.error(event.reason);
    setStatus("Xato", "idle");
    addEvent(message);
  });
}

bind();
