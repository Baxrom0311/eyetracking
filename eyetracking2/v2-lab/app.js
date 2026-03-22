const $ = (selector) => document.querySelector(selector);

const headerEl = $("#header");
const mainContent = $("#main-content");
const workspace = $("#workspace");
const composerCard = $("#composer-card");
const boardShell = $("#board-shell");
const boardMain = $("#board-main");
const boardHead = boardMain?.querySelector(".board-head");
const cameraContainer = $("#camera-container");
const cameraVideo = $("#camera-video");
const overlayCanvas = $("#overlay-canvas");
const btnStartCam = $("#btn-start-camera");
const btnCalibrate = $("#btn-calibrate");
const btnRecalibrate = $("#btn-recalibrate");
const btnBoardView = $("#btn-board-view");
const btnOpenSession = $("#btn-open-session");
const btnOpenInsights = $("#btn-open-insights");
const btnCloseSession = $("#btn-close-session");
const btnCloseInsights = $("#btn-close-insights");
const btnSpeak = $("#btn-speak");
const btnClearMessage = $("#btn-clear-message");
const btnBackspace = $("#btn-backspace");
const messageDisplay = $("#message-display");
const boardNav = $("#board-nav");
const boardTitle = $("#board-title");
const boardSubtitle = $("#board-subtitle");
const boardKicker = $("#board-kicker");
const aacGrid = $("#aac-grid");
const statusBadge = $("#status-badge");
const statusText = $("#status-text");
const fpsDisplay = $("#fps-display");
const infoState = $("#info-state");
const infoEmotion = $("#info-emotion");
const infoFace = $("#info-face");
const infoGaze = $("#info-gaze");
const infoZone = $("#info-zone");
const infoCalib = $("#info-calib");
const infoFocus = $("#info-focus");
const infoWords = $("#info-words");
const calibOverlay = $("#calibration-overlay");
const calibrationPoints = $("#calibration-points");
const calibrationTarget = $("#calibration-target");
const calibText = $("#calib-text");
const bannerEl = $("#banner");
const bannerText = $("#banner-text");
const gazeDot = $("#screen-gaze-dot");
const sessionModal = $("#session-modal");
const insightsModal = $("#insights-modal");
const insightFatigueLevel = $("#insight-fatigue-level");
const insightFatigueNote = $("#insight-fatigue-note");
const insightStressLevel = $("#insight-stress-level");
const insightStressNote = $("#insight-stress-note");
const insightAttentionLevel = $("#insight-attention-level");
const insightAttentionNote = $("#insight-attention-note");
const insightExpressionLevel = $("#insight-expression-level");
const insightExpressionNote = $("#insight-expression-note");
const insightSummary = $("#insight-summary");
const insightSummaryNote = $("#insight-summary-note");

let currentPage = "core";
let messageWords = [];
let activeGazeTarget = null;
let activeGazeStartedAt = 0;
let gazeCooldownUntil = 0;
let resizeSyncTimer = null;
let layoutSyncTimer = null;
let bannerTimeout = null;
let fpsTimer = null;
let validationTimer = null;
let validationSettleTimer = null;

const AAC_DWELL_MS = 1100;
const AAC_ACTION_COOLDOWN_MS = 850;
const MAX_MESSAGE_WORDS = 14;
const CALIBRATION_CLICKS = 4;
const VALIDATION_SETTLE_MS = 350;
const VALIDATION_SAMPLE_MS = 1100;
const ROI_RADIUS = 160;
const SIGNAL_WINDOW_MS = 60000;
const TRAIL_SAMPLE_MAX = 70;

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

