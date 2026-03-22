const $ = (selector) => document.querySelector(selector);

const headerEl = $("#header");
const mainContent = $("#main-content");
const workspace = $("#workspace");
const composerCard = $("#composer-card");
const boardShell = $("#board-shell");
const boardMain = $("#board-main");
const boardHead = boardMain?.querySelector(".board-head");
const video = $("#camera-video");
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
const calibCanvas = $("#calibration-canvas");
const calibCtx = calibCanvas.getContext("2d");
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

let ws = null;
let cameraReady = false;
let sending = false;
let captureCanvas = null;
let captureCtx = null;
let frameInterval = null;
let calibrating = false;
let bannerTimeout = null;

let currentPage = "core";
let messageWords = [];
let activeGazeTarget = null;
let activeGazeStartedAt = 0;
let gazeCooldownUntil = 0;
let resizeSyncTimer = null;
let layoutSyncTimer = null;
let lastBlinkEventAt = 0;
let lastLongBlinkEventAt = 0;
let lastHeadAwayEventAt = 0;
let lastLowQualityEventAt = 0;
let lastSeriousEmotionAt = 0;
let lastSurpriseEmotionAt = 0;

const TARGET_FPS = 15;
const JPEG_QUALITY = 0.65;
const AAC_DWELL_MS = 1100;
const AAC_ACTION_COOLDOWN_MS = 850;
const MAX_MESSAGE_WORDS = 14;
const SIGNAL_WINDOW_MS = 60000;

const healthSignals = {
    samples: [],
    blinkEvents: [],
    longBlinkEvents: [],
    headAwayEvents: [],
    lowQualityEvents: [],
    seriousEmotionEvents: [],
    surpriseEmotionEvents: [],
    lastEmotion: "—",
};

const AAC_PAGES = {
    core: {
        kicker: "Muloqot paneli",
        title: "Asosiy so'zlar",
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
        kicker: "Parvarish so'zlari",
        title: "Ehtiyoj va parvarish",
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
        kicker: "Hissiyotlar",
        title: "Hissiyot va javoblar",
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
        kicker: "Shaxsiy bo'lim",
        title: "Odamlar va shaxsiy",
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

    const text = messageWords.join(" ");

    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
            command: "speak_text",
            text,
        }));
        showBanner("Matn gapirtirilmoqda", 2);
        return;
    }

    if (!("speechSynthesis" in window)) {
        showBanner("TTS hozir mavjud emas", 3);
        return;
    }

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

