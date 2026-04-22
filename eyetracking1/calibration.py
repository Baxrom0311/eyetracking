import cv2
import json
import time
import numpy as np
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Tuple, Optional
from settings import (
    CALIB_FILE,
    CALIB_DWELL_SEC,
    CALIB_MAX_INVALID_SEC,
    CALIB_MAX_POINT_MEAN_ERR_RATIO,
    CALIB_MAX_RMSE_RATIO,
    CALIB_MIN_FILTERED_SAMPLES,
    CALIB_MIN_GAZE_SPAN_X,
    CALIB_MIN_GAZE_SPAN_Y,
    CALIB_MIN_POINTS_REQUIRED,
    CALIB_OUTLIER_Z,
    CALIB_PREVIEW_SCALE,
    CALIB_RIDGE_ALPHA,
    CALIB_SETTLE_SEC,
    CALIB_SACCADE_THRESHOLD,
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
    rmse_px: float = 0.0
    max_mean_error_px: float = 0.0
    screen_w: int = 0
    screen_h: int = 0
    point_count: int = 0
    sample_count: int = 0

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


def _build_calibration_points(sw: int, sh: int) -> List[CalibrationPoint]:
    """
    9 nuqta: 3x3 grid, 12%/88% marginlar.
    Tobii Pro / PyGaze standarti — to'liq ekran qamrovi va burchaklar.
    Middle-edge nuqtalar (top-center, left-center) interpolatsiya sifatini oshiradi.
    """
    margins = [0.12, 0.50, 0.88]
    positions = [(x, y) for y in margins for x in margins]
    return [CalibrationPoint(int(col * sw), int(row * sh)) for col, row in positions]


class CalibrationManager:
    """
    OpenCV window da 9 nuqta ko'rsatadi.
    Foydalanuvchi har nuqtaga CALIB_DWELL_SEC soniya qaraydi.
    Keyin Ridge regression model yasaydi.
    """

    def __init__(self, screen_w: int, screen_h: int):
        self.sw = screen_w
        self.sh = screen_h
        self._points  = _build_calibration_points(screen_w, screen_h)
        self._current = 0
        self._start_t = 0.0
        self._model   = None
        self.done     = False
        self.active   = False
        self._pause_t: Optional[float] = None

    # ── Kalibrasiyani boshlash ─────────────────────────────
    def start(self):
        self._current = 0
        self._start_t = time.time()
        self.active   = True
        self.done     = False
        self._model   = None
        self._pause_t = None
        for p in self._points:
            p.samples.clear()
        logger.info("Kalibrasiya boshlandi.")

    # ── Har frame da chaqiriladi ───────────────────────────
    def update(self, gaze_norm: Optional[Tuple[float, float]], is_blinking: bool = False) -> bool:
        """
        gaze_norm: (nx, ny) 0-1 oralig'ida.
        is_blinking: True bo'lsa sample tashlanadi (ko'z yumilgan).
        True qaytarsa → kalibrasiya tugadi.
        """
        if not self.active or self.done:
            return False

        now = time.time()
        pt = self._points[self._current]
        if gaze_norm is None:
            if self._pause_t is None:
                self._pause_t = now
            elif now - self._pause_t >= CALIB_MAX_INVALID_SEC:
                if pt.samples:
                    logger.info(
                        "Kalibrasiya nuqtasi %d uzoq uzildi, nuqta qayta boshlandi.",
                        self._current + 1,
                    )
                pt.samples.clear()
                self._start_t = now
                self._pause_t = None
            return False

        if self._pause_t is not None:
            self._start_t += now - self._pause_t
            self._pause_t = None

        elapsed = now - self._start_t

        # Settling period: dastlabki 0.5s da sample yig'maslik (saccade latency)
        if elapsed >= CALIB_SETTLE_SEC and not is_blinking:
            pt.samples.append(gaze_norm)

        if elapsed >= CALIB_DWELL_SEC:
            logger.info(f"Nuqta {self._current+1}/{len(self._points)} tayyor "
                        f"({len(pt.samples)} sample)")
            self._current += 1
            self._start_t = now
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
        now = self._pause_t if self._pause_t is not None else time.time()
        elapsed = now - self._start_t
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
        if self._pause_t is not None:
            cv2.putText(frame, "Signal vaqtincha yo'q, davom etishi uchun ko'z topilsin",
                        (20, 126),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.48, (120, 180, 255), 1)

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
        point_feature_sets = []
        for pt in self._points:
            if not pt.samples:
                continue
            arr = np.asarray(pt.samples, dtype=float)
            # 1-bosqich: saccade filtri (tez sakrashlarni olib tashlash)
            arr = self._filter_saccades(arr)
            # 2-bosqich: statistik outlier filtri (MAD)
            filtered = self._filter_outliers(arr)
            if filtered.shape[0] < CALIB_MIN_FILTERED_SAMPLES:
                logger.warning(
                    "Nuqta (%d, %d) uchun filterdan keyin sample kam qoldi: %d/%d. Xom sample ishlatildi.",
                    pt.screen_x,
                    pt.screen_y,
                    filtered.shape[0],
                    arr.shape[0],
                )
                filtered = arr
            elif filtered.shape[0] != arr.shape[0]:
                logger.info(
                    "Nuqta (%d, %d) outlier filtri: %d → %d sample",
                    pt.screen_x,
                    pt.screen_y,
                    arr.shape[0],
                    filtered.shape[0],
                )
            arr = filtered
            mx, my = arr.mean(axis=0)
            point_means.append([mx, my])
            point_x = []
            point_y = []
            for nx, ny in arr:
                feat = [nx, ny, nx**2, ny**2, nx * ny]
                target = [pt.screen_x, pt.screen_y]
                X.append(feat)
                Y.append(target)
                point_x.append(feat)
                point_y.append(target)
            point_feature_sets.append(
                (
                    np.asarray(point_x, dtype=float),
                    np.asarray(point_y, dtype=float),
                )
            )

        X, Y = np.array(X, dtype=float), np.array(Y, dtype=float)
        if len(X) < 3:
            raise RuntimeError("Kalibrasiya uchun yetarli sample yig'ilmadi.")
        if len(point_means) < CALIB_MIN_POINTS_REQUIRED:
            raise RuntimeError(
                f"Kalibrasiya uchun yetarli nuqta yig'ilmadi: {len(point_means)}/{len(self._points)}."
            )
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
        pred = model.predict(X)
        sample_errors = np.linalg.norm(pred - Y, axis=1)
        rmse_px = float(np.sqrt(np.mean(sample_errors**2))) if len(sample_errors) else 0.0
        point_mean_errors = []
        for point_x, point_y in point_feature_sets:
            point_pred = model.predict(point_x)
            point_errors = np.linalg.norm(point_pred - point_y, axis=1)
            point_mean_errors.append(float(np.mean(point_errors)))
        max_point_mean_error = max(point_mean_errors or [0.0])

        max_rmse_px = min(self.sw, self.sh) * CALIB_MAX_RMSE_RATIO
        max_point_err_px = min(self.sw, self.sh) * CALIB_MAX_POINT_MEAN_ERR_RATIO
        if rmse_px > max_rmse_px or max_point_mean_error > max_point_err_px:
            raise RuntimeError(
                "Kalibrasiya sifati past. "
                f"RMSE={rmse_px:.1f}px, point_mean_max={max_point_mean_error:.1f}px"
            )

        model.rmse_px = rmse_px
        model.max_mean_error_px = max_point_mean_error
        model.screen_w = self.sw
        model.screen_h = self.sh
        model.point_count = len(point_means)
        model.sample_count = int(len(X))
        self._model = model

        # Saqlash
        try:
            coef  = model.coef_.tolist()
            inter = model.intercept_.tolist()
            calib_path = Path(CALIB_FILE)
            calib_path.parent.mkdir(parents=True, exist_ok=True)
            with calib_path.open("w", encoding="utf-8") as f:
                json.dump(
                    {
                        "coef": coef,
                        "intercept": inter,
                        "alpha": model.alpha,
                        "screen_w": self.sw,
                        "screen_h": self.sh,
                        "rmse_px": model.rmse_px,
                        "max_mean_error_px": model.max_mean_error_px,
                        "point_count": model.point_count,
                        "sample_count": model.sample_count,
                    },
                    f,
                )
            logger.info("Kalibrasiya saqlandi: %s", calib_path)
        except Exception as e:
            logger.warning(f"Kalibrasiya saqlanmadi: {e}")

    @staticmethod
    def _filter_saccades(samples: np.ndarray) -> np.ndarray:
        """
        Frame-to-frame tez sakrashlarni (saccade) olib tashlaydi.
        Agar ketma-ket ikkita sample orasidagi masofa > CALIB_SACCADE_THRESHOLD bo'lsa,
        ikkinchi sample tashlanadi.
        """
        if samples.ndim != 2 or samples.shape[0] < 3:
            return samples
        diffs = np.linalg.norm(np.diff(samples, axis=0), axis=1)
        # Birinchi sample har doim saqlanadi, keyingilari faqat masofa past bo'lsa
        keep = np.ones(samples.shape[0], dtype=bool)
        keep[1:] = diffs <= CALIB_SACCADE_THRESHOLD
        filtered = samples[keep]
        if filtered.shape[0] < 3:
            return samples  # juda kam qolsa, xom holatda qaytarish
        return filtered

    @staticmethod
    def _filter_outliers(samples: np.ndarray) -> np.ndarray:
        """
        Har bir calibration nuqtasi ichida keskin chalg'igan gaze sample larni olib tashlaydi.
        Modified z-score MAD asosida ishlaydi; sample juda kam bo'lsa xom holatda qaytaradi.
        """
        if samples.ndim != 2 or samples.shape[0] < CALIB_MIN_FILTERED_SAMPLES:
            return samples

        median = np.median(samples, axis=0)
        abs_dev = np.abs(samples - median)
        mad = np.median(abs_dev, axis=0)
        mad = np.where(mad < 1e-6, 1e-6, mad)
        modified_z = 0.6745 * abs_dev / mad
        keep_mask = np.all(modified_z <= CALIB_OUTLIER_Z, axis=1)

        if not np.any(keep_mask):
            return samples
        return samples[keep_mask]

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
        now = self._pause_t if self._pause_t is not None else time.time()
        elapsed = now - self._start_t
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
    def load_saved(
        expected_screen_w: Optional[int] = None,
        expected_screen_h: Optional[int] = None,
    ) -> Optional[object]:
        try:
            with Path(CALIB_FILE).open(encoding="utf-8") as f:
                data = json.load(f)
            saved_screen_w = data.get("screen_w")
            saved_screen_h = data.get("screen_h")
            legacy_without_screen = False
            if saved_screen_w is not None and saved_screen_h is not None:
                saved_screen_w = int(saved_screen_w)
                saved_screen_h = int(saved_screen_h)
            else:
                legacy_without_screen = True
                logger.info(
                    "Saqlangan kalibrasiya legacy formatda. Ekran metadata yo'q, "
                    "ehtiyotkorlik bilan yuklanmoqda."
                )

            if (
                not legacy_without_screen
                and expected_screen_w is not None
                and expected_screen_h is not None
            ):
                expected_screen_w = int(expected_screen_w)
                expected_screen_h = int(expected_screen_h)
                if (
                    saved_screen_w != expected_screen_w
                    or saved_screen_h != expected_screen_h
                ):
                    logger.info(
                        "Saqlangan kalibrasiya boshqa ekran uchun: %dx%d, hozir %dx%d.",
                        saved_screen_w,
                        saved_screen_h,
                        expected_screen_w,
                        expected_screen_h,
                    )
                    return None

            model = RidgeCalibrationModel(alpha=float(data.get("alpha", CALIB_RIDGE_ALPHA)))
            model.coef_      = np.array(data["coef"], dtype=float)
            model.intercept_ = np.array(
                data.get("intercept", data.get("inter", [0.0, 0.0])),
                dtype=float,
            )
            model.rmse_px = float(data.get("rmse_px", 0.0))
            model.max_mean_error_px = float(data.get("max_mean_error_px", 0.0))
            model.screen_w = int(saved_screen_w or expected_screen_w or 0)
            model.screen_h = int(saved_screen_h or expected_screen_h or 0)
            model.point_count = int(data.get("point_count", 0))
            model.sample_count = int(data.get("sample_count", 0))
            logger.info("Saqlangan kalibrasiya yuklandi.")
            return model
        except Exception:
            return None
