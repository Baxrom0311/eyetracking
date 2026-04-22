import os

from app_paths import APP_CACHE_DIR, ensure_runtime_dirs

ensure_runtime_dirs()
os.environ.setdefault("MPLCONFIGDIR", str(APP_CACHE_DIR))
os.environ.setdefault("XDG_CACHE_HOME", str(APP_CACHE_DIR))

import cv2
import numpy as np
import mediapipe as mp
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Tuple
from settings import (
    MP_MAX_FACES, MP_MIN_DETECT_CONF, MP_MIN_TRACK_CONF,
    FACE_LANDMARKER_MODEL, FACE_LANDMARKER_URL, LEFT_IRIS, RIGHT_IRIS,
    LEFT_EYE_TOP, LEFT_EYE_BOTTOM, LEFT_EYE_LEFT, LEFT_EYE_RIGHT,
    RIGHT_EYE_TOP, RIGHT_EYE_BOTTOM, RIGHT_EYE_LEFT, RIGHT_EYE_RIGHT,
    BLINK_EAR_THRESHOLD, BLINK_CONSEC_FRAMES, HEAD_AWAY_THRESHOLD,
    HEAD_AWAY_EXIT_THRESHOLD, HEAD_OFFSET_SMOOTHING_ALPHA,
    GAZE_X_SENSITIVITY, GAZE_Y_SENSITIVITY,
    DOUBLE_BLINK_MS, LONG_BLINK_MS,
    HEAD_MOVEMENT_WEIGHT, HEAD_YAW_SCALE, HEAD_PITCH_SCALE,
    HEAD_NEUTRAL_ADAPT_ALPHA, HEAD_POSE_MAX_OFFSET, HEAD_POSE_SMOOTHING,
)
import time

logger = logging.getLogger(__name__)


@dataclass
class IrisData:
    """Bir ko'z iris ma'lumotlari."""
    center: Tuple[float, float] = (0.0, 0.0)   # normallashgan (0-1)
    radius: float = 0.0
    found:  bool  = False


@dataclass
class FaceData:
    """Bir frame da yuzdan olingan barcha ma'lumotlar."""
    found:          bool      = False
    left_iris:      IrisData  = field(default_factory=IrisData)
    right_iris:     IrisData  = field(default_factory=IrisData)
    gaze_norm:      Tuple[float, float] = (0.5, 0.5)  # ekran uchun (0-1)
    left_ear:       float     = 1.0    # Eye Aspect Ratio
    right_ear:      float     = 1.0
    left_blink:     bool      = False
    right_blink:    bool      = False
    head_away:      bool      = False
    head_offset:    float     = 0.0
    head_yaw:       float     = 0.0    # bosh gorizontal burilishi (-1..1)
    head_pitch:     float     = 0.0    # bosh vertikal burilishi  (-1..1)
    emotion:        str       = "😐 Normal" # aniqlangan kayfiyat
    landmarks:      Optional[object] = None   # xom MediaPipe landmarks


class BlinkDetector:
    """
    EAR (Eye Aspect Ratio) asosida blink, double blink, long blink aniqlaydi.
    """
    def __init__(self):
        self._left_consec   = 0
        self._right_consec  = 0
        self._last_blink_t  = 0.0
        self._blink_count   = 0

        # Natijalar (bir frame uchun)
        self.single_blink   = False
        self.double_blink   = False
        self.long_blink     = False
        self._blink_start_t = 0.0
        self._in_blink      = False

    def update(self, left_ear: float, right_ear: float):
        self.single_blink = False
        self.double_blink = False
        self.long_blink   = False

        avg_ear = (left_ear + right_ear) / 2.0
        now = time.time() * 1000  # ms

        if avg_ear < BLINK_EAR_THRESHOLD:
            if not self._in_blink:
                self._in_blink      = True
                self._blink_start_t = now
            self._left_consec  += 1
            self._right_consec += 1
        else:
            if self._in_blink:
                duration = now - self._blink_start_t
                self._in_blink = False

                if duration >= LONG_BLINK_MS:
                    self.long_blink = True
                elif self._left_consec >= BLINK_CONSEC_FRAMES:
                    self.single_blink = True
                    # Double blink tekshirish
                    if now - self._last_blink_t < DOUBLE_BLINK_MS:
                        self.double_blink = True
                        self._blink_count = 0
                    else:
                        self._blink_count = 1
                    self._last_blink_t = now

            self._left_consec  = 0
            self._right_consec = 0


