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
const btnCloseSession = $("#btn-close-session");
const btnSpeak = $("#btn-speak");
const btnClearMessage = $("#btn-clear-message");
const btnBackspace = $("#btn-backspace");
const btnToggleMode = $("#btn-toggle-mode");
const messageDisplay = $("#message-display");
const predictionStrip = $("#prediction-strip");
const quickStrip = $("#quick-strip");
const emergencyStrip = $("#emergency-strip");
const phraseBank = $("#phrase-bank");
const phraseCaption = $("#phrase-caption");
const modeBadge = $("#mode-badge");
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
const modeSummary = $("#mode-summary");
const calibOverlay = $("#calibration-overlay");
const calibCanvas = $("#calibration-canvas");
const calibCtx = calibCanvas.getContext("2d");
const calibText = $("#calib-text");
const bannerEl = $("#banner");
const bannerText = $("#banner-text");
const gazeDot = $("#screen-gaze-dot");
const sessionModal = $("#session-modal");

let ws = null;
let cameraReady = false;
let sending = false;
let capturePending = false;
let captureCanvas = null;
let captureCtx = null;
let frameInterval = null;
let calibrating = false;
let bannerTimeout = null;

let currentPage = "core";
let currentMode = "patient";
let messageWords = [];
let activeGazeTarget = null;
let activeGazeStartedAt = 0;
let gazeCooldownUntil = 0;
let resizeSyncTimer = null;
let layoutSyncTimer = null;

const TARGET_FPS = 12;
const JPEG_QUALITY = 0.58;
const CAPTURE_WIDTH = 512;
const CAPTURE_HEIGHT = 384;
const AAC_DWELL_MS = 1450;
const AAC_ACTION_COOLDOWN_MS = 1100;
const AAC_TARGET_STICKY_PX = 42;
const MAX_MESSAGE_WORDS = 14;

