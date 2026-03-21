import cv2
import time
import logging
import numpy as np
import sys
from settings import (
    CAMERA_INDEX, CAMERA_WIDTH, CAMERA_HEIGHT,
    CAMERA_FPS, LOW_LIGHT_THRESHOLD
)

logger = logging.getLogger(__name__)


class CameraError(Exception):
    pass


class CameraManager:
    """
    Webcam ni ochadi, frame oladi, yopadi.
    Xatolarni ushlaydi va State Machine ga xabar beradi.
    """

    def __init__(self, index: int = CAMERA_INDEX):
        self.index   = index
        self.cap     = None
        self._fps_times = []
        self.fps     = 0.0
        self.brightness = 255

    def _open_capture(self):
        # macOS da AVFoundation backend ni aniq ko'rsatish ruxsat/xulqni barqaror qiladi.
        if sys.platform == "darwin":
            return cv2.VideoCapture(self.index, cv2.CAP_AVFOUNDATION)
        return cv2.VideoCapture(self.index)

    # ── ochish ────────────────────────────────────────────
    def open(self) -> bool:
        """
        Kamerani ochadi.
        Muvaffaqiyatli bo'lsa True, bo'lmasa CameraError tashlaydi.
        """
        self.cap = self._open_capture()
        if not self.cap.isOpened():
            if sys.platform == "darwin":
                raise CameraError(
                    f"Kamera {self.index} ochilmadi. macOS Camera ruxsati "
                    "berilmagan yoki boshqa dastur kamerani band qilgan. "
                    "System Settings -> Privacy & Security -> Camera bo'limida "
                    "terminalingizga (Terminal, iTerm, VS Code) ruxsat bering."
                )
            raise CameraError(
                f"Kamera {self.index} topilmadi yoki ruxsat yo'q. "
                "Boshqa dastur kamerani ishlatayotgan bo'lishi mumkin."
            )
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH,  CAMERA_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
        self.cap.set(cv2.CAP_PROP_FPS,          CAMERA_FPS)
        logger.info(f"Kamera {self.index} ochildi: "
                    f"{int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x"
                    f"{int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")
        return True

    # ── frame olish ───────────────────────────────────────
    def read(self):
        """
        Bir frame qaytaradi (BGR numpy array).
        Muammo bo'lsa None qaytaradi.
        """
        if self.cap is None or not self.cap.isOpened():
            return None

        ok, frame = self.cap.read()
        if not ok or frame is None:
            logger.warning("Frame olinmadi.")
            return None

        self._update_fps()
        self._update_brightness(frame)
        return frame

    # ── yorug'lik tekshirish ──────────────────────────────
    def is_low_light(self) -> bool:
        return self.brightness < LOW_LIGHT_THRESHOLD

    def _update_brightness(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        self.brightness = int(np.mean(gray))

    # ── FPS hisoblash ─────────────────────────────────────
    def _update_fps(self):
        now = time.time()
        self._fps_times.append(now)
        # Faqat oxirgi 1 soniyani saqlaymiz
        self._fps_times = [t for t in self._fps_times if now - t < 1.0]
        self.fps = len(self._fps_times)

    # ── yopish ────────────────────────────────────────────
    def close(self):
        if self.cap and self.cap.isOpened():
            self.cap.release()
            logger.info("Kamera yopildi.")
        self.cap = None

    # ── context manager ───────────────────────────────────
    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *_):
        self.close()

    # ── info ──────────────────────────────────────────────
    def info(self) -> dict:
        return {
            "index":      self.index,
            "fps":        round(self.fps, 1),
            "brightness": self.brightness,
            "low_light":  self.is_low_light(),
            "opened":     self.cap.isOpened() if self.cap else False,
        }
