import cv2
import json
import time
import numpy as np
import logging
from dataclasses import dataclass, field
from typing import List, Tuple, Optional
from settings import (
    CALIB_FILE,
    CALIB_DWELL_SEC,
    CALIB_MIN_GAZE_SPAN_X,
    CALIB_MIN_GAZE_SPAN_Y,
    CALIB_POINTS,
    CALIB_PREVIEW_SCALE,
    CALIB_RIDGE_ALPHA,
    OVERLAY_CURSOR_COLOR,
)

logger = logging.getLogger(__name__)


class CalibrationPoint:
    def __init__(self, screen_x: int, screen_y: int):
        self.screen_x = screen_x
        self.screen_y = screen_y
        self.samples: List[Tuple[float, float]] = []   # iris normlari


@dataclass
class RidgeCalibrationModel:
    alpha: float = CALIB_RIDGE_ALPHA
    coef_: np.ndarray = field(default_factory=lambda: np.zeros((2, 5), dtype=float))
    intercept_: np.ndarray = field(default_factory=lambda: np.zeros(2, dtype=float))

    def fit(self, x_data, y_data):
        x_data = np.asarray(x_data, dtype=float)
        y_data = np.asarray(y_data, dtype=float)
        design = np.hstack([x_data, np.ones((x_data.shape[0], 1), dtype=float)])
        reg = np.eye(design.shape[1], dtype=float) * self.alpha
        reg[-1, -1] = 0.0
        beta = np.linalg.pinv(design.T @ design + reg) @ design.T @ y_data
        self.coef_ = beta[:-1].T
        self.intercept_ = beta[-1]
        return self

    def predict(self, x_data):
        x_data = np.asarray(x_data, dtype=float)
        return x_data @ self.coef_.T + self.intercept_


def _build_9_points(sw: int, sh: int) -> List[CalibrationPoint]:
    """3x3 grid — 9 nuqta. Haqiqiy chekkalarga qarash qiyin bo'lgani uchun sal ichkariroqdan olinadi."""
    pts = []
    # Nuqtalarni ekran chetidan biroz ichkariga suramiz x(15%), y(15%)
    for row in [0.15, 0.5, 0.85]:
        for col in [0.15, 0.5, 0.85]:
            pts.append(CalibrationPoint(int(col * sw), int(row * sh)))
    return pts


