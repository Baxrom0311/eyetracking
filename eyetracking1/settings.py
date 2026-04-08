import os


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_str(name: str, default: str) -> str:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip()
    return value or default

# ── Kamera ──────────────────────────────────────────────
CAMERA_INDEX        = 0        # 0 = birinchi (laptop) kamera
CAMERA_WIDTH        = 640
CAMERA_HEIGHT       = 480
CAMERA_FPS          = 30
LOW_LIGHT_THRESHOLD = 40       # brightness 0-255, shundan past = LOW_LIGHT
CAMERA_READ_FAIL_LIMIT = 30    # ketma-ket bo'sh frame bo'lsa kamera xatosi
PREVIEW_MIRROR      = True

# ── MediaPipe ───────────────────────────────────────────
MP_MAX_FACES        = 1
MP_MIN_DETECT_CONF  = 0.7
MP_MIN_TRACK_CONF   = 0.7
MP_REFINE_LANDMARKS = True     # iris uchun majburiy
FACE_LANDMARKER_MODEL = os.path.join(
    os.path.dirname(__file__), "models", "face_landmarker.task"
)
FACE_LANDMARKER_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task"

# Iris landmark indekslari (MediaPipe Face Mesh)
LEFT_IRIS   = [474, 475, 476, 477]
RIGHT_IRIS  = [469, 470, 471, 472]
# Blink uchun ko'z landmark indekslari (EAR)
LEFT_EYE_TOP    = 159
LEFT_EYE_BOTTOM = 145
LEFT_EYE_LEFT   = 33
LEFT_EYE_RIGHT  = 133
RIGHT_EYE_TOP   = 386
RIGHT_EYE_BOTTOM= 374
RIGHT_EYE_LEFT  = 362
RIGHT_EYE_RIGHT = 263

# ── Blink ───────────────────────────────────────────────
BLINK_EAR_THRESHOLD  = 0.20   # EAR ratio shundan past = ko'z yumilgan
BLINK_CONSEC_FRAMES  = 2      # necha ketma-ket frame = blink
DOUBLE_BLINK_MS      = 500    # ms ichida ikki blink = double blink (click)
LONG_BLINK_MS        = 800    # ms uzun blink = right click
NO_FACE_DELAY_SEC    = 0.5    # yuz yo'qolsa shuncha kutib NO_FACE ga o'tadi
HEAD_AWAY_THRESHOLD  = 0.22   # enter threshold
HEAD_AWAY_EXIT_THRESHOLD = 0.14
HEAD_AWAY_DELAY_SEC  = 0.6    # bosh chetga ketganda qisqa flickerlarni filtrlash
HEAD_OFFSET_SMOOTHING_ALPHA = 0.25

# ── Head Pose → Gaze Blend (gibrid model) ──────────────
HEAD_MOVEMENT_WEIGHT = 0.45   # Bosh harakati gaze ga ehtiyotkorroq ta'sir qiladi
HEAD_YAW_SCALE       = 0.40   # Yaw (gorizontal burilish) kuchaytirgich
HEAD_PITCH_SCALE     = 0.48   # Pitch (vertikal burilish) kuchaytirgich
HEAD_POSE_SMOOTHING  = 0.25   # Head pose uchun alohida smoothing (0=sekin, 1=xom)
HEAD_NEUTRAL_ADAPT_ALPHA = 0.04
HEAD_POSE_MAX_OFFSET = 0.18

# ── Gaze / Cursor ───────────────────────────────────────
SMOOTHING_ALPHA      = 0.35   # Exponential smoothing (kattaroq = tezroq)
CURSOR_SPEED         = 1.0
MOVE_THRESHOLD_PX    = 4      # Jitter filtri
PYAUTOGUI_PAUSE      = 0.0
GAZE_X_SENSITIVITY   = 1.4    # Iris gaze uchun (gibrid modelda kamroq kerak)
GAZE_Y_SENSITIVITY   = 1.6    # Iris gaze uchun (gibrid modelda kamroq kerak)
LINEAR_GAZE_X_MIN    = 0.20   # kalibrasiyasiz fallback diapazon
LINEAR_GAZE_X_MAX    = 0.80
LINEAR_GAZE_Y_MIN    = 0.20
LINEAR_GAZE_Y_MAX    = 0.80