function getCameraErrorMessage(err) {
    const name = err?.name || "UnknownError";
    const host = window.location.hostname;

    if (!window.isSecureContext) {
        if (host === "0.0.0.0") {
            return "0.0.0.0 emas, localhost yoki 127.0.0.1 bilan oching";
        }
        return "Kamera faqat https, localhost yoki 127.0.0.1 da ishlaydi";
    }

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        return "Brauzer getUserMedia API ni bermayapti";
    }

    if (name === "NotAllowedError" || name === "PermissionDeniedError") {
        return "Kamera browser yoki macOS tomonidan bloklangan";
    }

    if (name === "NotFoundError" || name === "DevicesNotFoundError") {
        return "Kamera qurilmasi topilmadi";
    }

    if (name === "NotReadableError" || name === "TrackStartError") {
        return "Kamera band yoki boshqa dastur ushlab turibdi";
    }

    if (name === "OverconstrainedError" || name === "ConstraintNotSatisfiedError") {
        return "Kamera parametrlariga mos qurilma topilmadi";
    }

    if (name === "SecurityError") {
        return "Brauzer xavfsizlik siyosati kamerani blokladi";
    }

    return `Kamera xatosi: ${name}`;
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
    const totalSamples = healthSignals.samples.length;
    const trackingSamples = healthSignals.samples.filter((sample) => sample.state === "TRACKING").length;
    const trackingRatio = totalSamples ? trackingSamples / totalSamples : 0;
    const blinkCount = healthSignals.blinkEvents.length;
    const longBlinkCount = healthSignals.longBlinkEvents.length;
    const headAwayCount = healthSignals.headAwayEvents.length;
    const lowQualityCount = healthSignals.lowQualityEvents.length;
    const seriousCount = healthSignals.seriousEmotionEvents.length;
    const surpriseCount = healthSignals.surpriseEmotionEvents.length;

    const fatigueScore = (blinkCount / 6) + (longBlinkCount * 2) + (lowQualityCount * 0.6);
    const stressScore = (seriousCount * 1.8) + (surpriseCount * 1.1) + (headAwayCount * 0.8);
    const attentionPercent = Math.round(trackingRatio * 100);

    const fatigueLevel = levelFromScore(fatigueScore, 3, 6);
    const stressLevel = levelFromScore(stressScore, 3, 6);
    const attentionLevel = attentionPercent >= 80 ? "Yaxshi" : attentionPercent >= 55 ? "O'rta" : "Past";

    insightFatigueLevel.textContent = fatigueLevel;
    insightFatigueNote.textContent = `${blinkCount} blink, ${longBlinkCount} uzun blink. Ko'paysa ko'z charchog'i yoki noqulaylik signali bo'lishi mumkin.`;

    insightStressLevel.textContent = stressLevel;
    insightStressNote.textContent = `${seriousCount} jiddiy, ${surpriseCount} hayron ekspressiya va ${headAwayCount} bosh og'ishi kuzatildi.`;

    insightAttentionLevel.textContent = `${attentionLevel} (${attentionPercent}%)`;
    insightAttentionNote.textContent = `So'nggi 60 soniyada kuzatuv barqarorligi taxminan ${attentionPercent}% bo'ldi.`;

    insightExpressionLevel.textContent = healthSignals.lastEmotion || "—";
    insightExpressionNote.textContent = "Bu hozirgi ekspressiya signali. Klinik tashxis sifatida talqin qilinmaydi.";

    if (fatigueLevel === "Yuqori" || stressLevel === "Yuqori") {
        insightSummary.textContent = "Signal oshgan";
        insightSummaryNote.textContent = "Charchoq yoki noqulaylik signali ko'paygan. Bu kasallik tashxisi emas, lekin kuzatuvni kuchaytirish mumkin.";
    } else if (fatigueLevel === "O'rta" || stressLevel === "O'rta") {
        insightSummary.textContent = "Ehtiyotkor kuzatuv";
        insightSummaryNote.textContent = "O'rta darajadagi yuz/ko'z signallari ko'rindi. Bu faqat yordamchi observatsion panel.";
    } else {
        insightSummary.textContent = "Barqaror signal";
        insightSummaryNote.textContent = "Hozircha keskin signal ko'rinmadi. Baribir bu klinik xulosa bermaydi.";
    }
}

function recordHealthSignals(data) {
    const now = Date.now();

    healthSignals.samples.push({ t: now, state: data.state || "IDLE" });
    healthSignals.lastEmotion = data.emotion || "—";

    if ((data.blink?.single || data.blink?.double) && now - lastBlinkEventAt > 700) {
        healthSignals.blinkEvents.push(now);
        lastBlinkEventAt = now;
    }

    if (data.blink?.long && now - lastLongBlinkEventAt > 1200) {
        healthSignals.longBlinkEvents.push(now);
        lastLongBlinkEventAt = now;
    }

    if (data.state === "HEAD_AWAY" && now - lastHeadAwayEventAt > 2000) {
        healthSignals.headAwayEvents.push(now);
        lastHeadAwayEventAt = now;
    }

    if ((data.state === "LOW_QUALITY" || data.state === "NO_FACE") && now - lastLowQualityEventAt > 2500) {
        healthSignals.lowQualityEvents.push(now);
        lastLowQualityEventAt = now;
    }

    if (String(data.emotion || "").includes("Jiddiy") && now - lastSeriousEmotionAt > 3000) {
        healthSignals.seriousEmotionEvents.push(now);
        lastSeriousEmotionAt = now;
    }

    if (String(data.emotion || "").includes("Hayron") && now - lastSurpriseEmotionAt > 3000) {
        healthSignals.surpriseEmotionEvents.push(now);
        lastSurpriseEmotionAt = now;
    }

    healthSignals.samples = healthSignals.samples.filter((sample) => now - sample.t <= SIGNAL_WINDOW_MS);
    pruneEvents(healthSignals.blinkEvents, now);
    pruneEvents(healthSignals.longBlinkEvents, now);
    pruneEvents(healthSignals.headAwayEvents, now);
    pruneEvents(healthSignals.lowQualityEvents, now);
    pruneEvents(healthSignals.seriousEmotionEvents, now);
    pruneEvents(healthSignals.surpriseEmotionEvents, now);

    updateInsightsPanel();
}