const AAC_PAGES = {
    core: {
        kicker: "Communication Board",
        title: "Core Words",
        subtitle: "Eng ko'p ishlatiladigan asosiy so'zlar. Bir necha tile tanlab, keyin gapirtiring.",
        note: "tez ishlatiladigan",
        tiles: [
            { label: "Men", symbol: "I", hint: "subyekt", tone: "gold" },
            { label: "Xohlayman", symbol: "+", hint: "istak", tone: "mint" },
            { label: "Ko'proq", symbol: "++", hint: "davom", tone: "sky" },
            { label: "To'xta", symbol: "■", hint: "to'xtatish", tone: "coral" },
            { label: "Sen", symbol: "U", hint: "murojaat", tone: "sand" },
            { label: "Ha", symbol: "✓", hint: "tasdiq", tone: "lime" },
            { label: "Yo'q", symbol: "×", hint: "rad etish", tone: "rose" },
            { label: "Bor", symbol: "→", hint: "harakat", tone: "mint" },
            { label: "Yordam", symbol: "!", hint: "chaqiruv", tone: "coral" },
            { label: "Yana", symbol: "↻", hint: "takror", tone: "sky" },
            { label: "Yoqadi", symbol: "♥", hint: "his", tone: "gold" },
            { label: "Emas", symbol: "⊘", hint: "inkor", tone: "slate" },
        ],
    },
    needs: {
        kicker: "Care Words",
        title: "Needs and Care",
        subtitle: "Parvarish, tibbiy yordam va kundalik ehtiyojlar uchun tezkor tugmalar.",
        note: "parvarish",
        tiles: [
            { label: "Suv", symbol: "💧", hint: "ichimlik", tone: "sky" },
            { label: "Og'riq", symbol: "✚", hint: "og'riq bor", tone: "coral" },
            { label: "Hojatxona", symbol: "WC", hint: "hojat", tone: "sand" },
            { label: "Shifokor", symbol: "Dr", hint: "tibbiy yordam", tone: "slate" },
            { label: "Sovuq", symbol: "❄", hint: "harorat", tone: "sky" },
            { label: "Issiq", symbol: "☼", hint: "harorat", tone: "gold" },
            { label: "Ochman", symbol: "🍽", hint: "ovqat", tone: "lime" },
            { label: "Charchadim", symbol: "☾", hint: "dam", tone: "rose" },
            { label: "Dori", symbol: "Rx", hint: "medikament", tone: "mint" },
            { label: "Burang", symbol: "↺", hint: "pozitsiya", tone: "sand" },
            { label: "Yostiq", symbol: "▣", hint: "qulaylik", tone: "gold" },
            { label: "Nafas", symbol: "≈", hint: "nafas olish", tone: "mint" },
        ],
    },
    feelings: {
        kicker: "Emotions",
        title: "Feelings and Responses",
        subtitle: "Holat, kayfiyat va javoblarni tez ifodalash uchun qisqa so'zlar.",
        note: "holat",
        tiles: [
            { label: "Yaxshi", symbol: "☺", hint: "ijobiy", tone: "mint" },
            { label: "Yomon", symbol: "☹", hint: "salbiy", tone: "coral" },
            { label: "Qo'rqdim", symbol: "!", hint: "xavotir", tone: "rose" },
            { label: "Tinch", symbol: "○", hint: "xotirjam", tone: "sky" },
            { label: "Rahmat", symbol: "♥", hint: "minnatdorchilik", tone: "gold" },
            { label: "Iltimos", symbol: "⋯", hint: "iltimos", tone: "sand" },
            { label: "Tushundim", symbol: "✓", hint: "angladim", tone: "lime" },
            { label: "Tushunmadim", symbol: "?", hint: "izoh kerak", tone: "slate" },
            { label: "Yetarli", symbol: "■", hint: "bo'ldi", tone: "coral" },
            { label: "Yana ayting", symbol: "↻", hint: "takrorlang", tone: "sky" },
            { label: "Yolg'iz", symbol: "1", hint: "hamroh kerak", tone: "rose" },
            { label: "Xursand", symbol: "☀", hint: "kayfiyat", tone: "gold" },
        ],
    },
    personal: {
        kicker: "Personal",
        title: "People and Personal",
        subtitle: "Oila, shaxsiy mavzular va kundalik hayotga oid tugmalar.",
        note: "shaxsiy",
        tiles: [
            { label: "Ona", symbol: "M", hint: "oila", tone: "rose" },
            { label: "Ota", symbol: "D", hint: "oila", tone: "sand" },
            { label: "Hamshira", symbol: "N", hint: "parvarish", tone: "mint" },
            { label: "Oilam", symbol: "⌂", hint: "yaqinlar", tone: "gold" },
            { label: "Telefon", symbol: "☎", hint: "aloqa", tone: "slate" },
            { label: "Musiqa", symbol: "♫", hint: "ko'ngilochar", tone: "sky" },
            { label: "Uy", symbol: "⌂", hint: "joy", tone: "lime" },
            { label: "Tashqariga", symbol: "↗", hint: "sayr", tone: "mint" },
            { label: "Ismim", symbol: "ID", hint: "tanishtirish", tone: "sand" },
            { label: "Ibodat", symbol: "✦", hint: "ruhiy", tone: "gold" },
            { label: "TV", symbol: "▭", hint: "ekran", tone: "sky" },
            { label: "Qo'ng'iroq", symbol: "⟲", hint: "chaqirish", tone: "coral" },
        ],
    },
};

const trackingState = {
    started: false,
    previewVisible: true,
    phase: "idle",
    calibrated: false,
    samples: 0,
    gaze: null,
    lastGazeAt: 0,
    activeZone: -1,
    zoneStartedAt: 0,
    frameCounter: 0,
    validationResults: [],
    validationAverageError: null,
    validationRoiRate: null,
    validationBuffer: [],
    trail: [],
    calibrationHits: new Map(CALIBRATION_POINTS.map((point) => [point.id, 0])),
    events: [],
};

const healthSignals = {
    samples: [],
    lostSignalEvents: [],
    jitterEvents: [],
    dwellEvents: [],
    lastSignal: "Signal kutilmoqda",
};

function addEvent(message) {
    const stamp = new Date().toLocaleTimeString("uz-UZ", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
    });
    trackingState.events.unshift({ stamp, message: String(message) });
    trackingState.events = trackingState.events.slice(0, 24);
}

