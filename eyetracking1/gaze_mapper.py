import numpy as np
import logging
from typing import Tuple, Optional
from settings import (
    CALIB_MAX_POINT_MEAN_ERR_RATIO,
    CALIB_MAX_RMSE_RATIO,
    SMOOTHING_ALPHA,
    MOVE_THRESHOLD_PX,
    LINEAR_GAZE_X_MIN,
    LINEAR_GAZE_X_MAX,
    LINEAR_GAZE_Y_MIN,
    LINEAR_GAZE_Y_MAX,
)

# pyautogui serverda (headless) ishlamasligi mumkin
try:
    import pyautogui
    _SCREEN_SIZE = pyautogui.size()
except Exception:
    _SCREEN_SIZE = (1920, 1080)

logger = logging.getLogger(__name__)


class KalmanGaze:
    """
    Oddiy 2D Kalman filter — cursor titroqligini kamaytiradi.
    """
    def __init__(self):
        self.x = np.zeros((4, 1), dtype=np.float32)   # [x, y, vx, vy]
        self.P = np.eye(4, dtype=np.float32) * 500
        self.F = np.array([[1,0,1,0],[0,1,0,1],[0,0,1,0],[0,0,0,1]], np.float32)
        self.H = np.array([[1,0,0,0],[0,1,0,0]], np.float32)
        self.R = np.eye(2, dtype=np.float32) * 50
        self.Q = np.eye(4, dtype=np.float32) * 0.1

    def update(self, mx: float, my: float) -> Tuple[float, float]:
        # Predict
        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q
        # Update
        z = np.array([[mx], [my]], dtype=np.float32)
        y = z - self.H @ self.x
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)
        self.x = self.x + K @ y
        self.P = (np.eye(4) - K @ self.H) @ self.P
        return float(self.x[0][0]), float(self.x[1][0])