function connectWS() {
    const protocol = location.protocol === "https:" ? "wss:" : "ws:";
    ws = new WebSocket(`${protocol}//${location.host}/ws`);
    ws.binaryType = "arraybuffer";

    ws.onopen = () => {
        setStatus("connected", "Ulangan");
        showBanner("Server bilan ulanish tayyor", 2);
        btnCalibrate.disabled = false;
        syncScreenMetrics();
    };

    ws.onclose = () => {
        setStatus("disconnected", "Uzildi");
        btnCalibrate.disabled = true;
        btnRecalibrate.disabled = true;
        ws = null;
        gazeDot.classList.add("hidden");
        clearGazeSelection();
        setTimeout(connectWS, 2000);
    };

    ws.onerror = () => {
        setStatus("disconnected", "Xato");
    };

    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleServerMessage(data);
        } catch (error) {
            console.error("JSON parse xatosi:", error);
        }
    };
}

function handleServerMessage(data) {
    if (data.error) {
        showBanner(data.error, 3);
        sending = false;
        return;
    }

    if (data.status) {
        sending = false;
        return;
    }

    recordHealthSignals(data);

    if (data.fps !== undefined) {
        fpsDisplay.textContent = `${data.fps} FPS`;
    }

    infoFace.textContent = data.face_found ? "Topildi" : "Yo'q";
    infoFace.style.color = data.face_found ? "var(--accent)" : "var(--danger)";

    const stateMap = {
        TRACKING: "Kuzatuv",
        CALIBRATING: "Kalibratsiya",
        CALIBRATION_DONE: "Tayyor",
        NEEDS_CALIBRATION: "Kalibratsiya kerak",
        NO_FACE: "Yuz yo'q",
        HEAD_AWAY: "Bosh chetda",
        LOW_QUALITY: "Past sifat",
        IDLE: "Kutish",
    };

    infoState.textContent = stateMap[data.state] || data.state || "—";

    if (data.state === "TRACKING") {
        setStatus("tracking", "Kuzatuv");
    } else if (data.state === "CALIBRATING") {
        setStatus("connected", "Kalibratsiya");
    } else {
        setStatus("connected", "Ulangan");
    }

    if (data.emotion) {
        infoEmotion.textContent = data.emotion;
    }

    if (data.zone) {
        infoZone.textContent = data.zone.name || `Zona ${data.zone.idx}`;
    } else {
        infoZone.textContent = "—";
    }

    if (data.gaze) {
        const [sx, sy] = data.gaze;
        infoGaze.textContent = `${Math.round(sx)}, ${Math.round(sy)}`;

        const scrW = window.screen.width || window.innerWidth;
        const scrH = window.screen.height || window.innerHeight;
        const pctX = Math.max(0, Math.min(1, sx / scrW));
        const pctY = Math.max(0, Math.min(1, sy / scrH));
        const viewportX = pctX * window.innerWidth;
        const viewportY = pctY * window.innerHeight;

        gazeDot.style.left = `${viewportX}px`;
        gazeDot.style.top = `${viewportY}px`;
        gazeDot.classList.remove("hidden");

        if (data.state === "TRACKING") {
            updateGazeSelection(viewportX, viewportY);
        } else {
            clearGazeSelection();
        }
    } else {
        infoGaze.textContent = "—";
        gazeDot.classList.add("hidden");
        clearGazeSelection();
    }

    if (data.calibration) {
        const calibration = data.calibration;

        if (calibration.active) {
            calibrating = true;
            calibOverlay.classList.remove("hidden");
            infoCalib.textContent = `${calibration.current}/${calibration.total}`;
            drawCalibrationPoint(calibration);
        } else {
            if (calibrating) {
                calibrating = false;
                calibOverlay.classList.add("hidden");
                if (calibration.done) {
                    showBanner("Kalibratsiya muvaffaqiyatli tugadi", 3);
                    btnRecalibrate.disabled = false;
                }
            }

            infoCalib.textContent = calibration.done ? "Ha" : "Yo'q";
        }

        if (calibration.error) {
            showBanner(calibration.error, 3);
        }
    }

    sending = false;
}