const PATIENT_PAGES = {
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

const CARE_PAGES = {
    care: {
        kicker: "Parvarish paneli",
        title: "Parvarish amallari",
        subtitle: "Hamshira yoki qarovchi uchun tez-tez kerak bo'ladigan amallar.",
        note: "amallar",
        tiles: [
            { label: "Hamshira", symbol: "N", hint: "chaqirish", tone: "coral" },
            { label: "Shifokor", symbol: "Dr", hint: "ko'rik", tone: "slate" },
            { label: "Dori", symbol: "Rx", hint: "dorilar", tone: "mint" },
            { label: "Suv", symbol: "💧", hint: "ichimlik", tone: "sky" },
            { label: "Aspirator", symbol: "↯", hint: "sekretsiya", tone: "coral" },
            { label: "Kislorod", symbol: "O2", hint: "nafas", tone: "sky" },
            { label: "Burang", symbol: "↺", hint: "pozitsiya", tone: "sand" },
            { label: "Ko'taring", symbol: "↑", hint: "holat", tone: "gold" },
            { label: "Yostiq", symbol: "▣", hint: "qulaylik", tone: "gold" },
            { label: "Tozalang", symbol: "✦", hint: "gigiena", tone: "mint" },
            { label: "Tekshiring", symbol: "?", hint: "nazorat", tone: "slate" },
            { label: "Hojatxona", symbol: "WC", hint: "hojat", tone: "sand" },
        ],
    },
    comfort: {
        kicker: "Qulaylik",
        title: "Qulaylik va holat",
        subtitle: "Bemorning qulayligi va tana holatini tez ifodalash.",
        note: "qulaylik",
        tiles: [
            { label: "Og'riq", symbol: "✚", hint: "og'riq", tone: "coral" },
            { label: "Sovuq", symbol: "❄", hint: "harorat", tone: "sky" },
            { label: "Issiq", symbol: "☼", hint: "harorat", tone: "gold" },
            { label: "Chanqadim", symbol: "💧", hint: "ichimlik", tone: "sky" },
            { label: "Ochman", symbol: "🍽", hint: "ovqat", tone: "lime" },
            { label: "Charchadim", symbol: "☾", hint: "dam", tone: "rose" },
            { label: "Tinch", symbol: "○", hint: "xotirjam", tone: "mint" },
            { label: "Yotqizing", symbol: "↓", hint: "holat", tone: "sand" },
            { label: "O'tiring", symbol: "↥", hint: "holat", tone: "gold" },
            { label: "Pastga", symbol: "↧", hint: "balandlik", tone: "slate" },
            { label: "Sekinroq", symbol: "≈", hint: "sur'at", tone: "sky" },
            { label: "Tezroq", symbol: "≫", hint: "sur'at", tone: "coral" },
        ],
    },
    confirm: {
        kicker: "Tasdiqlash",
        title: "Tasdiq va boshqaruv",
        subtitle: "Ha/yo'q, davom ettirish yoki to'xtatish uchun tezkor javoblar.",
        note: "tasdiq",
        tiles: [
            { label: "Ha", symbol: "✓", hint: "tasdiq", tone: "lime" },
            { label: "Yo'q", symbol: "×", hint: "rad etish", tone: "rose" },
            { label: "Yana", symbol: "↻", hint: "takror", tone: "sky" },
            { label: "To'xta", symbol: "■", hint: "to'xtatish", tone: "coral" },
            { label: "Yetarli", symbol: "■", hint: "bo'ldi", tone: "sand" },
            { label: "Kerak", symbol: "+", hint: "talab", tone: "gold" },
            { label: "Emas", symbol: "⊘", hint: "inkor", tone: "slate" },
            { label: "Tushundim", symbol: "✓", hint: "angladim", tone: "mint" },
            { label: "Tushunmadim", symbol: "?", hint: "izoh", tone: "slate" },
            { label: "Og'ir", symbol: "!", hint: "kuchli", tone: "coral" },
            { label: "Qulay", symbol: "◌", hint: "holat", tone: "mint" },
            { label: "Rahmat", symbol: "♥", hint: "minnatdorchilik", tone: "gold" },
        ],
    },
    family: {
        kicker: "Aloqa",
        title: "Oila va aloqa",
        subtitle: "Oila bilan bog'lanish va kundalik aloqa uchun kerakli iboralar.",
        note: "aloqa",
        tiles: [
            { label: "Ona", symbol: "M", hint: "oila", tone: "rose" },
            { label: "Ota", symbol: "D", hint: "oila", tone: "sand" },
            { label: "Oilam", symbol: "⌂", hint: "yaqinlar", tone: "gold" },
            { label: "Telefon", symbol: "☎", hint: "aloqa", tone: "slate" },
            { label: "Video", symbol: "▭", hint: "video", tone: "sky" },
            { label: "Musiqa", symbol: "♫", hint: "ko'ngilochar", tone: "sky" },
            { label: "TV", symbol: "▭", hint: "ekran", tone: "slate" },
            { label: "Ibodat", symbol: "✦", hint: "ruhiy", tone: "gold" },
            { label: "Kelishsin", symbol: "⇢", hint: "tashrif", tone: "mint" },
            { label: "Uy", symbol: "⌂", hint: "joy", tone: "lime" },
            { label: "Uxlamoqchiman", symbol: "☾", hint: "dam", tone: "rose" },
            { label: "Gaplashay", symbol: "⋯", hint: "suhbat", tone: "mint" },
        ],
    },
};

const AAC_MODES = {
    patient: {
        name: "Asosiy panel",
        summary: "Bemor muloqoti",
        toggleLabel: "Parvarish paneli",
        defaultPage: "core",
        phraseCaption: "Ko'p ishlatiladigan tayyor gaplar.",
        defaultPredictions: ["Men", "Ha", "Yo'q", "Yordam"],
        quickReplies: [
            { label: "Ha", tone: "lime", type: "fast" },
            { label: "Yo'q", tone: "rose", type: "fast" },
            { label: "Yordam kerak", tone: "coral", type: "phrase" },
            { label: "Og'riq bor", tone: "coral", type: "phrase" },
            { label: "To'xtating", tone: "sand", type: "phrase" },
            { label: "Rahmat", tone: "gold", type: "phrase" },
        ],
        emergencyActions: [
            { label: "Tez yordam kerak", tone: "danger" },
            { label: "Nafas olish qiyin", tone: "danger" },
            { label: "Kuchli og'riq", tone: "danger" },
            { label: "Hamshirani chaqiring", tone: "danger" },
        ],
        phraseBank: [
            "Men suv xohlayman",
            "Meni burang",
            "Menga yostiq kerak",
            "Hojatxona kerak",
            "Men charchadim",
            "Oilam bilan gaplashmoqchiman",
        ],
        predictionMap: {
            "__start__": ["Men", "Ha", "Yo'q", "Yordam"],
            "men": ["Xohlayman", "Yaxshi", "Yomon", "Yordam"],
            "men xohlayman": ["Suv", "Yordam", "Ko'proq", "Yostiq"],
            "og'riq": ["Bor", "Ko'proq", "Shifokor"],
            "yordam": ["Kerak", "Hamshira", "Tezroq"],
            "hojatxona": ["Kerak"],
            "nafas": ["Qiyin", "Kerak"],
        },
        pages: PATIENT_PAGES,
    },
    caregiver: {
        name: "Parvarish paneli",
        summary: "Qarov so'rovlari",
        toggleLabel: "Asosiy panel",
        defaultPage: "care",
        phraseCaption: "Qarov va holat uchun tayyor gaplar.",
        defaultPredictions: ["Meni", "Hamshira", "Og'riq", "Yostiq"],
        quickReplies: [
            { label: "Ha", tone: "lime", type: "fast" },
            { label: "Yo'q", tone: "rose", type: "fast" },
            { label: "Meni burang", tone: "sand", type: "phrase" },
            { label: "Yostiqni to'g'rilang", tone: "gold", type: "phrase" },
            { label: "Hamshirani chaqiring", tone: "coral", type: "phrase" },
            { label: "Og'riqni tekshiring", tone: "coral", type: "phrase" },
        ],
        emergencyActions: [
            { label: "Aspirator kerak", tone: "danger" },
            { label: "Kislorodni tekshiring", tone: "danger" },
            { label: "Dorini tekshiring", tone: "danger" },
            { label: "Holatim yomonlashdi", tone: "danger" },
        ],
        phraseBank: [
            "Meni chapga buring",
            "Meni o'ngga buring",
            "Boshingizni ko'taring",
            "Kislorodni tekshiring",
            "Dorini tekshiring",
            "Aspirator kerak",
        ],
        predictionMap: {
            "__start__": ["Meni", "Hamshira", "Og'riq", "Yostiq"],
            "meni": ["Burang", "Ko'taring", "Yotqizing"],
            "hamshira": ["Chaqiring", "Kerak"],
            "og'riq": ["Bor", "Kuchli", "Tekshiring"],
            "nafas": ["Qiyin", "Tekshiring"],
            "yostiq": ["Kerak", "To'g'rilang"],
        },
        pages: CARE_PAGES,
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

function setTextIfChanged(node, value) {
    if (!node) return;
    const nextValue = String(value);
    if (node.textContent !== nextValue) {
        node.textContent = nextValue;
    }
}

function setStyleIfChanged(node, property, value) {
    if (!node) return;
    if (node.style[property] !== value) {
        node.style[property] = value;
    }
}

function getViewportSize() {
    return {
        width: window.innerWidth || document.documentElement.clientWidth || 1280,
        height: window.innerHeight || document.documentElement.clientHeight || 720,
    };
}

function getActiveModeConfig() {
    return AAC_MODES[currentMode] || AAC_MODES.patient;
}

function getActivePages() {
    return getActiveModeConfig().pages;
}

function normalizeToken(value) {
    return String(value || "")
        .trim()
        .toLowerCase()
        .replaceAll("’", "'")
        .replaceAll("`", "'")
        .replaceAll("ʻ", "'")
        .replaceAll("ʼ", "'");
}

function tokenizeText(text) {
    return String(text || "")
        .split(/\s+/)
        .map((part) => part.trim())
        .filter(Boolean);
}

function uniqueValues(values) {
    const seen = new Set();
    const result = [];
    for (const value of values) {
        const key = normalizeToken(value);
        if (!key || seen.has(key)) continue;
        seen.add(key);
        result.push(value);
    }
    return result;
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

    const activePages = getActivePages();
    const activePage = activePages[currentPage] || activePages[getActiveModeConfig().defaultPage];

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
    const rows = Math.ceil(((activePage?.tiles.length) || 0) / cols);
    const gridGap = getPx(gridStyles.rowGap || gridStyles.gap);
    const gridAvailableHeight = Math.max(180, boardAvailableHeight - boardShellVerticalPadding - boardHeadHeight - boardMainGap);
    const rawRowHeight = Math.floor((gridAvailableHeight - (gridGap * Math.max(0, rows - 1))) / Math.max(1, rows));
    const minRowHeight = viewportHeight < 760 ? 90 : 108;
    const clampedRowHeight = Math.max(minRowHeight, Math.min(220, rawRowHeight));
    const navGap = getPx(boardNavStyles.rowGap || boardNavStyles.gap);
    const navCount = Object.keys(activePages).length;
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
}

function openSessionModal() {
    closeOverlayWindows(false);
    sessionModal.classList.remove("hidden");
    sessionModal.setAttribute("aria-hidden", "false");
    document.body.classList.add("modal-open");
    setHeaderView("session");
}

function closeOverlayWindows(resetHeader = true) {
    sessionModal.classList.add("hidden");
    sessionModal.setAttribute("aria-hidden", "true");
    document.body.classList.remove("modal-open");
    if (resetHeader) {
        setHeaderView("board");
    }
}

function closeSessionModal() {
    closeOverlayWindows(true);
}

function setStatus(state, text) {
    const className = `status-badge status-${state}`;
    if (statusBadge.className !== className) {
        statusBadge.className = className;
    }
    setTextIfChanged(statusText, text);
}

function setMessageWords(words) {
    messageWords = tokenizeText(words.join(" ")).slice(0, MAX_MESSAGE_WORDS);
    updateMessageDisplay();
}

function getPredictionSuggestions() {
    const mode = getActiveModeConfig();
    const predictions = [];
    const normalizedWords = messageWords.map((word) => normalizeToken(word));
    const normalizedText = normalizedWords.join(" ");

    if (!normalizedText) {
        predictions.push(...mode.defaultPredictions);
    }

    const tailKeys = [];
    if (normalizedWords.length >= 2) {
        tailKeys.push(normalizedWords.slice(-2).join(" "));
    }
    if (normalizedWords.length >= 1) {
        tailKeys.push(normalizedWords.slice(-1).join(" "));
    }
    tailKeys.push("__start__");

    for (const key of tailKeys) {
        predictions.push(...(mode.predictionMap[key] || []));
    }

    const corpus = [
        ...mode.phraseBank,
        ...mode.quickReplies.map((item) => item.label),
        ...mode.emergencyActions.map((item) => item.label),
    ];
    for (const page of Object.values(mode.pages)) {
        corpus.push(...page.tiles.map((tile) => tile.label));
    }

    if (normalizedWords.length) {
        for (const phrase of corpus) {
            const phraseTokens = tokenizeText(phrase);
            const normalizedPhraseTokens = phraseTokens.map((token) => normalizeToken(token));
            const isPrefix = normalizedWords.every(
                (token, index) => normalizedPhraseTokens[index] === token,
            );
            if (!isPrefix) continue;
            if (normalizedPhraseTokens.length === normalizedWords.length) continue;

            const remainder = phraseTokens
                .slice(normalizedWords.length, normalizedWords.length + 2)
                .join(" ");
            if (remainder) {
                predictions.push(remainder);
            }
        }
    }

    const unique = uniqueValues(predictions)
        .filter((value) => normalizeToken(value) !== normalizeToken(messageWords.slice(-1)[0] || ""))
        .slice(0, 6);
    return unique;
}

function renderPredictionStrip() {
    const predictions = getPredictionSuggestions();
    predictionStrip.innerHTML = predictions.length
        ? predictions.map((item) => `
            <button
                class="predict-chip gaze-target"
                data-action="suggestion"
                data-text="${escapeHtml(item)}"
                data-label="${escapeHtml(item)}"
            >
                ${escapeHtml(item)}
            </button>
        `).join("")
        : '<span class="utility-empty">Prediction hozircha yo\'q</span>';
}

function renderQuickStrip() {
    const mode = getActiveModeConfig();
    quickStrip.innerHTML = mode.quickReplies.map((item) => `
        <button
            class="quick-chip quick-chip-${item.type || "phrase"} tone-${item.tone} gaze-target"
            data-action="phrase"
            data-text="${escapeHtml(item.label)}"
            data-label="${escapeHtml(item.label)}"
        >
            ${escapeHtml(item.label)}
        </button>
    `).join("");
}

function renderEmergencyStrip() {
    const mode = getActiveModeConfig();
    emergencyStrip.innerHTML = mode.emergencyActions.map((item) => `
        <button
            class="quick-chip quick-chip-emergency tone-${item.tone} gaze-target"
            data-action="emergency"
            data-text="${escapeHtml(item.label)}"
            data-label="${escapeHtml(item.label)}"
        >
            ${escapeHtml(item.label)}
        </button>
    `).join("");
}

function renderPhraseBank() {
    const mode = getActiveModeConfig();
    phraseCaption.textContent = mode.phraseCaption;
    phraseBank.innerHTML = mode.phraseBank.map((item) => `
        <button
            class="phrase-chip gaze-target"
            data-action="phrase"
            data-text="${escapeHtml(item)}"
            data-label="${escapeHtml(item)}"
        >
            ${escapeHtml(item)}
        </button>
    `).join("");
}

function renderModeSummary() {
    const mode = getActiveModeConfig();
    modeBadge.textContent = mode.name;
    modeSummary.textContent = mode.summary;
    btnToggleMode.textContent = mode.toggleLabel;
    btnToggleMode.dataset.label = mode.toggleLabel;
}

function renderSupportPanels() {
    renderModeSummary();
    renderPredictionStrip();
    renderQuickStrip();
    renderEmergencyStrip();
    renderPhraseBank();
}

function updateMessageDisplay() {
    setTextIfChanged(infoWords, String(messageWords.length));
    if (messageWords.length === 0) {
        messageDisplay.innerHTML = '<span class="message-placeholder">Tanlangan so\'zlar shu yerda yig\'iladi</span>';
        renderPredictionStrip();
        scheduleLayoutFit();
        return;
    }

    messageDisplay.innerHTML = messageWords
        .map((word) => `<span class="message-chip">${escapeHtml(word)}</span>`)
        .join("");
    renderPredictionStrip();
    scheduleLayoutFit();
}

function appendTokens(tokens, replace = false) {
    const words = tokenizeText(tokens.join(" "));
    if (!words.length) return;

    const nextWords = replace ? [] : [...messageWords];
    for (const word of words) {
        if (nextWords.length >= MAX_MESSAGE_WORDS) {
            showBanner("Matn uzunligi limiti to'ldi", 2);
            break;
        }
        nextWords.push(word);
    }
    setMessageWords(nextWords);
}

function appendWord(word) {
    const words = tokenizeText(word);
    if (!words.length) {
        return;
    }
    if (messageWords.length >= MAX_MESSAGE_WORDS) {
        showBanner("Matn uzunligi limiti to'ldi", 2);
        return;
    }
    appendTokens(words);
}

function appendPhrase(text, replace = false) {
    appendTokens(tokenizeText(text), replace);
}

function clearMessage() {
    setMessageWords([]);
}

function backspaceMessage() {
    if (messageWords.length === 0) return;
    setMessageWords(messageWords.slice(0, -1));
}

function speakText(text, { replaceMessage = false, banner = "Matn gapirtirilmoqda" } = {}) {
    const clean = String(text || "").trim();
    if (!clean) {
        showBanner("Avval so'z tanlang", 2);
        return;
    }

    if (replaceMessage) {
        setMessageWords(tokenizeText(clean));
    }

    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
            command: "speak_text",
            text: clean,
        }));
        showBanner(banner, 2);
        return;
    }

    if (!("speechSynthesis" in window)) {
        showBanner("TTS hozir mavjud emas", 3);
        return;
    }

    const utterance = new SpeechSynthesisUtterance(clean);
    utterance.lang = "uz-UZ";
    utterance.rate = 0.92;
    utterance.pitch = 1.0;

    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
    showBanner(banner, 2);
}