function renderValidation() {
    if (trackingState.phase === "validation") {
        const done = trackingState.validationResults.length;
        infoEmotion.textContent = `${done} / ${VALIDATION_POINTS.length} tekshirildi`;
        return;
    }

    if (!trackingState.calibrated) {
        infoEmotion.textContent = "—";
        return;
    }

    if (trackingState.validationAverageError == null) {
        infoEmotion.textContent = "Kutilmoqda";
        return;
    }

    const roiPercent = trackingState.validationRoiRate == null
        ? "—"
        : `${Math.round(trackingState.validationRoiRate * 100)}%`;
    infoEmotion.textContent = `${Math.round(trackingState.validationAverageError)} px • ROI ${roiPercent}`;
}

function escapeHtml(value) {
    return value
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;");
}

function showBanner(text, sec = 3) {
    bannerText.textContent = text;
    bannerEl.classList.remove("hidden");
    if (bannerTimeout) clearTimeout(bannerTimeout);
    bannerTimeout = setTimeout(() => {
        bannerEl.classList.add("hidden");
    }, sec * 1000);
}

function getPx(value) {
    const parsed = Number.parseFloat(value);
    return Number.isFinite(parsed) ? parsed : 0;
}

function getGridColumnCount() {
    if (window.innerWidth <= 980) {
        return 3;
    }
    return 4;
}

function syncLayoutFit() {
    if (!headerEl || !mainContent || !workspace || !composerCard || !boardShell || !boardMain || !boardHead) {
        return;
    }

    const viewportHeight = window.innerHeight;
    const mainStyles = getComputedStyle(mainContent);
    const workspaceStyles = getComputedStyle(workspace);
    const boardShellStyles = getComputedStyle(boardShell);
    const boardMainStyles = getComputedStyle(boardMain);
    const boardNavStyles = getComputedStyle(boardNav);
    const gridStyles = getComputedStyle(aacGrid);

    const mainVerticalPadding = getPx(mainStyles.paddingTop) + getPx(mainStyles.paddingBottom);
    const availableMainHeight = Math.max(420, viewportHeight - headerEl.offsetHeight);
    const workspaceGap = getPx(workspaceStyles.rowGap || workspaceStyles.gap);
    const composerHeight = composerCard.offsetHeight;
    const boardAvailableHeight = Math.max(360, availableMainHeight - composerHeight - workspaceGap - mainVerticalPadding);
    const boardShellVerticalPadding = getPx(boardShellStyles.paddingTop) + getPx(boardShellStyles.paddingBottom);
    const boardMainGap = getPx(boardMainStyles.rowGap || boardMainStyles.gap);
    const boardHeadHeight = boardHead.offsetHeight;
    const cols = getGridColumnCount();
    const rows = Math.ceil((AAC_PAGES[currentPage]?.tiles.length || 0) / cols);
    const gridGap = getPx(gridStyles.rowGap || gridStyles.gap);
    const gridAvailableHeight = Math.max(180, boardAvailableHeight - boardShellVerticalPadding - boardHeadHeight - boardMainGap);
    const rawRowHeight = Math.floor((gridAvailableHeight - (gridGap * Math.max(0, rows - 1))) / Math.max(1, rows));
    const minRowHeight = viewportHeight < 760 ? 90 : 108;
    const clampedRowHeight = Math.max(minRowHeight, Math.min(220, rawRowHeight));
    const navGap = getPx(boardNavStyles.rowGap || boardNavStyles.gap);
    const navCount = Object.keys(AAC_PAGES).length;
    const rawNavHeight = Math.floor((boardAvailableHeight - boardShellVerticalPadding - (navGap * Math.max(0, navCount - 1))) / Math.max(1, navCount));
    const minNavHeight = viewportHeight < 760 ? 76 : 92;
    const clampedNavHeight = Math.max(minNavHeight, Math.min(160, rawNavHeight));
    const fitLock = rawRowHeight >= minRowHeight && rawNavHeight >= minNavHeight;

    mainContent.style.height = `${availableMainHeight}px`;
    document.documentElement.style.setProperty("--board-fit-height", `${boardAvailableHeight}px`);
    document.documentElement.style.setProperty("--aac-row-height", `${clampedRowHeight}px`);
    document.documentElement.style.setProperty("--board-tab-height", `${clampedNavHeight}px`);

    document.body.classList.toggle("fit-lock", fitLock);
    document.body.classList.toggle("fit-compact", clampedRowHeight <= 126 || clampedNavHeight <= 104);
    document.body.classList.toggle("fit-tight", clampedRowHeight <= 108 || clampedNavHeight <= 88);
}

function scheduleLayoutFit() {
    if (layoutSyncTimer) {
        clearTimeout(layoutSyncTimer);
    }
    layoutSyncTimer = setTimeout(() => {
        syncLayoutFit();
    }, 40);
}

function setHeaderView(view) {
    btnBoardView.classList.toggle("is-active", view === "board");
    btnOpenSession.classList.toggle("is-active", view === "session");
    btnOpenInsights.classList.toggle("is-active", view === "insights");
}

function openSessionModal() {
    closeOverlayWindows(false);
    sessionModal.classList.remove("hidden");
    sessionModal.setAttribute("aria-hidden", "false");
    document.body.classList.add("modal-open");
    setHeaderView("session");
}

