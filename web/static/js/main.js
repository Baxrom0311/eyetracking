/**
 * GazeSpeak Web — Asosiy modul.
 * Barcha modullarni birlashtiradi va ilovani boshqaradi.
 */

// ── DOM elementlari ────────────────────────────────────
const $ = (s) => document.querySelector(s);
const video = $('#camera-video');
const overlayCanvas = $('#overlay-canvas');
const overlayCtx = overlayCanvas.getContext('2d');
const btnStartCam = $('#btn-start-camera');
const btnCalibrate = $('#btn-calibrate');
const btnRecalibrate = $('#btn-recalibrate');
const statusBadge = $('#status-badge');
const statusText = $('#status-text');
const fpsDisplay = $('#fps-display');
const infoState = $('#info-state');
const infoEmotion = $('#info-emotion');
const infoFace = $('#info-face');
const infoGaze = $('#info-gaze');
const infoZone = $('#info-zone');
const infoCalib = $('#info-calib');
const calibOverlay = $('#calibration-overlay');
const calibCanvas = $('#calibration-canvas');
const calibCtx = calibCanvas.getContext('2d');
const calibText = $('#calib-text');
const bannerEl = $('#banner');
const bannerText = $('#banner-text');
const gazeDot = $('#screen-gaze-dot');
const zoneCells = document.querySelectorAll('.zone-cell');

// ── Holat ──────────────────────────────────────────────
let ws = null;
let cameraReady = false;
let sending = false;
let captureCanvas = null;
let captureCtx = null;
let frameInterval = null;
let calibrating = false;
let bannerTimeout = null;

const TARGET_FPS = 15;
const JPEG_QUALITY = 0.65;

// ── Banner ─────────────────────────────────────────────
function showBanner(text, sec = 3) {
    bannerText.textContent = text;
    bannerEl.classList.remove('hidden');
    if (bannerTimeout) clearTimeout(bannerTimeout);
    bannerTimeout = setTimeout(() => {
        bannerEl.classList.add('hidden');
    }, sec * 1000);
}

// ── Status ─────────────────────────────────────────────
function setStatus(state, text) {
    statusBadge.className = 'status-badge status-' + state;
    statusText.textContent = text;
}