function speakMessage() {
    if (messageWords.length === 0) {
        showBanner("Avval so'z tanlang", 2);
        return;
    }
    speakText(messageWords.join(" "), { banner: "Matn gapirtirilmoqda" });
}

function renderBoardNav() {
    const pages = getActivePages();
    if (!pages[currentPage]) {
        currentPage = getActiveModeConfig().defaultPage;
    }
    boardNav.innerHTML = Object.entries(pages)
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
    const pages = getActivePages();
    if (!pages[currentPage]) {
        currentPage = getActiveModeConfig().defaultPage;
    }

    const page = pages[currentPage];
    if (!page) return;
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
    const pages = getActivePages();
    if (!pages[pageKey]) return;
    currentPage = pageKey;
    clearGazeSelection();
    renderBoardNav();
    renderBoardGrid();
    renderPredictionStrip();
}

function clearGazeSelection() {
    if (activeGazeTarget) {
        activeGazeTarget.classList.remove("gaze-active");
        activeGazeTarget.style.setProperty("--dwell-progress", "0%");
    }
    activeGazeTarget = null;
    activeGazeStartedAt = 0;
}

function pointHitsTarget(target, x, y, padding = 0) {
    if (!target || !target.isConnected) return false;
    if (target.disabled) return false;
    const rect = target.getBoundingClientRect();
    if (!rect.width || !rect.height) return false;
    return (
        x >= rect.left - padding
        && x <= rect.right + padding
        && y >= rect.top - padding
        && y <= rect.bottom + padding
    );
}