# ── Kalibrasiya ─────────────────────────────────────────
CALIB_POINTS         = 9      # 9 nuqta
CALIB_DWELL_SEC      = 3.0    # Diqqatni jamlash uchun ko'proq vaqt
CALIB_FILE           = os.path.join(os.path.dirname(__file__), "calibration.json")
CALIB_PREVIEW_SCALE  = 0.22
CALIB_RIDGE_ALPHA    = 0.05   # Alpha kattalashtirildi (model barqarorligi uchun)
CALIB_MIN_GAZE_SPAN_X = 0.06  # Ekstremal hollarni ham qabul qilish uchun kichraytirildi
CALIB_MIN_GAZE_SPAN_Y = 0.04
CALIB_OUTLIER_Z      = 2.5    # per-point modified z-score threshold
CALIB_MIN_FILTERED_SAMPLES = 8
CALIB_MAX_INVALID_SEC = 0.8
CALIB_MIN_POINTS_REQUIRED = 7
CALIB_MAX_RMSE_RATIO = 0.10
CALIB_MAX_POINT_MEAN_ERR_RATIO = 0.14

# ── Dwell click ─────────────────────────────────────────
DWELL_CLICK_MS       = 2600   # Faqat yetarlicha barqaror qaralganda click
DWELL_RADIUS_PX      = 32     # Radius kichikroq — accidental dwell kamroq
DWELL_SUPPRESS_AFTER_ACTION_SEC = 2.5
CURSOR_ENABLED_DEFAULT = _env_bool("GAZESPEAK_POINTER_ENABLED", False)

# ── Zona tahlili (10s dwell → xabar) ───────────────────
ZONE_DWELL_SEC       = 6      # AAC signal uchun tezroq, lekin tasodifiy emas
ZONE_COOLDOWN_SEC    = 30     # Trigger keyin shuncha sec kutiladi (spam oldini olish)

# Ekran 5 zonaga bo'linadi (nisbiy, 0.0-1.0)
# [x_min, y_min, x_max, y_max, nom, xabar_matni]
SCREEN_ZONES = [
    [0.0,  0.0,  0.5,  0.5,  "Yuqori chap",   "Foydalanuvchi ekranning yuqori chap qismiga qarayapti"],
    [0.5,  0.0,  1.0,  0.5,  "Yuqori o'ng",   "Foydalanuvchi ekranning yuqori o'ng qismiga qarayapti"],
    [0.0,  0.5,  0.5,  1.0,  "Pastki chap",   "Foydalanuvchi ekranning pastki chap qismiga qarayapti"],
    [0.5,  0.5,  1.0,  1.0,  "Pastki o'ng",   "Foydalanuvchi ekranning pastki o'ng qismiga qarayapti"],
    [0.35, 0.35, 0.65, 0.65, "Markaz",        "Foydalanuvchi ekran markaziga qarayapti"],
]

# ── TTS ─────────────────────────────────────────────────
TTS_RATE             = 150    # So'z/daqiqa
TTS_VOLUME           = 1.0    # 0.0 - 1.0
TTS_LANGUAGE         = "uz"   # uz, ru, en
TTS_ENABLED          = _env_bool("GAZESPEAK_TTS_ENABLED", True)

# ── Android WebSocket ───────────────────────────────────
ANDROID_WS_HOST      = _env_str("GAZESPEAK_ANDROID_WS_HOST", "127.0.0.1")
ANDROID_WS_PORT      = 8765
ANDROID_ENABLED      = _env_bool("GAZESPEAK_ANDROID_ENABLED", True)

# ── Web AAC Performance ─────────────────────────────────
WEB_ENABLE_EMOTION   = _env_bool("GAZESPEAK_WEB_ENABLE_EMOTION", False)
WEB_ENABLE_ZONE_ANALYSIS = _env_bool("GAZESPEAK_WEB_ENABLE_ZONE_ANALYSIS", False)

# ── Overlay UI ──────────────────────────────────────────
OVERLAY_WINDOW_NAME  = "GazeSpeak"
OVERLAY_SHOW_FPS     = True
OVERLAY_SHOW_ZONES   = True
OVERLAY_CURSOR_RADIUS= 12
OVERLAY_CURSOR_COLOR = (0, 220, 120)   # BGR yashil
OVERLAY_DWELL_COLOR  = (0, 180, 255)   # BGR sariq
OVERLAY_ERROR_COLOR  = (0, 60, 220)    # BGR qizil
OVERLAY_FONT_SCALE   = 0.55
ZONE_FIRED_BANNER_SEC = 3.0

# ── Debug ────────────────────────────────────────────────
DEBUG_MODE           = _env_bool("GAZESPEAK_DEBUG", True)
LOG_FILE             = "gazespeak.log"
LOG_MAX_BYTES        = 1_500_000
LOG_BACKUP_COUNT     = 3