class CalibrationManager:
    """
    OpenCV window da 9 nuqta ko'rsatadi.
    Foydalanuvchi har nuqtaga CALIB_DWELL_SEC soniya qaraydi.
    Keyin Ridge regression model yasaydi.
    """

    def __init__(self, screen_w: int, screen_h: int):
        self.sw = screen_w
        self.sh = screen_h
        self._points  = _build_9_points(screen_w, screen_h)
        self._current = 0
        self._start_t = 0.0
        self._model   = None
        self.done     = False
        self.active   = False

    # ── Kalibrasiyani boshlash ─────────────────────────────
    def start(self):
        self._current = 0
        self._start_t = time.time()
        self.active   = True
        self.done     = False
        self._model   = None
        for p in self._points:
            p.samples.clear()
        logger.info("Kalibrasiya boshlandi.")

    # ── Har frame da chaqiriladi ───────────────────────────
    def update(self, gaze_norm: Optional[Tuple[float, float]]) -> bool:
        """
        gaze_norm: (nx, ny) 0-1 oralig'ida.
        True qaytarsa → kalibrasiya tugadi.
        """
        if not self.active or self.done:
            return False

        pt = self._points[self._current]
        if gaze_norm is None:
            pt.samples.clear()
            self._start_t = time.time()
            return False

        elapsed = time.time() - self._start_t
        pt.samples.append(gaze_norm)

        if elapsed >= CALIB_DWELL_SEC:
            logger.info(f"Nuqta {self._current+1}/{len(self._points)} tayyor "
                        f"({len(pt.samples)} sample)")
            self._current += 1
            self._start_t = time.time()
            if self._current >= len(self._points):
                try:
                    self._fit()
                    self.active = False
                    self.done   = True
                    return True
                except Exception as e:
                    self.active = False
                    self.done = False
                    self._model = None
                    logger.error(f"Kalibrasiya modeli yasalmadi: {e}")
                    return False
        return False

    # ── Overlay chizish ───────────────────────────────────
    def draw(self, frame: np.ndarray, preview: Optional[np.ndarray] = None) -> np.ndarray:
        if not self.active:
            return frame

        pt      = self._points[self._current]
        elapsed = time.time() - self._start_t
        ratio   = min(1.0, elapsed / CALIB_DWELL_SEC)

        # Qora fon overlay
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (frame.shape[1], frame.shape[0]),
                      (0, 0, 0), -1)
        frame = cv2.addWeighted(overlay, 0.55, frame, 0.45, 0)

        for idx, point in enumerate(self._points):
            px = int(point.screen_x / self.sw * frame.shape[1])
            py = int(point.screen_y / self.sh * frame.shape[0])
            if idx < self._current:
                cv2.circle(frame, (px, py), 7, (120, 120, 120), -1)
            elif idx > self._current:
                cv2.circle(frame, (px, py), 7, (80, 80, 80), 1)

        # Nuqtani kamera koordinatiga o'tkazish
        # (kamera oynasi to'liq ekran emas, shunchaki overlay uchun)
        cx = int(pt.screen_x / self.sw * frame.shape[1])
        cy = int(pt.screen_y / self.sh * frame.shape[0])

        # Tashqi doira (progress)
        radius = 28
        angle  = int(360 * ratio)
        cv2.ellipse(frame, (cx, cy), (radius, radius), -90,
                    0, angle, (0, 220, 120), 3)
        cv2.circle(frame, (cx, cy), 8, (0, 220, 120), -1)
        cv2.circle(frame, (cx, cy), 3, (255, 255, 255), -1)

        # Matn
        msg = f"Shu nuqtaga qarang  {self._current+1}/{len(self._points)}"
        cv2.putText(frame, msg, (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        hint = "Ko'zingizni qimirlatmang, faqat nuqtaga qarang"
        cv2.putText(frame, hint, (20, 70),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)
        cv2.putText(frame, f"Sample: {len(pt.samples)}", (20, 100),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 220, 180), 1)

        if preview is not None:
            inset_w = max(200, int(frame.shape[1] * CALIB_PREVIEW_SCALE))
            inset_h = int(preview.shape[0] / preview.shape[1] * inset_w)
            inset = cv2.resize(preview, (inset_w, inset_h))
            y0 = frame.shape[0] - inset_h - 28
            x0 = frame.shape[1] - inset_w - 28
            frame[y0:y0+inset_h, x0:x0+inset_w] = inset
            cv2.rectangle(frame, (x0, y0), (x0 + inset_w, y0 + inset_h), (255, 255, 255), 2)
            cv2.putText(frame, "Camera preview", (x0, y0 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 220, 220), 1)
        return frame

    # ── Model yasash ──────────────────────────────────────
    def _fit(self):
        X, Y = [], []
        point_means = []
        for pt in self._points:
            if not pt.samples:
                continue
            arr = np.asarray(pt.samples, dtype=float)
            mx, my = arr.mean(axis=0)
            point_means.append([mx, my])
            for nx, ny in arr:
                X.append([nx, ny, nx**2, ny**2, nx * ny])
                Y.append([pt.screen_x, pt.screen_y])

        X, Y = np.array(X, dtype=float), np.array(Y, dtype=float)
        if len(X) < 3:
            raise RuntimeError("Kalibrasiya uchun yetarli sample yig'ilmadi.")
        if point_means:
            span_x, span_y = np.ptp(np.asarray(point_means, dtype=float), axis=0)
            logger.info(
                "Kalibrasiya gaze span: nx=%.3f ny=%.3f",
                span_x,
                span_y,
            )
            if span_x < CALIB_MIN_GAZE_SPAN_X or span_y < CALIB_MIN_GAZE_SPAN_Y:
                logger.warning(
                    "Gaze signali tor: nx=%.3f ny=%.3f. Kamera va monitor "
                    "balandligini bir tekisroq qiling.",
                    span_x,
                    span_y,
                )
        model = RidgeCalibrationModel(alpha=CALIB_RIDGE_ALPHA)
        model.fit(X, Y)
        self._model = model

        # Saqlash
        try:
            coef  = model.coef_.tolist()
            inter = model.intercept_.tolist()
            with open(CALIB_FILE, "w") as f:
                json.dump(
                    {
                        "coef": coef,
                        "intercept": inter,
                        "alpha": model.alpha,
                    },
                    f,
                )
            logger.info(f"Kalibrasiya saqlandi: {CALIB_FILE}")
        except Exception as e:
            logger.warning(f"Kalibrasiya saqlanmadi: {e}")

    # ── Web API yordamchi metodlari ─────────────────────────
    def current_point(self) -> Optional[CalibrationPoint]:
        """Hozirgi kalibratsiya nuqtasini qaytarish."""
        if not self.active or self._current >= len(self._points):
            return None
        return self._points[self._current]

    def current_progress(self) -> float:
        """Hozirgi nuqtadagi progress (0.0-1.0)."""
        if not self.active:
            return 0.0
        elapsed = time.time() - self._start_t
        return min(1.0, elapsed / CALIB_DWELL_SEC)

    def current_index(self) -> int:
        """Hozirgi nuqta indeksi."""
        return self._current

    def total_points(self) -> int:
        """Jami nuqtalar soni."""
        return len(self._points)

    # ── Model olish ───────────────────────────────────────
    def get_model(self):
        return self._model

    # ── Saqlanganni yuklash ───────────────────────────────
    @staticmethod
    def load_saved() -> Optional[object]:
        try:
            with open(CALIB_FILE) as f:
                data = json.load(f)
            model = RidgeCalibrationModel(alpha=float(data.get("alpha", CALIB_RIDGE_ALPHA)))
            model.coef_      = np.array(data["coef"], dtype=float)
            model.intercept_ = np.array(data["intercept"], dtype=float)
            logger.info("Saqlangan kalibrasiya yuklandi.")
            return model
        except Exception:
            return None