function openInsightsModal() {
    closeOverlayWindows(false);
    insightsModal.classList.remove("hidden");
    insightsModal.setAttribute("aria-hidden", "false");
    document.body.classList.add("modal-open");
    setHeaderView("insights");
}

function closeOverlayWindows(resetHeader = true) {
    sessionModal.classList.add("hidden");
    sessionModal.setAttribute("aria-hidden", "true");
    insightsModal.classList.add("hidden");
    insightsModal.setAttribute("aria-hidden", "true");
    document.body.classList.remove("modal-open");
    if (resetHeader) {
        setHeaderView("board");
    }
}

function closeSessionModal() {
    closeOverlayWindows(true);
}

function closeInsightsModal() {
    closeOverlayWindows(true);
}

function setStatus(state, text) {
    statusBadge.className = `status-badge status-${state}`;
    statusText.textContent = text;
    infoState.textContent = text;
}

function updateMessageDisplay() {
    infoWords.textContent = String(messageWords.length);
    if (messageWords.length === 0) {
        messageDisplay.innerHTML = '<span class="message-placeholder">Tanlangan so\'zlar shu yerda yig\'iladi</span>';
        scheduleLayoutFit();
        return;
    }

    messageDisplay.innerHTML = messageWords
        .map((word) => `<span class="message-chip">${escapeHtml(word)}</span>`)
        .join("");
    scheduleLayoutFit();
}

function appendWord(word) {
    if (messageWords.length >= MAX_MESSAGE_WORDS) {
        showBanner("Matn uzunligi limiti to'ldi", 2);
        return;
    }

    messageWords.push(word);
    updateMessageDisplay();
}

function clearMessage() {
    messageWords = [];
    updateMessageDisplay();
}

function backspaceMessage() {
    if (messageWords.length === 0) return;
    messageWords.pop();
    updateMessageDisplay();
}

function speakMessage() {
    if (messageWords.length === 0) {
        showBanner("Avval so'z tanlang", 2);
        return;
    }

    if (!("speechSynthesis" in window)) {
        showBanner("TTS hozir mavjud emas", 3);
        return;
    }

    const text = messageWords.join(" ");
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "uz-UZ";
    utterance.rate = 0.92;
    utterance.pitch = 1.0;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
    showBanner("Matn gapirtirildi", 2);
}

function renderBoardNav() {
    boardNav.innerHTML = Object.entries(AAC_PAGES)
        .map(([key, page], index) => `
            <button
                class="board-tab gaze-target ${key === currentPage ? "is-active" : ""}"
                data-action="page"
                data-page="${key}"
                data-label="${escapeHtml(page.title)}"
            >
                <span class="tab-kicker">${String(index + 1).padStart(2, "0")}</span>
                <strong>${escapeHtml(page.title)}</strong>
                <span class="tab-note">${escapeHtml(page.note)}</span>
            </button>
        `)
        .join("");
    scheduleLayoutFit();
}

function renderBoardGrid() {
    const page = AAC_PAGES[currentPage];
    boardKicker.textContent = page.kicker;
    boardTitle.textContent = page.title;
    boardSubtitle.textContent = page.subtitle;

    aacGrid.innerHTML = page.tiles
        .map((tile) => `
            <button
                class="aac-tile gaze-target tone-${tile.tone}"
                data-action="word"
                data-word="${escapeHtml(tile.label)}"
                data-label="${escapeHtml(tile.label)}"
            >
                <span class="tile-symbol">${escapeHtml(tile.symbol)}</span>
                <span class="tile-text">${escapeHtml(tile.label)}</span>
                <span class="tile-hint">${escapeHtml(tile.hint)}</span>
            </button>
        `)
        .join("");
    scheduleLayoutFit();
}

function setPage(pageKey) {
    if (!AAC_PAGES[pageKey]) return;
    currentPage = pageKey;
    clearGazeSelection();
    renderBoardNav();
    renderBoardGrid();
}

function clearGazeSelection() {
    if (activeGazeTarget) {
        activeGazeTarget.classList.remove("gaze-active");
        activeGazeTarget.style.setProperty("--dwell-progress", "0%");
    }
    activeGazeTarget = null;
    activeGazeStartedAt = 0;
}

function getGazeTargetAt(x, y) {
    const target = document.elementFromPoint(x, y)?.closest(".gaze-target");
    if (!target) return null;
    if (target.disabled) return null;
    return target;
}

function performTargetAction(target, source = "manual") {
    const action = target.dataset.action;

    if (action === "word") {
        appendWord(target.dataset.word || target.dataset.label || "");
    } else if (action === "page") {
        setPage(target.dataset.page);
    } else if (action === "open-session") {
        openSessionModal();
    } else if (action === "open-insights") {
        openInsightsModal();
    } else if (action === "close-session") {
        closeSessionModal();
    } else if (action === "close-insights") {
        closeInsightsModal();
    } else if (action === "show-board") {
        closeOverlayWindows(true);
    } else if (action === "clear") {
        clearMessage();
    } else if (action === "backspace") {
        backspaceMessage();
    } else if (action === "speak") {
        speakMessage();
    }

    if (source === "gaze") {
        showBanner(`${target.dataset.label || "Tanlov"} tanlandi`, 1.2);
    }
}

