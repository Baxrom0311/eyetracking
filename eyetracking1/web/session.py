"""
GazeSpeak Web — Har bir WebSocket ulanish uchun tracker session.
"""

import sys
import os
import logging
import time
import cv2
import numpy as np
from typing import Optional, Dict, Any

# Ota papkadan modullarni import qilish
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from face_tracker import FaceTracker
from gaze_mapper import GazeMapper
from calibration import CalibrationManager
from zone_analyzer import ZoneAnalyzer
from settings import ZONE_FIRED_BANNER_SEC

logger = logging.getLogger(__name__)


class GazeSession:
    """
    Bitta foydalanuvchi uchun gaze tracking sessiyasi.
    Har bir WebSocket ulanishda yangi instance yaratiladi.
    """

    def __init__(self):
        self.tracker = FaceTracker()
        self.mapper = GazeMapper()
        self.calib_mgr = CalibrationManager(self.mapper.screen_w, self.mapper.screen_h)
        self.zones = ZoneAnalyzer()
        self.screen_w = self.mapper.screen_w
        self.screen_h = self.mapper.screen_h

        # Holat
        self.calibrating = False
        self.calibration_done = False
        self.gaze_screen = None
        self.zone_idx = -1
        self.zone_progress = 0.0
        self.zone_fired_until = 0.0
        self.zone_message = None
        self.debug = False

        # FPS hisoblash
        self._frame_count = 0
        self._fps_start = time.time()
        self._current_fps = 0.0

        # Saqlangan kalibratsiyani yuklash
        saved_model = CalibrationManager.load_saved()
        if saved_model is not None and self.mapper.set_calibration(saved_model):
            self.calibration_done = True
            logger.info("Session: saqlangan kalibrasiya yuklandi.")

    def _reset_zone_state(self):
        self.gaze_screen = None
        self.zone_idx = -1
        self.zone_progress = 0.0
        self.zone_fired_until = 0.0
        self.zone_message = None
        self.zones.reset_zone()

    def set_screen_size(self, screen_w: int, screen_h: int):
        screen_w = max(1, int(screen_w))
        screen_h = max(1, int(screen_h))
        if screen_w == self.screen_w and screen_h == self.screen_h:
            return
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.mapper.set_screen_size(screen_w, screen_h)
        logger.info("Session: ekran o'lchami yangilandi (%dx%d).", screen_w, screen_h)

    def process_frame(self, jpeg_bytes: bytes) -> Dict[str, Any]:
        """
        JPEG frame ni qabul qilib, gaze natijasini qaytaradi.
        """
        # JPEG → numpy array
        arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is None:
            return {"error": "Frame decode xatosi"}

        # FPS hisoblash
        self._frame_count += 1
        elapsed = time.time() - self._fps_start
        if elapsed >= 1.0:
            self._current_fps = self._frame_count / elapsed
            self._frame_count = 0
            self._fps_start = time.time()

        # Face tracking
        face_data = self.tracker.process(frame)
        iris_found = face_data.left_iris.found or face_data.right_iris.found
        gaze_ready = face_data.found and iris_found and not face_data.head_away

        result: Dict[str, Any] = {
            "face_found": face_data.found,
            "head_away": face_data.head_away,
            "fps": round(self._current_fps, 1),
            "gaze": None,
            "state": "IDLE",
            "zone": None,
            "calibration": {
                "active": self.calibrating,
                "point": None,
                "progress": 0.0,
                "current": 0,
                "total": 0,
                "done": self.calibration_done,
            },
            "emotion": face_data.emotion if face_data.found else "😶 Yuz yo'q",
            "blink": {
                "single": self.tracker.blink_detector.single_blink,
                "double": self.tracker.blink_detector.double_blink,
                "long": self.tracker.blink_detector.long_blink,
            },
        }

        # Kalibratsiya jarayoni
        if self.calibrating:
            result["state"] = "CALIBRATING"
            gaze_norm = face_data.gaze_norm if gaze_ready else None
            done = self.calib_mgr.update(gaze_norm)

            # Kalibratsiya nuqtasi ma'lumotlari
            pt = self.calib_mgr.current_point()
            if pt is not None:
                result["calibration"]["point"] = {
                    "x": pt.screen_x,
                    "y": pt.screen_y,
                }
                result["calibration"]["progress"] = self.calib_mgr.current_progress()
                result["calibration"]["current"] = self.calib_mgr.current_index() + 1
                result["calibration"]["total"] = self.calib_mgr.total_points()

            if done and self.calib_mgr.get_model() is not None:
                if self.mapper.set_calibration(self.calib_mgr.get_model()):
                    self.calibrating = False
                    self.calibration_done = True
                    result["state"] = "CALIBRATION_DONE"
                    logger.info("Session: kalibrasiya muvaffaqiyatli tugadi.")
                else:
                    self.calib_mgr.start()
                    result["calibration"]["error"] = "Kalibrasiya yaroqsiz, qayta urinib ko'ring"
        else:
            # Tracking
            if not face_data.found:
                result["state"] = "NO_FACE"
            elif face_data.head_away:
                result["state"] = "HEAD_AWAY"
            elif not self.calibration_done:
                result["state"] = "NEEDS_CALIBRATION"
            elif gaze_ready:
                result["state"] = "TRACKING"
                sx, sy = self.mapper.map(face_data.gaze_norm)
                self.gaze_screen = (sx, sy)
                result["gaze"] = [round(sx, 1), round(sy, 1)]

                # Zona tahlili
                if time.time() >= self.zone_fired_until:
                    zone_result = self.zones.update(sx, sy)
                    z_idx, z_prog = self.zones.get_progress(sx, sy)
                    self.zone_idx = z_idx
                    self.zone_progress = z_prog

                    if zone_result:
                        self.zone_fired_until = time.time() + ZONE_FIRED_BANNER_SEC
                        self.zone_message = zone_result.get("message", "")
                        result["zone"] = {
                            "idx": z_idx,
                            "progress": round(z_prog, 2),
                            "name": zone_result.get("zone_name", ""),
                            "message": self.zone_message,
                            "fired": True,
                        }
                    elif z_idx >= 0:
                        result["zone"] = {
                            "idx": z_idx,
                            "progress": round(z_prog, 2),
                            "name": "",
                            "message": "",
                            "fired": False,
                        }
            else:
                result["state"] = "LOW_QUALITY"

        return result

    def start_calibration(self, screen_w: int, screen_h: int):
        """Kalibratsiyani boshlash."""
        self.set_screen_size(screen_w, screen_h)
        self.mapper.clear_calibration(reset_filter=True)
        self.calib_mgr = CalibrationManager(self.screen_w, self.screen_h)
        self.calib_mgr.start()
        self.calibrating = True
        self.calibration_done = False
        self._reset_zone_state()
        logger.info("Session: kalibrasiya boshlandi (%dx%d).", self.screen_w, self.screen_h)

    def reset_calibration(self):
        """Kalibratsiyani bekor qilish."""
        self.calibrating = False
        self.calibration_done = False
        self.mapper.clear_calibration(reset_filter=True)
        self._reset_zone_state()

    def close(self):
        """Resurslarni tozalash."""
        try:
            self.tracker.close()
        except Exception:
            pass