function getGazeTargetAt(x, y) {
    if (pointHitsTarget(activeGazeTarget, x, y, AAC_TARGET_STICKY_PX)) {
        return activeGazeTarget;
    }
    const target = document.elementFromPoint(x, y)?.closest(".gaze-target");
    if (!target) return null;
    if (target.disabled) return null;
    return target;
}

function performTargetAction(target, source = "manual") {
    const action = target.dataset.action;

    if (action === "word") {
        appendWord(target.dataset.word || target.dataset.label || "");
    } else if (action === "suggestion") {
        appendPhrase(target.dataset.text || target.dataset.label || "");
    } else if (action === "phrase") {
        appendPhrase(target.dataset.text || target.dataset.label || "");
    } else if (action === "emergency") {
        const text = target.dataset.text || target.dataset.label || "";
        speakText(text, {
            replaceMessage: true,
            banner: "Emergency signal yuborildi",
        });
    } else if (action === "page") {
        setPage(target.dataset.page);
    } else if (action === "toggle-mode") {
        currentMode = currentMode === "patient" ? "caregiver" : "patient";
        currentPage = getActiveModeConfig().defaultPage;
        clearGazeSelection();
        renderSupportPanels();
        renderBoardNav();
        renderBoardGrid();
        updateMessageDisplay();
        showBanner(`${getActiveModeConfig().name} ochildi`, 1.4);
    } else if (action === "open-session") {
        openSessionModal();
    } else if (action === "close-session") {
        closeSessionModal();
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
        setTextIfChanged(infoFocus, "—");
        clearGazeSelection();
        return;
    }

    setTextIfChanged(infoFocus, target.dataset.label || target.textContent.trim());

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
        sending = false;
        capturePending = false;
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

    if (data.fps !== undefined) {
        setTextIfChanged(fpsDisplay, `${data.fps} FPS`);
    }

    setTextIfChanged(infoFace, data.face_found ? "Topildi" : "Yo'q");
    setStyleIfChanged(infoFace, "color", data.face_found ? "var(--accent)" : "var(--danger)");

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

    setTextIfChanged(infoState, stateMap[data.state] || data.state || "—");

    if (data.state === "TRACKING") {
        setStatus("tracking", "Kuzatuv");
    } else if (data.state === "CALIBRATING") {
        setStatus("connected", "Kalibratsiya");
    } else {
        setStatus("connected", "Ulangan");
    }

    if (infoEmotion && data.emotion) {
        setTextIfChanged(infoEmotion, data.emotion);
    }

    if (data.zone) {
        setTextIfChanged(infoZone, data.zone.name || `Zona ${data.zone.idx}`);
    } else {
        setTextIfChanged(infoZone, "—");
    }

    if (data.gaze) {
        const [sx, sy] = data.gaze;
        setTextIfChanged(infoGaze, `${Math.round(sx)}, ${Math.round(sy)}`);

        const { width: viewportWidth, height: viewportHeight } = getViewportSize();
        const surfaceWidth = Math.max(1, Number(data.surface?.w) || viewportWidth);
        const surfaceHeight = Math.max(1, Number(data.surface?.h) || viewportHeight);
        const viewportX = Math.max(
            0,
            Math.min(viewportWidth - 1, (sx / surfaceWidth) * viewportWidth),
        );
        const viewportY = Math.max(
            0,
            Math.min(viewportHeight - 1, (sy / surfaceHeight) * viewportHeight),
        );

        setStyleIfChanged(gazeDot, "left", `${viewportX}px`);
        setStyleIfChanged(gazeDot, "top", `${viewportY}px`);
        gazeDot.classList.remove("hidden");

        if (data.state === "TRACKING") {
            updateGazeSelection(viewportX, viewportY);
        } else {
            clearGazeSelection();
        }
    } else {
        setTextIfChanged(infoGaze, "—");
        gazeDot.classList.add("hidden");
        clearGazeSelection();
    }

    if (data.calibration) {
        const calibration = data.calibration;

            if (calibration.active) {
                calibrating = true;
                calibOverlay.classList.remove("hidden");
                setTextIfChanged(infoCalib, `${calibration.current}/${calibration.total}`);
                drawCalibrationPoint(calibration, data.surface);
            } else {
            if (calibrating) {
                calibrating = false;
                calibOverlay.classList.add("hidden");
                if (calibration.done) {
                    showBanner("Kalibratsiya muvaffaqiyatli tugadi", 3);
                    btnRecalibrate.disabled = false;
                }
            }

            setTextIfChanged(infoCalib, calibration.done ? "Ha" : "Yo'q");
        }

        if (calibration.error) {
            showBanner(calibration.error, 3);
        }
    }

    sending = false;
}

