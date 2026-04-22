import os

from app_paths import (
    CALIBRATION_FILE,
    TTS_CACHE_PATH,
    USER_FACE_LANDMARKER_MODEL,
    BUNDLED_FACE_LANDMARKER_MODEL,
    ensure_runtime_dirs,
    resolve_face_landmarker_model,
)

ensure_runtime_dirs()


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


# ── Kamera ──────────────────────────────────────────────
CAMERA_INDEX        = 0        # 0 = birinchi (laptop) kamera
CAMERA_WIDTH        = 320      # 320x240 MediaPipe uchun yetarli, 4x kam piksel
CAMERA_HEIGHT       = 240
CAMERA_FPS          = 30
LOW_LIGHT_THRESHOLD = 40       # brightness 0-255, shundan past = LOW_LIGHT
CAMERA_READ_FAIL_LIMIT = 30    # ketma-ket bo'sh frame bo'lsa kamera xatosi
PREVIEW_MIRROR      = True

# ── MediaPipe ───────────────────────────────────────────
MP_MAX_FACES        = 1
MP_MIN_DETECT_CONF  = 0.5      # 0.7→0.5: bosh buralganda ham yuzni topadi
MP_MIN_TRACK_CONF   = 0.5      # 0.7→0.5: tracking uzilmasligi uchun
MP_REFINE_LANDMARKS = True     # iris uchun majburiy
FACE_LANDMARKER_BUNDLED_MODEL = str(BUNDLED_FACE_LANDMARKER_MODEL)
FACE_LANDMARKER_USER_MODEL = str(USER_FACE_LANDMARKER_MODEL)
FACE_LANDMARKER_MODEL = str(resolve_face_landmarker_model())
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
HEAD_AWAY_THRESHOLD  = 0.32   # 0.22→0.32: bosh burilishiga tolerantroq
HEAD_AWAY_EXIT_THRESHOLD = 0.22 # 0.14→0.22: hysteresis zona kengroq
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
MOVE_THRESHOLD_PX    = 4      # Jitter filtri
GAZE_X_SENSITIVITY   = 1.4    # Iris gaze uchun (gibrid modelda kamroq kerak)
GAZE_Y_SENSITIVITY   = 1.6    # Iris gaze uchun (gibrid modelda kamroq kerak)
LINEAR_GAZE_X_MIN    = 0.20   # kalibrasiyasiz fallback diapazon
LINEAR_GAZE_X_MAX    = 0.80
LINEAR_GAZE_Y_MIN    = 0.20
LINEAR_GAZE_Y_MAX    = 0.80

# ── Kalibrasiya ─────────────────────────────────────────
CALIB_POINTS         = 9      # 3x3 grid — to'liq ekran qamrovi (Tobii/PyGaze standarti)
CALIB_DWELL_SEC      = 2.0    # Har bir nuqtaga 2 sek (0.5s settle + 1.2s yig'ish + 0.3s o'tish)
CALIB_SETTLE_SEC     = 0.5    # Nuqta paydo bo'lganda dastlabki 0.5s ni tashlab yuborish (saccade latency)
CALIB_FILE           = os.getenv("GAZESPEAK_CALIB_FILE", str(CALIBRATION_FILE))
CALIB_PREVIEW_SCALE  = 0.22
CALIB_RIDGE_ALPHA    = 0.02   # 0.05→0.02: 9 nuqtada regularizatsiya kamroq kerak (PMC10966887)
CALIB_MIN_GAZE_SPAN_X = 0.06
CALIB_MIN_GAZE_SPAN_Y = 0.04
CALIB_OUTLIER_Z      = 2.5    # per-point modified z-score threshold (MAD)
CALIB_SACCADE_THRESHOLD = 0.05  # frame-to-frame gaze jump > 5% = saccade, tashlanadi
CALIB_MIN_FILTERED_SAMPLES = 8
CALIB_MAX_INVALID_SEC = 0.8
CALIB_MIN_POINTS_REQUIRED = 7   # 4→7: 9 nuqtadan kamida 7 tasi kerak
CALIB_MAX_RMSE_RATIO = 0.08    # 0.10→0.08: sifat talabi qattiqroq
CALIB_MAX_POINT_MEAN_ERR_RATIO = 0.12  # 0.14→0.12: nuqta xatosi chegarasi qattiqroq

# ── TTS ─────────────────────────────────────────────────
TTS_RATE             = 150    # So'z/daqiqa
TTS_VOLUME           = 1.0    # 0.0 - 1.0
TTS_LANGUAGE         = "uz"   # uz, ru, en
TTS_ENABLED          = _env_bool("GAZESPEAK_TTS_ENABLED", True)
TTS_PROVIDER         = os.getenv("GAZESPEAK_TTS_PROVIDER", "edge").strip().lower()
TTS_EDGE_VOICE       = os.getenv("GAZESPEAK_TTS_EDGE_VOICE", "uz-UZ-MadinaNeural")
TTS_EDGE_RATE        = os.getenv("GAZESPEAK_TTS_EDGE_RATE", "-5%")
TTS_EDGE_VOLUME      = os.getenv("GAZESPEAK_TTS_EDGE_VOLUME", "+0%")
TTS_CACHE_DIR        = os.getenv(
    "GAZESPEAK_TTS_CACHE_DIR",
    str(TTS_CACHE_PATH),
)
