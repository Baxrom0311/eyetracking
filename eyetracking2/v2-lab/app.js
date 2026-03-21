const CALIBRATION_POINTS = [
  { id: "c1", x: 15, y: 15 },
  { id: "c2", x: 50, y: 15 },
  { id: "c3", x: 85, y: 15 },
  { id: "c4", x: 15, y: 50 },
  { id: "c5", x: 50, y: 50 },
  { id: "c6", x: 85, y: 50 },
  { id: "c7", x: 15, y: 85 },
  { id: "c8", x: 50, y: 85 },
  { id: "c9", x: 85, y: 85 },
];

const VALIDATION_POINTS = [
  { id: "v1", x: 15, y: 15, label: "Yuqori chap" },
  { id: "v2", x: 85, y: 15, label: "Yuqori o'ng" },
  { id: "v3", x: 50, y: 50, label: "Markaz" },
  { id: "v4", x: 15, y: 85, label: "Pastki chap" },
  { id: "v5", x: 85, y: 85, label: "Pastki o'ng" },
];

const ZONES = [
  { id: 0, label: "Yuqori chap", rect: [0, 0, 0.5, 0.5] },
  { id: 1, label: "Yuqori o'ng", rect: [0.5, 0, 1, 0.5] },
  { id: 2, label: "Pastki chap", rect: [0, 0.5, 0.5, 1] },
  { id: 3, label: "Pastki o'ng", rect: [0.5, 0.5, 1, 1] },
  { id: 4, label: "Markaz", rect: [0.33, 0.33, 0.67, 0.67] },
];

const CALIBRATION_CLICKS = 4;
const VALIDATION_SETTLE_MS = 350;
const VALIDATION_SAMPLE_MS = 1100;
const ROI_RADIUS = 160;
const DWELL_MS = 1600;
const TRAIL_MAX = 70;

const els = {
  stage: document.querySelector("#stage"),
  target: document.querySelector("#target"),
  cursor: document.querySelector("#gaze-cursor"),
  messageEyebrow: document.querySelector("#message-eyebrow"),
  messageTitle: document.querySelector("#message-title"),
  messageBody: document.querySelector("#message-body"),
  phaseBadge: document.querySelector("#phase-badge"),
  btnStart: document.querySelector("#btn-start"),
  btnRecalibrate: document.querySelector("#btn-recalibrate"),
  btnPreview: document.querySelector("#btn-preview"),
  btnExport: document.querySelector("#btn-export"),
  metricPhase: document.querySelector("#metric-phase"),
  metricGaze: document.querySelector("#metric-gaze"),
  metricSamples: document.querySelector("#metric-samples"),
  metricError: document.querySelector("#metric-error"),
  metricRoi: document.querySelector("#metric-roi"),
  metricZone: document.querySelector("#metric-zone"),
  validationList: document.querySelector("#validation-list"),
  eventLog: document.querySelector("#event-log"),
  trailCanvas: document.querySelector("#trail-canvas"),
  steps: [...document.querySelectorAll("[data-step]")],
  zones: [...document.querySelectorAll("[data-zone]")],
  zoneCards: [...document.querySelectorAll("[data-zone-tile]")],
};

const ctx = els.trailCanvas.getContext("2d");