function drawCalibrationPoint(calibration, surface) {
    const { width, height } = getViewportSize();
    calibCanvas.width = width;
    calibCanvas.height = height;

    calibCtx.clearRect(0, 0, width, height);
    calibCtx.fillStyle = "rgba(0, 0, 0, 0.88)";
    calibCtx.fillRect(0, 0, width, height);

    if (!calibration.point) return;

    const surfaceWidth = Math.max(1, Number(surface?.w) || width);
    const surfaceHeight = Math.max(1, Number(surface?.h) || height);
    const px = (calibration.point.x / surfaceWidth) * width;
    const py = (calibration.point.y / surfaceHeight) * height;
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
        captureCanvas.width = CAPTURE_WIDTH;
        captureCanvas.height = CAPTURE_HEIGHT;
        captureCtx = captureCanvas.getContext("2d", {
            alpha: false,
            desynchronized: true,
        }) || captureCanvas.getContext("2d");

        cameraReady = true;
        sending = false;
        capturePending = false;
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
    if (
        !cameraReady
        || !ws
        || ws.readyState !== WebSocket.OPEN
        || sending
        || capturePending
        || document.hidden
    ) {
        return;
    }

    capturePending = true;
    captureCtx.drawImage(video, 0, 0, CAPTURE_WIDTH, CAPTURE_HEIGHT);
    captureCanvas.toBlob(
        (blob) => {
            capturePending = false;
            if (!blob || !ws || ws.readyState !== WebSocket.OPEN) {
                sending = false;
                return;
            }

            sending = true;
            blob.arrayBuffer()
                .then((buffer) => {
                    if (!ws || ws.readyState !== WebSocket.OPEN) {
                        sending = false;
                        return;
                    }
                    ws.send(buffer);
                })
                .catch((error) => {
                    sending = false;
                    console.error("Frame encode xatosi:", error);
                });
        },
        "image/jpeg",
        JPEG_QUALITY,
    );
}

function startCalibration() {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    const { width, height } = getViewportSize();

    ws.send(JSON.stringify({
        command: "start_calibration",
        screen_w: width,
        screen_h: height,
    }));

    calibrating = true;
    calibOverlay.classList.remove("hidden");
    showBanner("Kalibratsiya boshlandi", 2);
}

function syncScreenMetrics() {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    const { width, height } = getViewportSize();
    ws.send(JSON.stringify({
        command: "set_screen",
        screen_w: width,
        screen_h: height,
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
    if (sessionModal && !sessionModal.classList.contains("hidden") && event.key === "Escape") {
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

document.addEventListener("visibilitychange", () => {
    if (!document.hidden) return;
    clearGazeSelection();
    gazeDot.classList.add("hidden");
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

sessionModal?.addEventListener("click", (event) => {
    if (event.target.matches("[data-session-close]")) {
        closeSessionModal();
    }
});

setStatus("disconnected", "Kamerani oching");
currentPage = getActiveModeConfig().defaultPage;
setHeaderView("board");
renderSupportPanels();
updateMessageDisplay();
renderBoardNav();
renderBoardGrid();
window.addEventListener("load", syncLayoutFit);
document.fonts?.ready?.then(() => {
    syncLayoutFit();
});