class FaceTracker:
    """
    MediaPipe Face Landmarker orqali yuz va iris kuzatadi.
    """

    def __init__(self, enable_blendshapes: bool = True):
        if not os.path.exists(FACE_LANDMARKER_MODEL):
            logger.info("Face Landmarker modeli topilmadi. Yuklab olinmoqda...")
            os.makedirs(os.path.dirname(FACE_LANDMARKER_MODEL), exist_ok=True)
            import urllib.request
            try:
                urllib.request.urlretrieve(FACE_LANDMARKER_URL, FACE_LANDMARKER_MODEL)
                logger.info("Model muvaffaqiyatli yuklab olindi.")
            except Exception as e:
                raise RuntimeError(
                    f"Modelni yuklab olishda xatolik: {e}. "
                    f"Iltimos, {FACE_LANDMARKER_URL} linkidan yuklab models/face_landmarker.task fayliga qo'ying."
                )
        BaseOptions = mp.tasks.BaseOptions
        FaceLandmarker = mp.tasks.vision.FaceLandmarker
        FaceLandmarkerOptions = mp.tasks.vision.FaceLandmarkerOptions
        RunningMode = mp.tasks.vision.RunningMode

        options = FaceLandmarkerOptions(
            base_options=BaseOptions(
                model_asset_path=FACE_LANDMARKER_MODEL,
                delegate=BaseOptions.Delegate.CPU,
            ),
            running_mode=RunningMode.VIDEO,
            num_faces=MP_MAX_FACES,
            min_face_detection_confidence=MP_MIN_DETECT_CONF,
            min_face_presence_confidence=MP_MIN_DETECT_CONF,
            min_tracking_confidence=MP_MIN_TRACK_CONF,
            output_face_blendshapes=enable_blendshapes,
        )
        self._face_landmarker = FaceLandmarker.create_from_options(options)
        self._enable_blendshapes = enable_blendshapes
        self._last_timestamp_ms = 0
        self._head_offset_smoothed = 0.0
        self._head_away_latched    = False
        self._smoothed_yaw         = 0.0
        self._smoothed_pitch       = 0.0
        self._neutral_yaw          = 0.0
        self._neutral_pitch        = 0.0
        self._neutral_ready        = False
        self.blink_detector        = BlinkDetector()
        logger.info("FaceTracker: MediaPipe Face Landmarker yuklandi.")

    def process(self, frame: np.ndarray) -> FaceData:
        """
        BGR frame ni qabul qiladi, FaceData qaytaradi.
        """
        data = FaceData()
        h, w = frame.shape[:2]
        timestamp_ms = max(time.time_ns() // 1_000_000, self._last_timestamp_ms + 1)
        self._last_timestamp_ms = timestamp_ms

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        results = self._face_landmarker.detect_for_video(mp_image, timestamp_ms)

        if not results.face_landmarks:
            self.blink_detector.update(1.0, 1.0)
            return data   # found=False

        lm = results.face_landmarks[0]
        data.found     = True
        data.landmarks = lm

        # ── Iris markazlari ───────────────────────────────
        data.left_iris  = self._iris_data(lm, LEFT_IRIS,  w, h)
        data.right_iris = self._iris_data(lm, RIGHT_IRIS, w, h)
        raw_head_offset = self._head_offset(lm)
        self._head_offset_smoothed = (
            HEAD_OFFSET_SMOOTHING_ALPHA * raw_head_offset
            + (1 - HEAD_OFFSET_SMOOTHING_ALPHA) * self._head_offset_smoothed
        )
        if self._head_away_latched:
            self._head_away_latched = (
                abs(self._head_offset_smoothed) >= HEAD_AWAY_EXIT_THRESHOLD
            )
        else:
            self._head_away_latched = (
                abs(self._head_offset_smoothed) >= HEAD_AWAY_THRESHOLD
            )
        data.head_offset = self._head_offset_smoothed
        data.head_away = self._head_away_latched

        # ── Head Pose (Yaw / Pitch) ───────────────────────
        raw_yaw, raw_pitch = self._head_yaw_pitch(lm)
        self._smoothed_yaw = (
            HEAD_POSE_SMOOTHING * raw_yaw
            + (1 - HEAD_POSE_SMOOTHING) * self._smoothed_yaw
        )
        self._smoothed_pitch = (
            HEAD_POSE_SMOOTHING * raw_pitch
            + (1 - HEAD_POSE_SMOOTHING) * self._smoothed_pitch
        )
        self._update_head_neutral(
            self._smoothed_yaw,
            self._smoothed_pitch,
            can_adapt=not data.head_away,
        )
        data.head_yaw = float(np.clip(self._smoothed_yaw - self._neutral_yaw, -1.0, 1.0))
        data.head_pitch = float(np.clip(self._smoothed_pitch - self._neutral_pitch, -1.0, 1.0))

        # ── Iris-ga asoslangan Gaze ──────────────────────
        gaze_candidates = []
        left_gaze = self._eye_relative_gaze(
            lm,
            data.left_iris,
            LEFT_EYE_LEFT,
            LEFT_EYE_RIGHT,
            LEFT_EYE_TOP,
            LEFT_EYE_BOTTOM,
        )
        if left_gaze is not None:
            gaze_candidates.append(left_gaze)
        right_gaze = self._eye_relative_gaze(
            lm,
            data.right_iris,
            RIGHT_EYE_LEFT,
            RIGHT_EYE_RIGHT,
            RIGHT_EYE_TOP,
            RIGHT_EYE_BOTTOM,
        )
        if right_gaze is not None:
            gaze_candidates.append(right_gaze)
        if gaze_candidates:
            iris_gx = float(np.mean([p[0] for p in gaze_candidates]))
            iris_gy = float(np.mean([p[1] for p in gaze_candidates]))
            # Iris sezgirligini qo'llash
            iris_gx, iris_gy = self._apply_gaze_sensitivity(iris_gx, iris_gy)

            # ── Gibrid: Iris + Head Pose birlashtirish ───
            # Head yaw/pitch ni neutral baseline ga nisbatan va cheklangan og'irlik bilan qo'shamiz.
            head_x_offset = float(
                np.clip(data.head_yaw * HEAD_YAW_SCALE, -HEAD_POSE_MAX_OFFSET, HEAD_POSE_MAX_OFFSET)
            )
            head_y_offset = float(
                np.clip(data.head_pitch * HEAD_PITCH_SCALE, -HEAD_POSE_MAX_OFFSET, HEAD_POSE_MAX_OFFSET)
            )
            head_gx = 0.5 - head_x_offset
            head_gy = 0.5 + head_y_offset
            hw = HEAD_MOVEMENT_WEIGHT
            gx = (iris_gx + head_gx * hw) / (1.0 + hw)
            gy = (iris_gy + head_gy * hw) / (1.0 + hw)
            data.gaze_norm = (
                float(np.clip(gx, 0.0, 1.0)),
                float(np.clip(gy, 0.0, 1.0)),
            )

        # ── EAR hisoblash ─────────────────────────────────
        data.left_ear  = self._ear(
            lm, LEFT_EYE_TOP, LEFT_EYE_BOTTOM, LEFT_EYE_LEFT, LEFT_EYE_RIGHT
        )
        data.right_ear = self._ear(
            lm, RIGHT_EYE_TOP, RIGHT_EYE_BOTTOM, RIGHT_EYE_LEFT, RIGHT_EYE_RIGHT
        )

        # ── Blink ─────────────────────────────────────────
        self.blink_detector.update(data.left_ear, data.right_ear)
        data.left_blink  = data.left_ear  < BLINK_EAR_THRESHOLD
        data.right_blink = data.right_ear < BLINK_EAR_THRESHOLD

        # ── Emotion (Kayfiyat) ────────────────────────────
        if self._enable_blendshapes and hasattr(results, 'face_blendshapes') and results.face_blendshapes:
            blends = {b.category_name: b.score for b in results.face_blendshapes[0]}
            smile = max(blends.get("mouthSmileLeft", 0.0), blends.get("mouthSmileRight", 0.0))
            frown = max(blends.get("browDownLeft", 0.0), blends.get("browDownRight", 0.0))
            surprise = blends.get("browInnerUp", 0.0)
            squint_l = blends.get("eyeSquintLeft", 0.0)
            squint_r = blends.get("eyeSquintRight", 0.0)

            if smile > 0.4:
                data.emotion = "😊 Xursand"
            elif surprise > 0.5:
                data.emotion = "😲 Hayron"
            elif frown > 0.5:
                data.emotion = "😠 Jiddiy"
            elif squint_l > 0.5 and squint_r < 0.3:
                data.emotion = "😉 Ko'z qisish (Chap)"
            elif squint_r > 0.5 and squint_l < 0.3:
                data.emotion = "😉 Ko'z qisish (O'ng)"
            else:
                data.emotion = "😐 Normal"

        return data

    # ── yordamchi metodlar ────────────────────────────────

    def _iris_data(self, lm, indices: List[int], w: int, h: int) -> IrisData:
        pts = np.array([[lm[i].x, lm[i].y] for i in indices])
        cx, cy = pts.mean(axis=0)
        # Radius: nuqtalar orasidagi o'rtacha masofa
        r = float(np.mean([
            np.linalg.norm(pts[i] - pts[(i+1) % len(pts)])
            for i in range(len(pts))
        ]))
        return IrisData(center=(float(cx), float(cy)), radius=r, found=True)

    def _ear(
        self,
        lm,
        top_idx: int,
        bot_idx: int,
        left_idx: int,
        right_idx: int,
    ) -> float:
        """
        Oddiy EAR: vertikal ko'z ochiqligi / gorizontal ko'z eni.
        """
        top = np.array([lm[top_idx].x, lm[top_idx].y])
        bot = np.array([lm[bot_idx].x, lm[bot_idx].y])
        left = np.array([lm[left_idx].x, lm[left_idx].y])
        right = np.array([lm[right_idx].x, lm[right_idx].y])
        horiz = float(np.linalg.norm(left - right))
        if horiz <= 1e-6:
            return 1.0
        vert = float(np.linalg.norm(top - bot))
        return vert / horiz

    def _eye_relative_gaze(
        self,
        lm,
        iris: IrisData,
        left_idx: int,
        right_idx: int,
        top_idx: int,
        bottom_idx: int,
    ) -> Optional[Tuple[float, float]]:
        if not iris.found:
            return None

        eye_left = float(lm[left_idx].x)
        eye_right = float(lm[right_idx].x)
        eye_top = float(lm[top_idx].y)
        eye_bottom = float(lm[bottom_idx].y)

        x_min, x_max = sorted((eye_left, eye_right))
        y_min, y_max = sorted((eye_top, eye_bottom))
        eye_w = x_max - x_min
        eye_h = y_max - y_min
        if eye_w <= 1e-6 or eye_h <= 1e-6:
            return None

        gx = (iris.center[0] - x_min) / eye_w
        gy = (iris.center[1] - y_min) / eye_h
        return (
            float(np.clip(gx, 0.0, 1.0)),
            float(np.clip(gy, 0.0, 1.0)),
        )

    def _apply_gaze_sensitivity(self, gx: float, gy: float) -> Tuple[float, float]:
        gx = 0.5 + (gx - 0.5) * GAZE_X_SENSITIVITY
        gy = 0.5 + (gy - 0.5) * GAZE_Y_SENSITIVITY
        return (
            float(np.clip(gx, 0.0, 1.0)),
            float(np.clip(gy, 0.0, 1.0)),
        )

    def _head_offset(self, lm) -> float:
        nose_x = float(lm[1].x)
        eye_center_x = (float(lm[LEFT_EYE_LEFT].x) + float(lm[RIGHT_EYE_RIGHT].x)) / 2.0
        eye_width = abs(float(lm[RIGHT_EYE_RIGHT].x) - float(lm[LEFT_EYE_LEFT].x))
        if eye_width <= 1e-6:
            return 0.0
        return (nose_x - eye_center_x) / eye_width

    def _head_yaw_pitch(self, lm) -> Tuple[float, float]:
        """
        Boshning gorizontal (yaw) va vertikal (pitch) burilishini hisoblaydi.
        Burunning ko'zlarga nisbatan joylashuvidan foydalaniladi.
        Natija: (-1..1) oralig'ida, 0 = to'g'ri qaraganida.
        """
        nose = np.array([float(lm[1].x), float(lm[1].y)])
        l_eye = np.array([float(lm[LEFT_EYE_LEFT].x), float(lm[LEFT_EYE_LEFT].y)])
        r_eye = np.array([float(lm[RIGHT_EYE_RIGHT].x), float(lm[RIGHT_EYE_RIGHT].y)])
        eye_center = (l_eye + r_eye) / 2.0
        eye_dist = float(np.linalg.norm(r_eye - l_eye))
        if eye_dist <= 1e-6:
            return 0.0, 0.0
        # Yaw: burunning gorizontal og'ishi ko'z orasidagi masofaga nisbatan
        yaw = float((nose[0] - eye_center[0]) / eye_dist)
        # Pitch: burunning vertikal og'ishi ko'z orasidagi masofaga nisbatan
        pitch = float((nose[1] - eye_center[1]) / eye_dist)
        return yaw, pitch

    def _update_head_neutral(self, yaw: float, pitch: float, can_adapt: bool) -> None:
        if not can_adapt:
            return
        if not self._neutral_ready:
            self._neutral_yaw = yaw
            self._neutral_pitch = pitch
            self._neutral_ready = True
            return

        if (
            abs(yaw - self._neutral_yaw) > HEAD_POSE_MAX_OFFSET * 2.0
            or abs(pitch - self._neutral_pitch) > HEAD_POSE_MAX_OFFSET * 2.0
        ):
            return

        alpha = HEAD_NEUTRAL_ADAPT_ALPHA
        self._neutral_yaw = alpha * yaw + (1 - alpha) * self._neutral_yaw
        self._neutral_pitch = alpha * pitch + (1 - alpha) * self._neutral_pitch

    def draw_debug(self, frame: np.ndarray, data: FaceData) -> np.ndarray:
        """
        Debug rejimda iris va landmarklarni chizadi.
        """
        if not data.found:
            return frame
        h, w = frame.shape[:2]
        for landmark in data.landmarks or []:
            x = int(landmark.x * w)
            y = int(landmark.y * h)
            cv2.circle(frame, (x, y), 1, (0, 180, 0), -1)
        for iris, color in [
            (data.left_iris,  (0, 255, 120)),
            (data.right_iris, (120, 255, 0)),
        ]:
            if iris.found:
                cx = int(iris.center[0] * w)
                cy = int(iris.center[1] * h)
                r  = max(2, int(iris.radius * w))
                cv2.circle(frame, (cx, cy), r,  color, 1)
                cv2.circle(frame, (cx, cy), 3,  color, -1)
        cv2.putText(
            frame,
            (
                f"EAR L:{data.left_ear:.2f} R:{data.right_ear:.2f}  "
                f"Head:{data.head_offset:+.2f}  "
                f"Gaze:{data.gaze_norm[0]:.2f},{data.gaze_norm[1]:.2f}"
            ),
            (12, h - 34),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 220, 120),
            1,
        )
        blink_text = []
        if self.blink_detector.single_blink:
            blink_text.append("blink")
        if self.blink_detector.double_blink:
            blink_text.append("double")
        if self.blink_detector.long_blink:
            blink_text.append("long")
        if blink_text:
            cv2.putText(
                frame,
                " / ".join(blink_text),
                (12, h - 12),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (0, 180, 255),
                2,
            )
        return frame

    def close(self):
        try:
            self._face_landmarker.close()
            logger.info("FaceTracker yopildi.")
        except Exception as e:
            logger.warning(f"FaceTracker yopilishida xato: {e}")