function updateGazeSelection(viewportX, viewportY) {
    if (trackingState.phase !== "tracking") {
        infoFocus.textContent = "—";
        clearGazeSelection();
        return;
    }

    const now = performance.now();

    if (now < gazeCooldownUntil) {
        return;
    }

    const target = getGazeTargetAt(viewportX, viewportY);

    if (!target) {
        infoFocus.textContent = "—";
        clearGazeSelection();
        return;
    }

    infoFocus.textContent = target.dataset.label || target.textContent.trim();

    if (target !== activeGazeTarget) {
        clearGazeSelection();
        activeGazeTarget = target;
        activeGazeStartedAt = now;
        activeGazeTarget.classList.add("gaze-active");
    }

    const progress = Math.min(1, (now - activeGazeStartedAt) / AAC_DWELL_MS);
    activeGazeTarget.style.setProperty("--dwell-progress", `${Math.round(progress * 100)}%`);

    if (progress >= 1) {
        const firedTarget = activeGazeTarget;
        gazeCooldownUntil = now + AAC_ACTION_COOLDOWN_MS;
        clearGazeSelection();
        performTargetAction(firedTarget, "gaze");
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

function syncZoneVisuals(firedZone = -1) {
    for (const node of document.querySelectorAll("[data-zone-tile]")) {
        const zoneId = Number(node.dataset.zoneTile);
        node.classList.toggle("active", zoneId === trackingState.activeZone);
        node.classList.toggle("fired", zoneId === firedZone);
    }

    for (const node of document.querySelectorAll("[data-zone]")) {
        const zoneId = Number(node.dataset.zone);
        node.classList.toggle("active", zoneId === trackingState.activeZone);
        node.classList.toggle("fired", zoneId === firedZone);
    }
}

function updateZoneState(zone) {
    if (!zone || trackingState.phase !== "tracking") {
        trackingState.activeZone = -1;
        trackingState.zoneStartedAt = performance.now();
        infoZone.textContent = "—";
        syncZoneVisuals();
        return;
    }

    if (zone.id !== trackingState.activeZone) {
        trackingState.activeZone = zone.id;
        trackingState.zoneStartedAt = performance.now();
        infoZone.textContent = zone.label;
        syncZoneVisuals();
        return;
    }

    const progress = Math.min(1, (performance.now() - trackingState.zoneStartedAt) / AAC_DWELL_MS);
    if (progress >= 1) {
        healthSignals.dwellEvents.push(Date.now());
        showBanner(`${zone.label} zona faollashdi`, 2);
        addEvent(`${zone.label} dwell trigger`);
        syncZoneVisuals(zone.id);
        trackingState.zoneStartedAt = performance.now();
    }
}

function resetCalibrationProgress() {
    trackingState.calibrationHits = new Map(CALIBRATION_POINTS.map((point) => [point.id, 0]));
    calibrationPoints.innerHTML = "";
    calibrationTarget.classList.add("hidden");
    calibrationPoints.classList.remove("hidden");
    calibText.textContent = "0 / 9 nuqta tayyor";

    for (const point of CALIBRATION_POINTS) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "calibration-point";
        button.style.left = `${point.x}%`;
        button.style.top = `${point.y}%`;
        button.textContent = `0/${CALIBRATION_CLICKS}`;
        button.addEventListener("click", () => handleCalibrationPoint(point.id, button));
        calibrationPoints.append(button);
    }
}

function openCalibrationOverlay() {
    calibOverlay.classList.remove("hidden");
    document.body.classList.add("modal-open");
}

function closeCalibrationOverlay() {
    calibOverlay.classList.add("hidden");
    document.body.classList.remove("modal-open");
    calibrationTarget.classList.add("hidden");
    calibrationPoints.classList.add("hidden");
}

function handleCalibrationPoint(pointId, button) {
    const nextCount = (trackingState.calibrationHits.get(pointId) ?? 0) + 1;
    trackingState.calibrationHits.set(pointId, nextCount);
    button.textContent = `${Math.min(nextCount, CALIBRATION_CLICKS)}/${CALIBRATION_CLICKS}`;

    if (nextCount >= CALIBRATION_CLICKS) {
        button.disabled = true;
        button.classList.add("done");
        button.style.opacity = "0.42";
    }

    const doneCount = [...trackingState.calibrationHits.values()].filter((value) => value >= CALIBRATION_CLICKS).length;
    calibText.textContent = `${doneCount} / ${CALIBRATION_POINTS.length} nuqta tayyor`;

    if (doneCount === CALIBRATION_POINTS.length) {
        calibrationPoints.classList.add("hidden");
        void runValidation();
    }
}

function setCalibrationTarget(percentX, percentY) {
    calibrationTarget.style.left = `${percentX}%`;
    calibrationTarget.style.top = `${percentY}%`;
    calibrationTarget.classList.remove("hidden");
}

function recordValidationPoint(point) {
    return new Promise((resolve) => {
        trackingState.validationBuffer = [];
        setCalibrationTarget(point.x, point.y);
        calibText.textContent = `Validation: ${point.label}`;

        validationSettleTimer = window.setTimeout(() => {
            if (calibOverlay.classList.contains("hidden")) {
                validationSettleTimer = null;
                resolve({ cancelled: true });
                return;
            }

            validationTimer = window.setTimeout(() => {
                validationTimer = null;
                if (calibOverlay.classList.contains("hidden")) {
                    resolve({ cancelled: true });
                    return;
                }
                const samples = [...trackingState.validationBuffer];
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
        }, VALIDATION_SETTLE_MS);
    });
}

async function runValidation() {
    trackingState.phase = "validation";
    setStatus("connected", "Validation");
    infoCalib.textContent = "Tekshirilmoqda";
    trackingState.validationResults = [];
    trackingState.validationAverageError = null;
    trackingState.validationRoiRate = null;
    renderValidation();
    updateInsightsPanel();

    for (const point of VALIDATION_POINTS) {
        const result = await recordValidationPoint(point);
        if (result.cancelled) {
            return;
        }
        trackingState.validationResults.push(result);
        renderValidation();
    }

    const valid = trackingState.validationResults.filter((entry) => Number.isFinite(entry.error));
    trackingState.validationAverageError = valid.length
        ? valid.reduce((sum, entry) => sum + entry.error, 0) / valid.length
        : null;
    trackingState.validationRoiRate = valid.length
        ? valid.filter((entry) => entry.error <= ROI_RADIUS).length / valid.length
        : null;

    calibrationTarget.classList.add("hidden");
    closeCalibrationOverlay();
    trackingState.phase = "tracking";
    trackingState.calibrated = true;
    infoCalib.textContent = "Ha";
    infoEmotion.textContent = trackingState.validationAverageError == null
        ? "Validation yo'q"
        : `${Math.round(trackingState.validationAverageError)} px`;
    setStatus("tracking", "Tracking");
    addEvent(`Validation tugadi: avg ${trackingState.validationAverageError == null ? "—" : Math.round(trackingState.validationAverageError)} px`);
    showBanner("Kalibratsiya va validation tugadi", 3);
    renderValidation();
    updateInsightsPanel();
}

function startCalibration() {
    if (!trackingState.started) {
        showBanner("Avval kamerani oching", 2);
        return;
    }

    clearValidationTimer();
    clearGazeSelection();
    trackingState.phase = "calibration";
    trackingState.calibrated = false;
    trackingState.activeZone = -1;
    trackingState.zoneStartedAt = performance.now();
    trackingState.validationResults = [];
    trackingState.validationAverageError = null;
    trackingState.validationRoiRate = null;
    trackingState.validationBuffer = [];
    infoCalib.textContent = "Yo'q";
    infoZone.textContent = "—";
    syncZoneVisuals();
    renderValidation();
    resetCalibrationProgress();
    openCalibrationOverlay();
    setStatus("connected", "Kalibratsiya");
    addEvent("Calibration boshlandi");
    showBanner("Har nuqtaga 4 marta bosing", 2.6);
}

function pruneEvents(array, now, windowMs = SIGNAL_WINDOW_MS) {
    while (array.length && now - array[0] > windowMs) {
        array.shift();
    }
}

function levelFromScore(score, medium, high) {
    if (score >= high) return "Yuqori";
    if (score >= medium) return "O'rta";
    return "Past";
}

function updateInsightsPanel() {
    const now = Date.now();
    pruneEvents(healthSignals.lostSignalEvents, now);
    pruneEvents(healthSignals.jitterEvents, now);
    pruneEvents(healthSignals.dwellEvents, now);

    const totalSamples = healthSignals.samples.length;
    const trackingSamples = healthSignals.samples.filter((sample) => sample.state === "tracking").length;
    const trackingRatio = totalSamples ? trackingSamples / totalSamples : 0;
    const fatigueScore = healthSignals.lostSignalEvents.length * 1.4 + (trackingState.validationAverageError || 0) / 120;
    const stressScore = healthSignals.jitterEvents.length * 1.6 + (trackingState.validationAverageError || 0) / 180;
    const attentionPercent = Math.round(trackingRatio * 100);

    const fatigueLevel = levelFromScore(fatigueScore, 3, 6);
    const stressLevel = levelFromScore(stressScore, 3, 6);
    const attentionLevel = attentionPercent >= 80 ? "Yaxshi" : attentionPercent >= 55 ? "O'rta" : "Past";

    insightFatigueLevel.textContent = fatigueLevel;
    insightFatigueNote.textContent = `${healthSignals.lostSignalEvents.length} signal uzilishi kuzatildi. Validation error bu signalni kuchaytiradi.`;

    insightStressLevel.textContent = stressLevel;
    insightStressNote.textContent = `${healthSignals.jitterEvents.length} ta yuqori jitter holati qayd etildi. Bu bosh harakati yoki yoritish bilan bog'liq bo'lishi mumkin.`;

    insightAttentionLevel.textContent = `${attentionLevel} (${attentionPercent}%)`;
    insightAttentionNote.textContent = `So'nggi 60 soniyada tracking barqarorligi taxminan ${attentionPercent}% bo'ldi.`;

    const signalLabel = trackingState.validationAverageError == null
        ? "Validation kutilmoqda"
        : trackingState.validationAverageError <= ROI_RADIUS
            ? "Barqaror"
            : "Nozik sozlash kerak";

    insightExpressionLevel.textContent = signalLabel;
    insightExpressionNote.textContent = `O'rtacha validation xatosi ${trackingState.validationAverageError == null ? "—" : `${Math.round(trackingState.validationAverageError)} px`} bo'ldi.`;

    if (fatigueLevel === "Yuqori" || stressLevel === "Yuqori") {
        insightSummary.textContent = "Signal oshgan";
        insightSummaryNote.textContent = "Tracking sifati o'zgaruvchan. Yoritish, kamera balandligi yoki calibrationni qayta tekshirib ko'ring.";
    } else if (fatigueLevel === "O'rta" || stressLevel === "O'rta") {
        insightSummary.textContent = "Ehtiyotkor kuzatuv";
        insightSummaryNote.textContent = "O'rta darajadagi signal tebranishlari ko'rindi. Bu klinik xulosa emas.";
    } else {
        insightSummary.textContent = "Barqaror signal";
        insightSummaryNote.textContent = "Hozircha tracking barqaror ko'rinmoqda. Bu faqat UI ichidagi observatsion ko'rsatkich.";
    }
}

function recordHealthSample(x, y) {
    const now = Date.now();
    healthSignals.samples.push({ t: now, state: trackingState.phase });
    healthSignals.samples = healthSignals.samples.filter((sample) => now - sample.t <= SIGNAL_WINDOW_MS);

    const recentTrail = trackingState.trail.slice(-10);
    if (recentTrail.length >= 2) {
        const prev = recentTrail[recentTrail.length - 2];
        const dx = x - prev.x;
        const dy = y - prev.y;
        const distance = Math.hypot(dx, dy);
        if (distance > 180) {
            healthSignals.jitterEvents.push(now);
        }
    }

    healthSignals.lastSignal = trackingState.calibrated ? "Tracking signal" : "Calibration signal";
    updateInsightsPanel();
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

function updatePreviewVisibility() {
    if (!window.webgazer) {
        return;
    }

    safeWebgazerCall(`showVideo(${trackingState.previewVisible})`, () => {
        window.webgazer.showVideo(trackingState.previewVisible);
    });
    safeWebgazerCall(`showFaceOverlay(${trackingState.previewVisible})`, () => {
        window.webgazer.showFaceOverlay(trackingState.previewVisible);
    });
    safeWebgazerCall(`showFaceFeedbackBox(${trackingState.previewVisible})`, () => {
        window.webgazer.showFaceFeedbackBox(trackingState.previewVisible);
    });
}

function mountPreviewElements() {
    const ids = ["webgazerVideoFeed", "webgazerFaceOverlay", "webgazerFaceFeedbackBox"];
    for (const id of ids) {
        const node = document.getElementById(id);
        if (!node) continue;
        node.classList.add("webgazer-preview-layer");
        if (node.parentElement !== cameraContainer) {
            cameraContainer.append(node);
        }
    }
}

function updateGazeDot(x, y) {
    gazeDot.style.left = `${x}px`;
    gazeDot.style.top = `${y}px`;
    gazeDot.classList.remove("hidden");
    infoGaze.textContent = `${Math.round(x)}, ${Math.round(y)}`;
}

function clearValidationTimer() {
    if (validationSettleTimer) {
        clearTimeout(validationSettleTimer);
        validationSettleTimer = null;
    }
    if (validationTimer) {
        clearTimeout(validationTimer);
        validationTimer = null;
    }
}

async function startTracker() {
    if (trackingState.started || !window.webgazer) {
        return;
    }

    const startupIssue = getStartupIssue();
    if (startupIssue) {
        setStatus("disconnected", "Xato");
        showBanner(startupIssue, 4);
        addEvent(startupIssue);
        return;
    }

    try {
        setStatus("connected", "Yuklanmoqda");
        window.webgazer.params.faceMeshSolutionPath = `${new URL("../vendor/mediapipe/face_mesh/", window.location.href).href}`;
        window.webgazer.params.saveDataAcrossSessions = false;
        window.webgazer.params.showVideo = true;
        window.webgazer.params.showFaceOverlay = true;
        window.webgazer.params.showFaceFeedbackBox = true;
        window.webgazer.params.showGazeDot = false;

        window.webgazer.setGazeListener((data) => {
            if (!trackingState.started || !data) {
                return;
            }

            const now = Date.now();
            trackingState.gaze = { x: data.x, y: data.y };
            trackingState.samples += 1;
            trackingState.lastGazeAt = now;
            trackingState.frameCounter += 1;
            trackingState.trail.push({ x: data.x, y: data.y });
            trackingState.trail = trackingState.trail.slice(-TRAIL_SAMPLE_MAX);
            updateGazeDot(data.x, data.y);
            updateGazeSelection(data.x, data.y);

            const zone = resolveZone(data.x, data.y);
            updateZoneState(zone);

            if (trackingState.phase === "validation") {
                trackingState.validationBuffer.push({ x: data.x, y: data.y });
            }

            infoFace.textContent = "Topildi";
            infoFace.style.color = "var(--accent)";
            recordHealthSample(data.x, data.y);
        });

        await window.webgazer.begin();
        safeWebgazerCall("showPredictionPoints(false)", () => {
            window.webgazer.showPredictionPoints(false);
        });
        safeWebgazerCall("applyKalmanFilter(true)", () => {
            window.webgazer.applyKalmanFilter(true);
        });

        trackingState.started = true;
        trackingState.previewVisible = true;
        trackingState.phase = "idle";
        trackingState.samples = 0;
        trackingState.gaze = null;
        trackingState.activeZone = -1;
        trackingState.zoneStartedAt = performance.now();
        infoCalib.textContent = "Yo'q";
        syncZoneVisuals();
        renderValidation();

        btnStartCam.textContent = "Kamera tayyor";
        btnStartCam.disabled = true;
        btnCalibrate.disabled = false;
        btnRecalibrate.disabled = false;

        setStatus("connected", "Ulangan");
        addEvent("WebGazer ishga tushdi");
        showBanner("Kamera tayyor. Kalibratsiyani boshlang.", 2.4);
        mountPreviewElements();
        updatePreviewVisibility();
        openSessionModal();
    } catch (error) {
        console.error(error);
        const message = describeWebgazerError(error);
        setStatus("disconnected", "Kamera xatosi");
        showBanner(message, 4);
        addEvent(message);
    }
}

function exportSession() {
    const payload = {
        exported_at: new Date().toISOString(),
        phase: trackingState.phase,
        samples: trackingState.samples,
        words: messageWords,
        validation_average_error_px: trackingState.validationAverageError,
        validation_roi_rate: trackingState.validationRoiRate,
        validation_results: trackingState.validationResults,
        events: trackingState.events,
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `gazespeak-webgazer-${Date.now()}.json`;
    link.click();
    URL.revokeObjectURL(url);
    showBanner("Session export qilindi", 2);
}

function refreshRuntimeState() {
    const now = Date.now();
    if (trackingState.started && now - trackingState.lastGazeAt > 1600) {
        infoFace.textContent = "Yo'q";
        infoFace.style.color = "var(--danger)";
        gazeDot.classList.add("hidden");
        clearGazeSelection();
        healthSignals.lostSignalEvents.push(now);
        updateInsightsPanel();
    }

    fpsDisplay.textContent = `${trackingState.frameCounter} FPS`;
    trackingState.frameCounter = 0;
}

function bind() {
    cameraVideo.style.display = "none";
    overlayCanvas.style.display = "none";

    btnStartCam.addEventListener("click", startTracker);
    btnCalibrate.addEventListener("click", startCalibration);
    btnRecalibrate.addEventListener("click", startCalibration);
    btnBackspace.addEventListener("click", backspaceMessage);
    btnClearMessage.addEventListener("click", clearMessage);
    btnSpeak.addEventListener("click", speakMessage);

    document.addEventListener("click", (event) => {
        const target = event.target.closest(".gaze-target");
        if (!target || target.disabled) return;
        performTargetAction(target, "manual");
    });

    document.addEventListener("keydown", (event) => {
        if ((!sessionModal.classList.contains("hidden") || !insightsModal.classList.contains("hidden")) && event.key === "Escape") {
            closeOverlayWindows(true);
            return;
        }

        if (event.key === "Escape" && !calibOverlay.classList.contains("hidden")) {
            clearValidationTimer();
            closeCalibrationOverlay();
            trackingState.phase = trackingState.calibrated ? "tracking" : "idle";
            setStatus(trackingState.calibrated ? "tracking" : "connected", trackingState.calibrated ? "Tracking" : "Ulangan");
            renderValidation();
        }
    });

    window.addEventListener("resize", () => {
        if (resizeSyncTimer) {
            clearTimeout(resizeSyncTimer);
        }
        resizeSyncTimer = setTimeout(() => {
            scheduleLayoutFit();
        }, 150);
    });

    sessionModal.addEventListener("click", (event) => {
        if (event.target.matches("[data-session-close]")) {
            closeSessionModal();
        }
    });

    insightsModal.addEventListener("click", (event) => {
        if (event.target.matches("[data-insights-close]")) {
            closeInsightsModal();
        }
    });

    window.addEventListener("beforeunload", () => {
        clearValidationTimer();
        clearTimeout(fpsTimer);
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

    fpsTimer = setInterval(refreshRuntimeState, 1000);
}

setStatus("disconnected", "Kamerani oching");
setHeaderView("board");
updateMessageDisplay();
renderValidation();
updateInsightsPanel();
renderBoardNav();
renderBoardGrid();
scheduleLayoutFit();
window.addEventListener("load", syncLayoutFit);
document.fonts?.ready?.then(() => {
    syncLayoutFit();
});
bind();