function drawCalibrationPoint(calibration) {
    const width = (calibCanvas.width = window.innerWidth);
    const height = (calibCanvas.height = window.innerHeight);

    calibCtx.clearRect(0, 0, width, height);
    calibCtx.fillStyle = "rgba(0, 0, 0, 0.88)";
    calibCtx.fillRect(0, 0, width, height);

    if (!calibration.point) return;

    const scrW = window.screen.width || width;
    const scrH = window.screen.height || height;
    const px = (calibration.point.x / scrW) * width;
    const py = (calibration.point.y / scrH) * height;
    const radius = 34;
    const startAngle = -Math.PI / 2;
    const endAngle = startAngle + (2 * Math.PI * calibration.progress);

    calibCtx.beginPath();
    calibCtx.arc(px, py, radius, 0, Math.PI * 2);
    calibCtx.strokeStyle = "rgba(255, 255, 255, 0.18)";
    calibCtx.lineWidth = 4;
    calibCtx.stroke();

    calibCtx.beginPath();
    calibCtx.arc(px, py, radius, startAngle, endAngle);
    calibCtx.strokeStyle = "#f0c96b";
    calibCtx.lineWidth = 5;
    calibCtx.stroke();

    calibCtx.beginPath();
    calibCtx.arc(px, py, 10, 0, Math.PI * 2);
    calibCtx.fillStyle = "#f0c96b";
    calibCtx.fill();

    calibCtx.beginPath();
    calibCtx.arc(px, py, 4, 0, Math.PI * 2);
    calibCtx.fillStyle = "#1d1b15";
    calibCtx.fill();

    calibCtx.fillStyle = "#fff5dc";
    calibCtx.font = '600 20px "Sora", sans-serif';
    calibCtx.textAlign = "center";
    calibCtx.fillText(`Nuqtaga qarang ${calibration.current}/${calibration.total}`, width / 2, 48);

    calibCtx.fillStyle = "rgba(255, 245, 220, 0.72)";
    calibCtx.font = '500 14px "Manrope", sans-serif';
    calibCtx.fillText("Ko'zni qimirlatmang, nuqtani ushlab turing", width / 2, 76);

    calibText.textContent = `Nuqta ${calibration.current}/${calibration.total} — ${Math.round(calibration.progress * 100)}%`;
}

async function startCamera() {
    try {
        if (!window.isSecureContext) {
            throw new Error("InsecureContext");
        }

        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            throw new Error("MediaDevicesUnavailable");
        }

        const stream = await navigator.mediaDevices.getUserMedia({
            video: {
                facingMode: "user",
                width: { ideal: 640 },
                height: { ideal: 480 },
            },
            audio: false,
        });

        video.srcObject = stream;
        await video.play();

        captureCanvas = document.createElement("canvas");
        captureCanvas.width = 640;
        captureCanvas.height = 480;
        captureCtx = captureCanvas.getContext("2d");

        cameraReady = true;
        btnStartCam.textContent = "Kamera tayyor";
        btnStartCam.disabled = true;
        showBanner("Kamera ochildi", 2);

        connectWS();

        if (frameInterval) clearInterval(frameInterval);
        frameInterval = setInterval(sendFrame, 1000 / TARGET_FPS);
    } catch (error) {
        const message = getCameraErrorMessage(error);
        setStatus("disconnected", "Kamera xatosi");
        showBanner(`❌ ${message}`, 5);
        console.error("Camera error:", error);
    }
}

function sendFrame() {
    if (!cameraReady || !ws || ws.readyState !== WebSocket.OPEN || sending) {
        return;
    }

    captureCtx.drawImage(video, 0, 0, 640, 480);
    captureCanvas.toBlob(
        (blob) => {
            if (!blob || !ws || ws.readyState !== WebSocket.OPEN) {
                return;
            }

            sending = true;
            blob.arrayBuffer().then((buffer) => {
                ws.send(buffer);
            });
        },
        "image/jpeg",
        JPEG_QUALITY,
    );
}

function startCalibration() {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;

    ws.send(JSON.stringify({
        command: "start_calibration",
        screen_w: window.screen.width || window.innerWidth,
        screen_h: window.screen.height || window.innerHeight,
    }));

    calibrating = true;
    calibOverlay.classList.remove("hidden");
    showBanner("Kalibratsiya boshlandi", 2);
}

function syncScreenMetrics() {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify({
        command: "set_screen",
        screen_w: window.screen.width || window.innerWidth,
        screen_h: window.screen.height || window.innerHeight,
    }));
}

btnStartCam.addEventListener("click", startCamera);
btnCalibrate.addEventListener("click", startCalibration);
btnRecalibrate.addEventListener("click", () => {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ command: "reset_calibration" }));
    }
    startCalibration();
});

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

    if (event.key === "Escape" && calibrating) {
        calibrating = false;
        calibOverlay.classList.add("hidden");
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ command: "reset_calibration" }));
        }
    }
});

window.addEventListener("resize", () => {
    if (resizeSyncTimer) {
        clearTimeout(resizeSyncTimer);
    }
    resizeSyncTimer = setTimeout(() => {
        syncScreenMetrics();
        syncLayoutFit();
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

setStatus("disconnected", "Kamerani oching");
setHeaderView("board");
updateMessageDisplay();
updateInsightsPanel();
renderBoardNav();
renderBoardGrid();
window.addEventListener("load", syncLayoutFit);
document.fonts?.ready?.then(() => {
    syncLayoutFit();
});