const state = {
  started: false,
  previewVisible: false,
  phase: "idle",
  samples: 0,
  gaze: null,
  trail: [],
  zone: -1,
  zoneStartedAt: 0,
  events: [],
  calibrationHits: new Map(CALIBRATION_POINTS.map((point) => [point.id, 0])),
  validationResults: [],
  validationIndex: -1,
  validationBuffer: [],
  validationAverageError: null,
  validationRoiRate: null,
};

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
  if (/Failed to fetch/i.test(raw)) {
    return "WebGazer runtime fayllari yuklanmadi. Local server orqali oching yoki vendor assetlarni tekshiring.";
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

function setPhase(phase) {
  state.phase = phase;
  const labelMap = {
    idle: "Idle",
    calibration: "Calibration",
    validation: "Validation",
    tracking: "Tracking",
  };
  els.phaseBadge.textContent = labelMap[phase] ?? phase;
  const chipClass = {
    idle: "idle",
    calibration: "calibrating",
    validation: "paused",
    tracking: "ready",
  };
  els.phaseBadge.className = `status-chip ${chipClass[phase] ?? "idle"}`;
  els.metricPhase.textContent = labelMap[phase] ?? phase;

  const rank = {
    start: phase === "idle" ? "active" : "done",
    calibration: phase === "calibration" ? "active" : ["validation", "tracking"].includes(phase) ? "done" : "",
    validation: phase === "validation" ? "active" : phase === "tracking" ? "done" : "",
    tracking: phase === "tracking" ? "active" : "",
  };

  for (const step of els.steps) {
    const key = step.dataset.step;
    step.classList.toggle("active", rank[key] === "active");
    step.classList.toggle("done", rank[key] === "done");
  }
}

function setMessage(eyebrow, title, body) {
  els.messageEyebrow.textContent = eyebrow;
  els.messageTitle.textContent = title;
  els.messageBody.textContent = body;
}

function addEvent(message) {
  const stamp = new Date().toLocaleTimeString("uz-UZ", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
  state.events.unshift({ stamp, message });
  state.events = state.events.slice(0, 10);
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
          <strong>${entry.message}</strong>
          <time>${entry.stamp}</time>
        </article>
      `,
    )
    .join("");
}

function renderValidation() {
  if (!state.validationResults.length) {
    els.validationList.innerHTML = '<p class="empty">Validation hali ishlamagan.</p>';
    return;
  }

  els.validationList.innerHTML = state.validationResults
    .map((result) => {
      const quality = result.error <= ROI_RADIUS ? "ROI ichida" : "ROI tashqarisida";
      return `
        <article class="validation-item">
          <strong>${result.label}</strong>
          <small>Error: ${Math.round(result.error)} px • ${quality} • ${result.samples} samples</small>
        </article>
      `;
    })
    .join("");
}

function resizeCanvas() {
  const ratio = window.devicePixelRatio || 1;
  const rect = els.stage.getBoundingClientRect();
  els.trailCanvas.width = Math.max(1, Math.round(rect.width * ratio));
  els.trailCanvas.height = Math.max(1, Math.round(rect.height * ratio));
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
}

function stagePositionFromViewport(x, y) {
  const rect = els.stage.getBoundingClientRect();
  return {
    x: (x / window.innerWidth) * rect.width,
    y: (y / window.innerHeight) * rect.height,
  };
}

function setTarget(percentX, percentY) {
  els.target.style.left = `${percentX}%`;
  els.target.style.top = `${percentY}%`;
  els.target.classList.remove("hidden");
}

function hideTarget() {
  els.target.classList.add("hidden");
}

function drawTrail() {
  const rect = els.stage.getBoundingClientRect();
  ctx.clearRect(0, 0, rect.width, rect.height);
  for (let index = 0; index < state.trail.length; index += 1) {
    const point = state.trail[index];
    const alpha = (index + 1) / state.trail.length;
    ctx.beginPath();
    ctx.fillStyle = `rgba(153, 226, 180, ${0.08 + alpha * 0.36})`;
    ctx.arc(point.x, point.y, 3 + alpha * 9, 0, Math.PI * 2);
    ctx.fill();
  }
}

function pushTrail(x, y) {
  const pos = stagePositionFromViewport(x, y);
  state.trail.push(pos);
  state.trail = state.trail.slice(-TRAIL_MAX);
  drawTrail();
}

function updateCursor(x, y) {
  const pos = stagePositionFromViewport(x, y);
  els.cursor.style.left = `${pos.x}px`;
  els.cursor.style.top = `${pos.y}px`;
  els.cursor.classList.remove("hidden");
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

function updateZone(zone) {
  if (!zone) {
    state.zone = -1;
    state.zoneStartedAt = performance.now();
    els.metricZone.textContent = "—";
    syncZoneClasses(-1, -1);
    return;
  }

  if (state.zone !== zone.id) {
    state.zone = zone.id;
    state.zoneStartedAt = performance.now();
    els.metricZone.textContent = zone.label;
    syncZoneClasses(zone.id, -1);
    return;
  }

  const progress = (performance.now() - state.zoneStartedAt) / DWELL_MS;
  if (progress >= 1) {
    addEvent(`${zone.label} zone dwell fired`);
    setMessage("Tracking", "Zone dwell faollashdi", `${zone.label} zonasi 1.6 soniya ushlab turildi.`);
    syncZoneClasses(zone.id, zone.id);
    state.zoneStartedAt = performance.now();
  }
}

function syncZoneClasses(activeId, firedId) {
  for (const zoneNode of els.zones) {
    const zoneId = Number(zoneNode.dataset.zone);
    zoneNode.classList.toggle("active", zoneId === activeId);
    zoneNode.classList.toggle("fired", zoneId === firedId);
  }
  for (const zoneNode of els.zoneCards) {
    const zoneId = Number(zoneNode.dataset.zoneTile);
    zoneNode.classList.toggle("active", zoneId === activeId);
    zoneNode.classList.toggle("fired", zoneId === firedId);
  }
}

function refreshTelemetry() {
  els.metricSamples.textContent = String(state.samples);
  els.metricGaze.textContent = state.gaze
    ? `${Math.round(state.gaze.x)}, ${Math.round(state.gaze.y)}`
    : "—";
  els.metricError.textContent = state.validationAverageError == null
    ? "—"
    : `${Math.round(state.validationAverageError)} px`;
  els.metricRoi.textContent = state.validationRoiRate == null
    ? "—"
    : `${Math.round(state.validationRoiRate * 100)}%`;
}

function updatePreview() {
  if (!window.webgazer) {
    return;
  }
  safeWebgazerCall(`showVideo(${state.previewVisible})`, () => {
    window.webgazer.showVideo(state.previewVisible);
  });
  safeWebgazerCall(`showFaceOverlay(${state.previewVisible})`, () => {
    window.webgazer.showFaceOverlay(state.previewVisible);
  });
  safeWebgazerCall(`showFaceFeedbackBox(${state.previewVisible})`, () => {
    window.webgazer.showFaceFeedbackBox(state.previewVisible);
  });
  els.btnPreview.textContent = state.previewVisible ? "Preview ON" : "Preview OFF";
}

function recordValidationPoint(point) {
  return new Promise((resolve) => {
    state.validationBuffer = [];
    state.validationIndex += 1;
    setTarget(point.x, point.y);
    setMessage(
      "Validation",
      `${point.label} nuqtasiga qarang`,
      "Nuqtani bosmang. Faqat tik qarab turing. O'rtacha error va ROI mosligi hisoblanadi.",
    );

    window.setTimeout(() => {
      const sampleWindow = window.setTimeout(() => {
        const samples = [...state.validationBuffer];
        if (!samples.length) {
          resolve({
            id: point.id,
            label: point.label,
            error: Number.POSITIVE_INFINITY,
            samples: 0,
          });
          return;
        }

        const meanX = samples.reduce((sum, entry) => sum + entry.x, 0) / samples.length;
        const meanY = samples.reduce((sum, entry) => sum + entry.y, 0) / samples.length;
        const targetX = (point.x / 100) * window.innerWidth;
        const targetY = (point.y / 100) * window.innerHeight;
        const error = Math.hypot(meanX - targetX, meanY - targetY);
        resolve({
          id: point.id,
          label: point.label,
          error,
          samples: samples.length,
        });
      }, VALIDATION_SAMPLE_MS);

      state._activeValidationTimer = sampleWindow;
    }, VALIDATION_SETTLE_MS);
  });
}

async function runValidation() {
  setPhase("validation");
  state.validationResults = [];
  state.validationAverageError = null;
  state.validationRoiRate = null;
  renderValidation();

  for (const point of VALIDATION_POINTS) {
    const result = await recordValidationPoint(point);
    state.validationResults.push(result);
    renderValidation();
  }

  hideTarget();
  const valid = state.validationResults.filter((entry) => Number.isFinite(entry.error));
  const avgError = valid.length
    ? valid.reduce((sum, entry) => sum + entry.error, 0) / valid.length
    : null;
  const roiRate = valid.length
    ? valid.filter((entry) => entry.error <= ROI_RADIUS).length / valid.length
    : null;

  state.validationAverageError = avgError;
  state.validationRoiRate = roiRate;
  refreshTelemetry();
  addEvent(`Validation tugadi: avg ${avgError ? Math.round(avgError) : "—"} px`);
}

function createCalibrationButtons() {
  CALIBRATION_POINTS.forEach((point, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "calibration-point";
    button.style.left = `${point.x}%`;
    button.style.top = `${point.y}%`;
    button.dataset.calibration = point.id;
    button.textContent = String(index + 1);
    button.addEventListener("click", async () => {
      const current = state.calibrationHits.get(point.id) ?? 0;
      const next = current + 1;
      state.calibrationHits.set(point.id, next);
      button.style.opacity = String(Math.max(0.35, 1 - next * 0.12));
      if (next >= CALIBRATION_CLICKS) {
        button.disabled = true;
        button.classList.add("done");
        button.style.opacity = "0.4";
      }
      const done = [...state.calibrationHits.values()].filter((value) => value >= CALIBRATION_CLICKS).length;
      setMessage(
        "Calibration",
        `Nuqtalar tayyor: ${done}/${CALIBRATION_POINTS.length}`,
        "Har nuqtaga qarab 4 marta bosing. Boshni imkon qadar qimirlatmang.",
      );
      if (done === CALIBRATION_POINTS.length) {
        for (const node of document.querySelectorAll("[data-calibration]")) {
          node.remove();
        }
        await runValidation();
        setPhase("tracking");
        setMessage(
          "Tracking",
          "Live tracking yoqildi",
          "Endi trail, zona dwell va validation summary ishlayapti. Xohlasangiz export qiling.",
        );
        addEvent("Calibration tugadi");
      }
    });
    els.stage.append(button);
  });
}

async function startFlow() {
  if (state.started || !window.webgazer) {
    return;
  }

  const startupIssue = getStartupIssue();
  if (startupIssue) {
    setMessage("Xato", "Start imkonsiz", startupIssue);
    addEvent(startupIssue);
    return;
  }

  try {
    window.webgazer.params.faceMeshSolutionPath = `${new URL("../vendor/mediapipe/face_mesh/", window.location.href).href}`;
    window.webgazer.params.saveDataAcrossSessions = false;
    window.webgazer.params.showVideo = state.previewVisible;
    window.webgazer.params.showFaceOverlay = state.previewVisible;
    window.webgazer.params.showFaceFeedbackBox = state.previewVisible;
    window.webgazer.params.showGazeDot = false;

    window.webgazer.setGazeListener((data) => {
      if (!state.started || !data) {
        return;
      }

      state.gaze = { x: data.x, y: data.y };
      state.samples += 1;
      updateCursor(data.x, data.y);
      pushTrail(data.x, data.y);
      refreshTelemetry();

      if (state.phase === "validation") {
        state.validationBuffer.push({ x: data.x, y: data.y });
      }

      if (state.phase === "tracking") {
        const zone = resolveZone(data.x, data.y);
        updateZone(zone);
      }
    });

    await window.webgazer.begin();

    safeWebgazerCall("showPredictionPoints(false)", () => {
      window.webgazer.showPredictionPoints(false);
    });
    safeWebgazerCall("applyKalmanFilter(true)", () => {
      window.webgazer.applyKalmanFilter(true);
    });

    state.started = true;
    state.samples = 0;
    state.gaze = null;
    state.trail = [];
    state.validationResults = [];
    state.validationAverageError = null;
    state.validationRoiRate = null;
    state.calibrationHits = new Map(CALIBRATION_POINTS.map((point) => [point.id, 0]));

    els.btnStart.disabled = true;
    els.btnRecalibrate.disabled = false;
    els.btnPreview.disabled = false;
    els.btnExport.disabled = false;

    setPhase("calibration");
    setMessage(
      "Calibration",
      "9 nuqtali calibration boshlandi",
      "Har nuqtaga qarab 4 marta bosing. WebGazer clicklardan modelni o'rgatadi.",
    );
    addEvent("Tracker ishga tushdi");
    createCalibrationButtons();
  } catch (error) {
    console.error(error);
    const message = describeWebgazerError(error);
    setMessage("Xato", "Tracker ishga tushmadi", message);
    addEvent(message);
  }
}

function exportSession() {
  const payload = {
    exported_at: new Date().toISOString(),
    phase: state.phase,
    samples: state.samples,
    validation_average_error_px: state.validationAverageError,
    validation_roi_rate: state.validationRoiRate,
    validation_results: state.validationResults,
    events: state.events,
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `webgazer-session-${Date.now()}.json`;
  link.click();
  URL.revokeObjectURL(url);
  addEvent("Session export qilindi");
}

function resetFlow() {
  addEvent("Hard reset");
  setMessage(
    "Reset",
    "Session qayta yuklanmoqda",
    "WebGazer state toza boshlanishi uchun sahifa qayta ochiladi.",
  );
  window.setTimeout(() => {
    window.location.reload();
  }, 250);
}

function bind() {
  resizeCanvas();
  renderEvents();
  renderValidation();
  refreshTelemetry();
  setPhase("idle");
  const startupIssue = getStartupIssue();
  if (startupIssue) {
    setMessage("Xato", "Startdan oldin tuzatish kerak", startupIssue);
    addEvent(startupIssue);
  }

  els.btnStart.addEventListener("click", startFlow);
  els.btnRecalibrate.addEventListener("click", resetFlow);
  els.btnPreview.addEventListener("click", () => {
    state.previewVisible = !state.previewVisible;
    updatePreview();
  });
  els.btnExport.addEventListener("click", exportSession);

  window.addEventListener("resize", () => {
    resizeCanvas();
    drawTrail();
  });

  window.addEventListener("beforeunload", () => {
    if (window.webgazer) {
      window.webgazer.end();
    }
  });

  window.addEventListener("error", (event) => {
    const stack = event.error?.stack || event.message || "Noma'lum browser xatosi.";
    console.error(event.error || event.message);
    addEvent(stack.split("\n")[0]);
  });

  window.addEventListener("unhandledrejection", (event) => {
    const message = String(event.reason?.message || event.reason || "Unhandled promise rejection");
    console.error(event.reason);
    addEvent(message);
  });
}

bind();