// ── WebSocket ──────────────────────────────────────────
function connectWS() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${location.host}/ws`);
    ws.binaryType = 'arraybuffer';

    ws.onopen = () => {
        setStatus('connected', 'Ulangan');
        showBanner('Server bilan ulandi ✓', 2);
        btnCalibrate.disabled = false;
    };

    ws.onclose = () => {
        setStatus('disconnected', 'Uzildi');
        ws = null;
        btnCalibrate.disabled = true;
        btnRecalibrate.disabled = true;
        gazeDot.classList.add('hidden');
        // Reconnect
        setTimeout(connectWS, 2000);
    };

    ws.onerror = () => {
        setStatus('disconnected', 'Xato');
    };

    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleServerMessage(data);
        } catch (e) {
            console.error('JSON parse xatosi:', e);
        }
    };
}

// ── Server xabarini qayta ishlash ──────────────────────
function handleServerMessage(data) {
    if (data.error) {
        console.warn('Server xatosi:', data.error);
        return;
    }
    if (data.status) return; // buyruq javobi

    // FPS
    if (data.fps !== undefined) {
        fpsDisplay.textContent = `${data.fps} FPS`;
    }

    // Face
    infoFace.textContent = data.face_found ? '✅ Topildi' : '❌ Yo\'q';
    infoFace.style.color = data.face_found ? 'var(--accent)' : 'var(--danger)';

    // State
    const stateMap = {
        'TRACKING': '🟢 Kuzatuv',
        'CALIBRATING': '🎯 Kalibratsiya',
        'CALIBRATION_DONE': '✅ Tayyor',
        'NO_FACE': '😶 Yuz yo\'q',
        'HEAD_AWAY': '↩️ Bosh chetda',
        'LOW_QUALITY': '⚠️ Past sifat',
        'IDLE': '⏸ Kutish',
    };
    infoState.textContent = stateMap[data.state] || data.state;

    if (data.state === 'TRACKING') {
        setStatus('tracking', 'Kuzatuv');
    } else if (data.state === 'CALIBRATING') {
        setStatus('connected', 'Kalibratsiya');
    } else {
        setStatus('connected', 'Ulangan');
    }

    // Emotion
    if (data.emotion) {
        infoEmotion.textContent = data.emotion;
    }

    // Gaze
    if (data.gaze) {
        const [sx, sy] = data.gaze;
        infoGaze.textContent = `${Math.round(sx)}, ${Math.round(sy)}`;

        // Screen gaze dot
        const scrW = window.screen.width || window.innerWidth;
        const scrH = window.screen.height || window.innerHeight;
        const pctX = (sx / scrW) * 100;
        const pctY = (sy / scrH) * 100;
        gazeDot.style.left = pctX + '%';
        gazeDot.style.top = pctY + '%';
        gazeDot.classList.remove('hidden');
    } else {
        infoGaze.textContent = '—';
        gazeDot.classList.add('hidden');
    }

    // Zone
    if (data.zone) {
        infoZone.textContent = data.zone.name || `Zona ${data.zone.idx}`;
        // Highlight zone cell
        zoneCells.forEach((cell) => {
            const idx = parseInt(cell.dataset.zone);
            cell.classList.remove('active', 'fired');
            if (idx === data.zone.idx) {
                cell.classList.add(data.zone.fired ? 'fired' : 'active');
            }
        });
        if (data.zone.fired && data.zone.message) {
            showBanner(`🎯 ${data.zone.message}`, 4);
        }
    } else {
        infoZone.textContent = '—';
        zoneCells.forEach((c) => c.classList.remove('active', 'fired'));
    }

    // Calibration
    if (data.calibration) {
        const cal = data.calibration;
        if (cal.active) {
            calibrating = true;
            calibOverlay.classList.remove('hidden');
            infoCalib.textContent = `${cal.current}/${cal.total}`;
            drawCalibrationPoint(cal);
        } else {
            if (calibrating) {
                calibrating = false;
                calibOverlay.classList.add('hidden');
                if (cal.done) {
                    showBanner('✅ Kalibratsiya muvaffaqiyatli!', 3);
                    btnRecalibrate.disabled = false;
                }
            }
            infoCalib.textContent = cal.done ? '✅ Ha' : '❌ Yo\'q';
        }
    }

    // Blink
    if (data.blink) {
        if (data.blink.double) showBanner('👆👆 Double blink', 1);
        else if (data.blink.long) showBanner('👆 Right click (uzun)', 1);
    }

    sending = false;
}

// ── Calibration nuqtasini chizish ──────────────────────
function drawCalibrationPoint(cal) {
    const cw = calibCanvas.width = window.innerWidth;
    const ch = calibCanvas.height = window.innerHeight;

    calibCtx.clearRect(0, 0, cw, ch);
    // Qora fon
    calibCtx.fillStyle = 'rgba(0, 0, 0, 0.85)';
    calibCtx.fillRect(0, 0, cw, ch);

    if (!cal.point) return;

    // Ekran koordinatalarini canvas ga moslashtirish
    const scrW = window.screen.width || cw;
    const scrH = window.screen.height || ch;
    const px = (cal.point.x / scrW) * cw;
    const py = (cal.point.y / scrH) * ch;

    // Progress doira
    const radius = 30;
    const startAngle = -Math.PI / 2;
    const endAngle = startAngle + (2 * Math.PI * cal.progress);

    // Orqa doira
    calibCtx.beginPath();
    calibCtx.arc(px, py, radius, 0, Math.PI * 2);
    calibCtx.strokeStyle = 'rgba(255, 255, 255, 0.15)';
    calibCtx.lineWidth = 3;
    calibCtx.stroke();

    // Progress
    calibCtx.beginPath();
    calibCtx.arc(px, py, radius, startAngle, endAngle);
    calibCtx.strokeStyle = '#10b981';
    calibCtx.lineWidth = 4;
    calibCtx.stroke();

    // Ichki nuqta
    calibCtx.beginPath();
    calibCtx.arc(px, py, 8, 0, Math.PI * 2);
    calibCtx.fillStyle = '#10b981';
    calibCtx.fill();

    // Oq markaz
    calibCtx.beginPath();
    calibCtx.arc(px, py, 3, 0, Math.PI * 2);
    calibCtx.fillStyle = '#fff';
    calibCtx.fill();

    // Matn
    calibCtx.fillStyle = '#fff';
    calibCtx.font = '600 18px Inter, sans-serif';
    calibCtx.textAlign = 'center';
    calibCtx.fillText(`Shu nuqtaga qarang ${cal.current}/${cal.total}`, cw / 2, 45);

    calibCtx.fillStyle = '#94a3b8';
    calibCtx.font = '400 14px Inter, sans-serif';
    calibCtx.fillText("Ko'zingizni qimirlatmang, faqat nuqtaga qarang", cw / 2, 72);

    calibText.textContent = `Nuqta ${cal.current}/${cal.total} — ${Math.round(cal.progress * 100)}%`;
}

// ── Kamera ─────────────────────────────────────────────
async function startCamera() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            video: {
                facingMode: 'user',
                width: { ideal: 640 },
                height: { ideal: 480 },
            },
            audio: false,
        });
        video.srcObject = stream;
        await video.play();

        // Capture canvas
        captureCanvas = document.createElement('canvas');
        captureCanvas.width = 640;
        captureCanvas.height = 480;
        captureCtx = captureCanvas.getContext('2d');

        cameraReady = true;
        btnStartCam.textContent = '📷 Kamera ishlayapti';
        btnStartCam.disabled = true;
        showBanner('Kamera ochildi ✓', 2);

        // WebSocket ulanish
        connectWS();

        // Frame jo'natish boshlanishi
        frameInterval = setInterval(sendFrame, 1000 / TARGET_FPS);
    } catch (err) {
        showBanner('❌ Kamera ruxsati berilmadi', 4);
        console.error('Camera error:', err);
    }
}

function sendFrame() {
    if (!cameraReady || !ws || ws.readyState !== WebSocket.OPEN || sending) return;

    captureCtx.drawImage(video, 0, 0, 640, 480);
    captureCanvas.toBlob(
        (blob) => {
            if (!blob || !ws || ws.readyState !== WebSocket.OPEN) return;
            sending = true;
            blob.arrayBuffer().then((buf) => {
                ws.send(buf);
            });
        },
        'image/jpeg',
        JPEG_QUALITY,
    );
}

// ── Kalibratsiya ───────────────────────────────────────
function startCalibration() {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify({
        command: 'start_calibration',
        screen_w: window.screen.width || window.innerWidth,
        screen_h: window.screen.height || window.innerHeight,
    }));
    calibrating = true;
    calibOverlay.classList.remove('hidden');
    showBanner('🎯 Kalibratsiya boshlandi...', 2);
}

// ── Event listeners ────────────────────────────────────
btnStartCam.addEventListener('click', startCamera);
btnCalibrate.addEventListener('click', startCalibration);
btnRecalibrate.addEventListener('click', () => {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ command: 'reset_calibration' }));
    }
    startCalibration();
});

// ESC — kalibratsiyadan chiqish
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && calibrating) {
        calibrating = false;
        calibOverlay.classList.add('hidden');
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ command: 'reset_calibration' }));
        }
    }
});

// ── Init ───────────────────────────────────────────────
setStatus('disconnected', 'Kamerani oching');