class GazeMapper:
    """
    Iris normallashgan koordinati (0-1) ni
    ekran piksel koordinatiga aylantiradi.

    Kalibrasiya bo'lmasa → oddiy linear mapping.
    Kalibrasiya bo'lsa   → polynomial regression matritsa ishlatiladi.
    """

    def __init__(self):
        self.screen_w, self.screen_h = _SCREEN_SIZE
        self._calib_model   = None   # sklearn model (keyinroq)
        self._kalman        = KalmanGaze()
        self._smoothed_x    = self.screen_w  / 2
        self._smoothed_y    = self.screen_h / 2
        self._last_x        = self._smoothed_x
        self._last_y        = self._smoothed_y
        logger.info(f"GazeMapper: ekran {self.screen_w}x{self.screen_h}")

    def _reset_filter_state(self):
        self._kalman = KalmanGaze()
        self._smoothed_x = self.screen_w / 2
        self._smoothed_y = self.screen_h / 2
        self._last_x = self._smoothed_x
        self._last_y = self._smoothed_y

    def set_screen_size(self, screen_w: int, screen_h: int, reset_filter: bool = True):
        screen_w = max(1, int(screen_w))
        screen_h = max(1, int(screen_h))
        if screen_w == self.screen_w and screen_h == self.screen_h:
            return
        self.screen_w = screen_w
        self.screen_h = screen_h
        if reset_filter:
            self._reset_filter_state()
        logger.info("GazeMapper: ekran o'lchami yangilandi: %dx%d", self.screen_w, self.screen_h)

    def clear_calibration(self, reset_filter: bool = False):
        self._calib_model = None
        if reset_filter:
            self._reset_filter_state()
        logger.info("GazeMapper: kalibrasiya modeli tozalandi.")

    def set_calibration(self, model):
        """Kalibrasiya modeli o'rnatiladi (calibration.py dan keladi)."""
        if model is None:
            self.clear_calibration()
            return False
        if not self._is_valid_calibration(model):
            logger.warning("GazeMapper: kalibrasiya modeli yaroqsiz, linear mapping ishlatiladi.")
            self._calib_model = None
            return False
        self._calib_model = model
        logger.info("GazeMapper: kalibrasiya modeli o'rnatildi.")
        return True

    def _is_valid_calibration(self, model) -> bool:
        try:
            samples = np.array([
                [0.15, 0.15, 0.15**2, 0.15**2, 0.15 * 0.15],
                [0.85, 0.15, 0.85**2, 0.15**2, 0.85 * 0.15],
                [0.15, 0.85, 0.15**2, 0.85**2, 0.15 * 0.85],
                [0.85, 0.85, 0.85**2, 0.85**2, 0.85 * 0.85],
                [0.50, 0.50, 0.50**2, 0.50**2, 0.50 * 0.50],
            ], dtype=float)
            pred = np.asarray(model.predict(samples), dtype=float)
            span_x = float(np.ptp(pred[:, 0]))
            span_y = float(np.ptp(pred[:, 1]))
            if span_x < self.screen_w * 0.15 or span_y < self.screen_h * 0.12:
                return False

            rmse_px = float(getattr(model, "rmse_px", 0.0) or 0.0)
            if rmse_px and rmse_px > min(self.screen_w, self.screen_h) * CALIB_MAX_RMSE_RATIO:
                logger.warning("GazeMapper: kalibrasiya RMSE juda katta: %.1fpx", rmse_px)
                return False

            point_error = float(getattr(model, "max_mean_error_px", 0.0) or 0.0)
            if (
                point_error
                and point_error > min(self.screen_w, self.screen_h) * CALIB_MAX_POINT_MEAN_ERR_RATIO
            ):
                logger.warning(
                    "GazeMapper: kalibrasiya nuqta xatosi juda katta: %.1fpx",
                    point_error,
                )
                return False
            return True
        except Exception as e:
            logger.warning("GazeMapper: kalibrasiya validatsiyasi yiqildi: %s", e)
            return False

    def map(self, gaze_norm: Tuple[float, float]) -> Tuple[int, int]:
        """
        (nx, ny) → (screen_x, screen_y) piksel.
        Natija ekran chegarasida qoladi.
        """
        nx, ny = gaze_norm

        if self._calib_model is not None:
            sx, sy = self._calibrated_map(nx, ny)
        else:
            sx, sy = self._linear_map(nx, ny)

        # Kalman smoothing
        sx, sy = self._kalman.update(sx, sy)

        # Exponential smoothing (qo'shimcha yumshatish)
        self._smoothed_x = (SMOOTHING_ALPHA * sx +
                            (1 - SMOOTHING_ALPHA) * self._smoothed_x)
        self._smoothed_y = (SMOOTHING_ALPHA * sy +
                            (1 - SMOOTHING_ALPHA) * self._smoothed_y)

        fx = int(np.clip(self._smoothed_x, 0, self.screen_w  - 1))
        fy = int(np.clip(self._smoothed_y, 0, self.screen_h - 1))
        return fx, fy

    def has_moved(self, sx: int, sy: int) -> bool:
        """Cursor yetarlicha yurdimi (jitter filtri)."""
        d = ((sx - self._last_x)**2 + (sy - self._last_y)**2) ** 0.5
        if d >= MOVE_THRESHOLD_PX:
            self._last_x, self._last_y = sx, sy
            return True
        return False

    def _linear_map(self, nx: float, ny: float) -> Tuple[float, float]:
        """
        Kalibrasiyasiz oddiy linear mapping.
        Relative gaze signal 0-1 oralig'ida bo'ladi.
        """
        nx = float(np.clip(nx, LINEAR_GAZE_X_MIN, LINEAR_GAZE_X_MAX))
        ny = float(np.clip(ny, LINEAR_GAZE_Y_MIN, LINEAR_GAZE_Y_MAX))
        sx = (nx - LINEAR_GAZE_X_MIN) / (LINEAR_GAZE_X_MAX - LINEAR_GAZE_X_MIN) * self.screen_w
        sy = (ny - LINEAR_GAZE_Y_MIN) / (LINEAR_GAZE_Y_MAX - LINEAR_GAZE_Y_MIN) * self.screen_h
        return sx, sy

    def _calibrated_map(self, nx: float, ny: float) -> Tuple[float, float]:
        # Qo'shimcha nolinear xususiyatlar (ko'zning burchaklarga qarashi non-linear bo'ladi)
        feat = np.array([[nx, ny, nx**2, ny**2, nx*ny]])
        pred = self._calib_model.predict(feat)[0]
        return float(pred[0]), float(pred[1])
