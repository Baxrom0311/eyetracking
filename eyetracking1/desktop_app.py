"""
GazeSpeak Desktop.

Native Qt AAC interface with direct Python tracking. This removes the
browser/WebSocket/JSON layer from the patient-facing app.

Run:
    python desktop_app.py
"""

from __future__ import annotations

import argparse
import logging
import os
import queue
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from calibration import CalibrationManager
from camera import CameraError, CameraManager
from face_tracker import FaceTracker
from gaze_mapper import GazeMapper
from app_meta import APP_NAME, APP_VERSION
from app_paths import ensure_runtime_dirs, runtime_snapshot
from settings import CAMERA_READ_FAIL_LIMIT, PREVIEW_MIRROR
from tts_engine import TTSEngine

logger = logging.getLogger(__name__)

TARGET_PROCESS_FPS = 20
FRAME_INTERVAL = 1.0 / TARGET_PROCESS_FPS
AAC_DWELL_SEC = 1.45
AAC_ACTION_COOLDOWN_SEC = 1.10
MAX_MESSAGE_WORDS = 14
CALIBRATION_GRID_POSITIONS = [0.12, 0.50, 0.88]


@dataclass(frozen=True)
class Tile:
    label: str
    hint: str = ""
    tone: str = "neutral"


PATIENT_PAGES: dict[str, dict[str, Any]] = {
    "core": {
        "title": "Asosiy so'zlar",
        "note": "Eng ko'p ishlatiladigan so'zlar.",
        "tiles": [
            Tile("Men", "subyekt", "gold"),
            Tile("Xohlayman", "istak", "mint"),
            Tile("Ko'proq", "davom", "sky"),
            Tile("To'xta", "stop", "coral"),
            Tile("Sen", "murojaat", "sand"),
            Tile("Ha", "tasdiq", "lime"),
            Tile("Yo'q", "rad", "rose"),
            Tile("Bor", "harakat", "mint"),
            Tile("Yordam", "chaqiruv", "coral"),
            Tile("Yana", "takror", "sky"),
            Tile("Yoqadi", "his", "gold"),
            Tile("Emas", "inkor", "slate"),
        ],
    },
    "needs": {
        "title": "Ehtiyoj va parvarish",
        "note": "Kundalik va tibbiy ehtiyojlar.",
        "tiles": [
            Tile("Suv", "ichimlik", "sky"),
            Tile("Og'riq", "og'riq bor", "coral"),
            Tile("Hojatxona", "hojat", "sand"),
            Tile("Shifokor", "tibbiy yordam", "slate"),
            Tile("Sovuq", "harorat", "sky"),
            Tile("Issiq", "harorat", "gold"),
            Tile("Ochman", "ovqat", "lime"),
            Tile("Charchadim", "dam", "rose"),
            Tile("Dori", "medikament", "mint"),
            Tile("Burang", "pozitsiya", "sand"),
            Tile("Yostiq", "qulaylik", "gold"),
            Tile("Nafas", "nafas olish", "mint"),
        ],
    },
    "feelings": {
        "title": "Hissiyot va javoblar",
        "note": "Holat va kayfiyat.",
        "tiles": [
            Tile("Yaxshi", "ijobiy", "mint"),
            Tile("Yomon", "salbiy", "coral"),
            Tile("Qo'rqdim", "xavotir", "rose"),
            Tile("Tinch", "xotirjam", "sky"),
            Tile("Rahmat", "minnatdorchilik", "gold"),
            Tile("Iltimos", "iltimos", "sand"),
            Tile("Tushundim", "angladim", "lime"),
            Tile("Tushunmadim", "izoh kerak", "slate"),
            Tile("Yetarli", "bo'ldi", "coral"),
            Tile("Yana ayting", "takrorlang", "sky"),
            Tile("Yolg'iz", "hamroh kerak", "rose"),
            Tile("Xursand", "kayfiyat", "gold"),
        ],
    },
    "personal": {
        "title": "Odamlar va shaxsiy",
        "note": "Oila va shaxsiy mavzular.",
        "tiles": [
            Tile("Ona", "oila", "rose"),
            Tile("Ota", "oila", "sand"),
            Tile("Hamshira", "parvarish", "mint"),
            Tile("Oilam", "yaqinlar", "gold"),
            Tile("Telefon", "aloqa", "slate"),
            Tile("Musiqa", "dam", "sky"),
            Tile("Uy", "joy", "lime"),
            Tile("Tashqariga", "sayr", "mint"),
            Tile("Ismim", "tanishtirish", "sand"),
            Tile("Ibodat", "ruhiy", "gold"),
            Tile("TV", "ekran", "sky"),
            Tile("Qo'ng'iroq", "chaqirish", "coral"),
        ],
    },
}

QUICK_REPLIES = [
    "Ha",
    "Yo'q",
    "Yordam kerak",
    "Og'riq bor",
    "To'xtating",
    "Rahmat",
]

EMERGENCY_REPLIES = [
    "Tez yordam kerak",
    "Nafas olish qiyin",
    "Kuchli og'riq",
    "Hamshirani chaqiring",
]

PHRASE_BANK = [
    "Men suv xohlayman",
    "Meni burang",
    "Menga yostiq kerak",
    "Hojatxona kerak",
    "Men charchadim",
    "Oilam bilan gaplashmoqchiman",
]

PREDICTION_MAP = {
    "__start__": ["Men", "Ha", "Yo'q", "Yordam"],
    "men": ["Xohlayman", "Yaxshi", "Yomon", "Yordam"],
    "men xohlayman": ["Suv", "Yordam", "Ko'proq", "Yostiq"],
    "og'riq": ["Bor", "Ko'proq", "Shifokor"],
    "yordam": ["Kerak", "Hamshira", "Tezroq"],
    "hojatxona": ["Kerak"],
    "nafas": ["Qiyin", "Kerak"],
}

class TrackingWorker(QThread):
    update = Signal(dict)
    fatal_error = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._commands: queue.Queue[tuple[str, dict[str, Any]]] = queue.Queue()
        self._running = True

    def stop(self) -> None:
        self._running = False
        self._commands.put(("stop", {}))

    def set_surface_size(self, width: int, height: int) -> None:
        self._commands.put(("surface", {"w": width, "h": height}))

    def start_calibration(self, width: int, height: int) -> None:
        self._commands.put(("start_calibration", {"w": width, "h": height}))

    def reset_calibration(self) -> None:
        self._commands.put(("reset_calibration", {}))

    def speak(self, text: str) -> None:
        self._commands.put(("speak", {"text": text}))

    def run(self) -> None:
        camera = CameraManager()
        tracker: FaceTracker | None = None
        mapper: GazeMapper | None = None
        calib_mgr: CalibrationManager | None = None
        tts: TTSEngine | None = None
        calibration_done = False
        calibrating = False
        empty_frames = 0

        try:
            tracker = FaceTracker(enable_blendshapes=False)
            mapper = GazeMapper()
            calib_mgr = CalibrationManager(mapper.screen_w, mapper.screen_h)
            tts = TTSEngine()

            saved = CalibrationManager.load_saved(mapper.screen_w, mapper.screen_h)
            if saved is not None and mapper.set_calibration(saved):
                calibration_done = True

            camera.open()
        except Exception as exc:
            self.fatal_error.emit(str(exc))
            self.update.emit({"state": "CAMERA_ERROR", "error": str(exc)})
            return

        while self._running:
            loop_start = time.time()

            while True:
                try:
                    command, payload = self._commands.get_nowait()
                except queue.Empty:
                    break

                if command == "stop":
                    self._running = False
                    break
                if mapper is None:
                    continue
                if command == "surface":
                    mapper.set_screen_size(payload["w"], payload["h"], reset_filter=False)
                    if calib_mgr is None:
                        calib_mgr = CalibrationManager(mapper.screen_w, mapper.screen_h)
                elif command == "start_calibration":
                    mapper.set_screen_size(payload["w"], payload["h"])
                    mapper.clear_calibration(reset_filter=True)
                    calib_mgr = CalibrationManager(mapper.screen_w, mapper.screen_h)
                    calib_mgr.start()
                    calibrating = True
                    calibration_done = False
                elif command == "reset_calibration":
                    mapper.clear_calibration(reset_filter=True)
                    calib_mgr = CalibrationManager(mapper.screen_w, mapper.screen_h)
                    calibrating = False
                    calibration_done = False
                elif command == "speak" and tts is not None:
                    text = str(payload.get("text", "")).strip()
                    if text:
                        tts.speak(text[:200])

            if not self._running:
                break

            frame = camera.read()
            if frame is None:
                empty_frames += 1
                if empty_frames >= CAMERA_READ_FAIL_LIMIT:
                    self.update.emit({
                        "state": "CAMERA_ERROR",
                        "error": "Kamera frame bermayapti",
                        "fps": round(camera.fps, 1),
                    })
                    self.fatal_error.emit("Kamera frame bermayapti")
                    break
                time.sleep(0.005)
                continue

            empty_frames = 0
            if PREVIEW_MIRROR:
                frame = cv2.flip(frame, 1)

            assert tracker is not None
            assert mapper is not None
            assert calib_mgr is not None

            face_data = tracker.process(frame)
            iris_found = face_data.left_iris.found or face_data.right_iris.found
            gaze_ready = face_data.found and iris_found and not face_data.head_away

            result = {
                "face_found": face_data.found,
                "head_away": face_data.head_away,
                "fps": round(camera.fps, 1),
                "gaze": None,
                "camera_frame": None,
                "state": "IDLE",
                "surface": {"w": mapper.screen_w, "h": mapper.screen_h},
                "calibration": {
                    "active": calibrating,
                    "done": calibration_done,
                    "point": None,
                    "progress": 0.0,
                    "current": 0,
                    "total": 0,
                },
                "blink": {
                    "single": tracker.blink_detector.single_blink,
                    "double": tracker.blink_detector.double_blink,
                    "long": tracker.blink_detector.long_blink,
                },
            }

            if calibrating:
                result["state"] = "CALIBRATING"
                gaze_norm = face_data.gaze_norm if gaze_ready else None
                if gaze_norm is not None:
                    sx, sy = mapper.map(gaze_norm)
                    result["gaze"] = [sx, sy]
                is_blinking = face_data.left_blink or face_data.right_blink
                done = calib_mgr.update(gaze_norm, is_blinking=is_blinking)

                point = calib_mgr.current_point()
                if point is not None:
                    result["calibration"].update({
                        "point": {"x": point.screen_x, "y": point.screen_y},
                        "progress": calib_mgr.current_progress(),
                        "current": calib_mgr.current_index() + 1,
                        "total": calib_mgr.total_points(),
                    })

                if done and calib_mgr.get_model() is not None:
                    if mapper.set_calibration(calib_mgr.get_model()):
                        calibrating = False
                        calibration_done = True
                        result["state"] = "CALIBRATION_DONE"
                    else:
                        calib_mgr.start()
                        result["calibration"]["error"] = "Kalibrasiya yaroqsiz"
                elif not calib_mgr.active and not calib_mgr.done:
                    calibrating = False
                    result["state"] = "CALIBRATION_FAILED"
                    result["calibration"]["error"] = "Kalibrasiya tugamadi"
            else:
                if not face_data.found:
                    result["state"] = "NO_FACE"
                elif face_data.head_away:
                    result["state"] = "HEAD_AWAY"
                elif gaze_ready:
                    sx, sy = mapper.map(face_data.gaze_norm)
                    result["gaze"] = [sx, sy]
                    result["state"] = "TRACKING" if calibration_done else "NEEDS_CALIBRATION"
                elif not calibration_done:
                    result["state"] = "NEEDS_CALIBRATION"
                else:
                    result["state"] = "LOW_QUALITY"

            result["camera_frame"] = tracker.draw_debug(frame.copy(), face_data)
            self.update.emit(result)

            elapsed = time.time() - loop_start
            if FRAME_INTERVAL > elapsed:
                time.sleep(FRAME_INTERVAL - elapsed)

        camera.close()
        if tracker is not None:
            tracker.close()
        if tts is not None:
            tts.stop()


class GazeDot(QWidget):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setFixedSize(34, 34)
        self.hide()

    def paintEvent(self, event) -> None:  
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(245, 197, 66, 150), 3))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(4, 4, 26, 26)
        painter.setPen(QPen(QColor(245, 197, 66, 230), 2))
        painter.drawLine(17, 2, 17, 11)
        painter.drawLine(17, 23, 17, 32)
        painter.drawLine(2, 17, 11, 17)
        painter.drawLine(23, 17, 32, 17)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(245, 197, 66))
        painter.drawEllipse(12, 12, 10, 10)


class CalibrationOverlay(QWidget):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._calibration: dict[str, Any] = {}
        self._surface = {"w": 1, "h": 1}
        self.hide()

    def set_data(self, calibration: dict[str, Any], surface: dict[str, Any]) -> None:
        self._calibration = calibration
        self._surface = surface
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 225))

        point = self._calibration.get("point")
        if not point:
            return

        sw = max(1, int(self._surface.get("w") or self.width()))
        sh = max(1, int(self._surface.get("h") or self.height()))
        x = int(point["x"] / sw * self.width())
        y = int(point["y"] / sh * self.height())
        progress = float(self._calibration.get("progress") or 0.0)
        current = int(self._calibration.get("current") or 0)
        total = int(self._calibration.get("total") or 0)

        painter.setPen(QPen(QColor(255, 255, 255, 80), 4))
        painter.drawEllipse(QPoint(x, y), 34, 34)
        painter.setPen(QPen(QColor(0, 220, 130), 5))
        painter.drawArc(QRect(x - 34, y - 34, 68, 68), 90 * 16, int(-360 * progress * 16))
        painter.setBrush(QColor(0, 220, 130))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPoint(x, y), 8, 8)

        painter.setPen(QColor("#fff5dc"))
        painter.setFont(QFont("Arial", 20, QFont.Bold))
        painter.drawText(QRect(0, 28, self.width(), 44), Qt.AlignCenter, f"Nuqta {current}/{total}")
        painter.setFont(QFont("Arial", 13))
        painter.drawText(
            QRect(0, 72, self.width(), 32),
            Qt.AlignCenter,
            "Nuqtaga qarang, ko'zni qimirlatmang",
        )


class CalibrationSurface(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._calibration: dict[str, Any] = {}
        self._surface = {"w": 1, "h": 1}
        self._gaze: list[int] | None = None
        self._state = "IDLE"
        self.setMinimumHeight(420)

    def set_data(
        self,
        calibration: dict[str, Any],
        surface: dict[str, Any],
        gaze: list[int] | None,
        state: str,
    ) -> None:
        self._calibration = calibration or {}
        self._surface = surface or {"w": 1, "h": 1}
        self._gaze = gaze
        self._state = state
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#111315"))

        inner = self.rect().adjusted(18, 18, -18, -18)
        painter.setPen(QPen(QColor("#2b3136"), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(inner, 12, 12)

        points = self._grid_points(inner)
        calibration_active = bool(self._calibration.get("active"))
        calibration_done = bool(self._calibration.get("done"))
        current_index = max(0, int(self._calibration.get("current") or 1) - 1)
        progress = float(self._calibration.get("progress") or 0.0)

        for index, point in enumerate(points):
            if calibration_done and not calibration_active:
                painter.setBrush(QColor(0, 190, 120))
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(point, 8, 8)
                continue

            if calibration_active and index < current_index:
                painter.setBrush(QColor(120, 125, 132))
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(point, 7, 7)
                continue

            if calibration_active and index == current_index:
                painter.setPen(QPen(QColor(0, 220, 130), 4))
                painter.setBrush(Qt.NoBrush)
                painter.drawArc(QRect(point.x() - 30, point.y() - 30, 60, 60), 90 * 16, int(-360 * progress * 16))
                painter.setPen(QPen(QColor(255, 255, 255, 90), 2))
                painter.drawEllipse(point, 24, 24)
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(0, 220, 130))
                painter.drawEllipse(point, 8, 8)
                continue

            painter.setPen(QPen(QColor("#4b555d"), 1))
            painter.setBrush(QColor("#242a2f"))
            painter.drawEllipse(point, 6, 6)

        if self._gaze:
            gx, gy = self._map_surface_point(self._gaze[0], self._gaze[1], inner)
            gaze_point = QPoint(gx, gy)
            painter.setPen(QPen(QColor(245, 197, 66, 150), 3))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(gaze_point, 14, 14)
            painter.drawLine(gx, gy - 18, gx, gy - 6)
            painter.drawLine(gx, gy + 6, gx, gy + 18)
            painter.drawLine(gx - 18, gy, gx - 6, gy)
            painter.drawLine(gx + 6, gy, gx + 18, gy)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(245, 197, 66))
            painter.drawEllipse(gaze_point, 4, 4)

        painter.setPen(QColor("#f6f1e8"))
        painter.setFont(QFont("Arial", 12, QFont.Bold))
        if calibration_active:
            current = int(self._calibration.get("current") or 0)
            total = int(self._calibration.get("total") or 0)
            text = f"Nuqta {current}/{total}"
        elif calibration_done:
            text = "Kalibratsiya tayyor"
        elif self._state == "NEEDS_CALIBRATION":
            text = "Kursorga qarab markazlarni tekshiring"
        else:
            text = "Kalibratsiyani boshlashga tayyor"
        painter.drawText(inner.adjusted(12, 12, -12, -12), Qt.AlignTop | Qt.AlignLeft, text)

    def _grid_points(self, rect: QRect) -> list[QPoint]:
        points: list[QPoint] = []
        for row in CALIBRATION_GRID_POSITIONS:
            for col in CALIBRATION_GRID_POSITIONS:
                x = rect.left() + int(rect.width() * col)
                y = rect.top() + int(rect.height() * row)
                points.append(QPoint(x, y))
        return points

    def _map_surface_point(self, x: int, y: int, rect: QRect) -> tuple[int, int]:
        sw = max(1, int(self._surface.get("w") or self.width()))
        sh = max(1, int(self._surface.get("h") or self.height()))
        px = rect.left() + int((x / sw) * rect.width())
        py = rect.top() + int((y / sh) * rect.height())
        return px, py


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("GazeSpeak Desktop")
        self.resize(1360, 860)
        self._words: list[str] = []
        self._current_page = "core"
        self._active_target: QPushButton | None = None
        self._target_started_at = 0.0
        self._cooldown_until = 0.0
        self._last_surface = QSize(1, 1)
        self._section_grids: dict[QFrame, QGridLayout] = {}
        self._board_columns = 4
        self._support_columns = 2
        self._metrics: dict[str, int] = {}
        self._mode = "communication"
        self._last_camera_frame = None

        self.worker = TrackingWorker()
        self.worker.update.connect(self.handle_tracking_update)
        self.worker.fatal_error.connect(self.show_fatal_error)

        self.root = QWidget()
        self.root.setObjectName("root")
        self.setCentralWidget(self.root)

        self.gaze_dot = GazeDot(self.root)
        self.calibration_overlay = CalibrationOverlay(self.root)

        self._build_ui()
        self.render_all()
        self.set_mode("communication")
        self._apply_responsive_layout(force=True)

        self.worker.start()
        QTimer.singleShot(0, self.sync_surface_size)

    def _build_ui(self) -> None:
        self.root_layout = QVBoxLayout(self.root)
        self.root_layout.setContentsMargins(18, 16, 18, 18)
        self.root_layout.setSpacing(14)

        self.header_layout = QHBoxLayout()
        self.brand = QLabel("GazeSpeak Desktop")
        self.brand.setObjectName("brand")
        self.status_label = QLabel("Tracker yuklanmoqda")
        self.status_label.setObjectName("status")
        self.fps_label = QLabel("0 FPS")
        self.fps_label.setObjectName("pill")
        self.brand.setWordWrap(True)

        self.calibrate_btn = self._new_button("Kalibratsiya", "control")
        self.recalibrate_btn = self._new_button("Qayta kalibratsiya", "control")
        self.fullscreen_btn = self._new_button("To'liq ekran", "control")

        self._mark_target(self.calibrate_btn, "calibrate", "Kalibratsiya")
        self._mark_target(self.recalibrate_btn, "calibrate", "Qayta kalibratsiya")
        self._mark_target(self.fullscreen_btn, "fullscreen", "To'liq ekran")

        self.calibrate_btn.clicked.connect(self.start_calibration)
        self.recalibrate_btn.clicked.connect(self.start_calibration)
        self.fullscreen_btn.clicked.connect(self.toggle_fullscreen)

        self.header_layout.addWidget(self.brand)
        self.header_layout.addStretch(1)
        self.header_layout.addWidget(self.status_label)
        self.header_layout.addWidget(self.fps_label)
        self.header_layout.addWidget(self.calibrate_btn)
        self.header_layout.addWidget(self.recalibrate_btn)
        self.header_layout.addWidget(self.fullscreen_btn)
        self.root_layout.addLayout(self.header_layout)

        self.mode_nav = QHBoxLayout()
        self.mode_nav.setSpacing(10)
        self.mode_buttons: dict[str, QPushButton] = {}
        for mode, label in [
            ("communication", "Bosh sahifa"),
            ("calibration", "Kalibratsiya"),
            ("camera", "Kamera"),
        ]:
            button = self._new_button(label, "mode")
            button.setCheckable(True)
            self._mark_target(button, "mode", label, mode)
            button.clicked.connect(lambda checked=False, value=mode: self.set_mode(value))
            self.mode_buttons[mode] = button
            self.mode_nav.addWidget(button)
        self.mode_nav.addStretch(1)
        self.root_layout.addLayout(self.mode_nav)

        self.body_layout = QHBoxLayout()
        self.body_layout.setSpacing(14)
        self.root_layout.addLayout(self.body_layout, 1)

        self.left_panel = QFrame()
        self.left_panel.setObjectName("panel")
        self.left_layout = QVBoxLayout(self.left_panel)
        self.left_layout.setContentsMargins(16, 16, 16, 16)
        self.left_layout.setSpacing(12)

        self.message_label = QLabel("Tanlangan so'zlar shu yerda yig'iladi")
        self.message_label.setObjectName("message")
        self.message_label.setWordWrap(True)
        self.message_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.left_layout.addWidget(self.message_label)

        self.actions_layout = QHBoxLayout()
        self.backspace_btn = self._new_button("Orqaga", "control")
        self.clear_btn = self._new_button("Tozalash", "control")
        self.speak_btn = self._new_button("Gapirtirish", "control")
        self.camera_toggle_btn = self._new_button("Kamera", "control")
        for button, action, label in [
            (self.backspace_btn, "backspace", "Orqaga"),
            (self.clear_btn, "clear", "Tozalash"),
            (self.speak_btn, "speak", "Gapirtirish"),
            (self.camera_toggle_btn, "camera", "Kamera"),
        ]:
            self._mark_target(button, action, label)
            self.actions_layout.addWidget(button)
        self.backspace_btn.clicked.connect(self.backspace)
        self.clear_btn.clicked.connect(self.clear_message)
        self.speak_btn.clicked.connect(self.speak_message)
        self.camera_toggle_btn.clicked.connect(self.toggle_camera_mode)
        self.left_layout.addLayout(self.actions_layout)

        self.focus_label = QLabel("Nishon: -")
        self.focus_label.setObjectName("focus")
        self.dwell_bar = QProgressBar()
        self.dwell_bar.setRange(0, 100)
        self.dwell_bar.setTextVisible(False)
        self.left_layout.addWidget(self.focus_label)
        self.left_layout.addWidget(self.dwell_bar)

        self.prediction_frame = self._section("Takliflar")
        self.quick_frame = self._section("Tez javoblar")
        self.emergency_frame = self._section("Favqulodda")
        self.phrase_frame = self._section("Iboralar")
        self.support_scroll = QScrollArea()
        self.support_scroll.setWidgetResizable(True)
        self.support_scroll.setFrameShape(QFrame.NoFrame)
        self.support_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.support_content = QWidget()
        self.support_content.setObjectName("supportCanvas")
        self.support_layout = QVBoxLayout(self.support_content)
        self.support_layout.setContentsMargins(0, 0, 0, 0)
        self.support_layout.addWidget(self.prediction_frame)
        self.support_layout.addWidget(self.quick_frame)
        self.support_layout.addWidget(self.emergency_frame)
        self.support_layout.addWidget(self.phrase_frame)
        self.support_layout.addStretch(1)
        self.support_scroll.setWidget(self.support_content)
        self.left_layout.addWidget(self.support_scroll, 1)

        self.right_panel = QFrame()
        self.right_panel.setObjectName("panel")
        self.right_layout = QVBoxLayout(self.right_panel)
        self.right_layout.setContentsMargins(16, 16, 16, 16)
        self.right_layout.setSpacing(14)

        self.right_stack = QStackedWidget()
        self.right_stack.setObjectName("viewStack")
        self.right_layout.addWidget(self.right_stack, 1)

        self.communication_page = QWidget()
        self.communication_layout = QVBoxLayout(self.communication_page)
        self.communication_layout.setContentsMargins(0, 0, 0, 0)
        self.communication_layout.setSpacing(12)
        self.page_nav = QHBoxLayout()
        self.page_nav.setSpacing(10)
        self.communication_layout.addLayout(self.page_nav, 0)

        self.board_header = QVBoxLayout()
        self.board_title = QLabel("")
        self.board_title.setObjectName("boardTitle")
        self.board_title.setWordWrap(True)
        self.board_note = QLabel("")
        self.board_note.setObjectName("muted")
        self.board_note.setWordWrap(True)
        self.board_header.addWidget(self.board_title)
        self.board_header.addWidget(self.board_note)
        self.communication_layout.addLayout(self.board_header, 0)

        self.board_scroll = QScrollArea()
        self.board_scroll.setWidgetResizable(True)
        self.board_scroll.setFrameShape(QFrame.NoFrame)
        self.board_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.board_content = QWidget()
        self.board_content.setObjectName("boardCanvas")
        self.board_area = QVBoxLayout(self.board_content)
        self.board_area.setContentsMargins(0, 0, 0, 0)
        self.board_area.setSpacing(12)
        self.grid = QGridLayout()
        self.grid.setSpacing(12)
        self.grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.board_area.addLayout(self.grid, 0)
        self.board_area.addStretch(1)
        self.board_scroll.setWidget(self.board_content)
        self.communication_layout.addWidget(self.board_scroll, 1)
        self.right_stack.addWidget(self.communication_page)

        self.calibration_page = QWidget()
        self.calibration_page.setObjectName("toolPage")
        self.calibration_layout = QVBoxLayout(self.calibration_page)
        self.calibration_layout.setContentsMargins(0, 0, 0, 0)
        self.calibration_layout.setSpacing(12)
        self.calibration_title = QLabel("Kalibratsiya")
        self.calibration_title.setObjectName("boardTitle")
        self.calibration_note = QLabel("9 nuqtaga ketma-ket qarang. Sariq marker sizning hozirgi ko'z yo'nalishingizni ko'rsatadi.")
        self.calibration_note.setObjectName("muted")
        self.calibration_note.setWordWrap(True)
        self.calibration_layout.addWidget(self.calibration_title)
        self.calibration_layout.addWidget(self.calibration_note)
        self.calibration_actions = QHBoxLayout()
        self.calibration_start_btn = self._new_button("Kalibratsiyani boshlash", "control")
        self.calibration_reset_btn = self._new_button("Qayta boshlash", "control")
        self._mark_target(self.calibration_start_btn, "calibrate", "Kalibratsiyani boshlash")
        self._mark_target(self.calibration_reset_btn, "calibrate", "Qayta boshlash")
        self.calibration_start_btn.clicked.connect(self.start_calibration)
        self.calibration_reset_btn.clicked.connect(self.start_calibration)
        self.calibration_actions.addWidget(self.calibration_start_btn)
        self.calibration_actions.addWidget(self.calibration_reset_btn)
        self.calibration_actions.addStretch(1)
        self.calibration_layout.addLayout(self.calibration_actions)
        self.calibration_status = QLabel("Kalibratsiya hali ishga tushmagan")
        self.calibration_status.setObjectName("focus")
        self.calibration_layout.addWidget(self.calibration_status)
        self.calibration_surface = CalibrationSurface()
        self.calibration_surface.setObjectName("calibrationSurface")
        self.calibration_layout.addWidget(self.calibration_surface, 1)
        self.right_stack.addWidget(self.calibration_page)

        self.camera_page = QWidget()
        self.camera_page.setObjectName("toolPage")
        self.camera_layout = QVBoxLayout(self.camera_page)
        self.camera_layout.setContentsMargins(0, 0, 0, 0)
        self.camera_layout.setSpacing(12)
        self.camera_title = QLabel("Kamera va landmarklar")
        self.camera_title.setObjectName("boardTitle")
        self.camera_note = QLabel("Bu sahifa tashrif buyuruvchilar uchun: MediaPipe yuz landmarklari, iris aylanalari va ishlatilayotgan nuqtalar shu yerda ko'rinadi.")
        self.camera_note.setObjectName("muted")
        self.camera_note.setWordWrap(True)
        self.camera_layout.addWidget(self.camera_title)
        self.camera_layout.addWidget(self.camera_note)
        self.camera_status = QLabel("Kamera oqimi kutilmoqda")
        self.camera_status.setObjectName("focus")
        self.camera_layout.addWidget(self.camera_status)
        self.camera_preview = QLabel("Kamera oqimi yo'q")
        self.camera_preview.setObjectName("cameraPreview")
        self.camera_preview.setAlignment(Qt.AlignCenter)
        self.camera_preview.setMinimumHeight(420)
        self.camera_layout.addWidget(self.camera_preview, 1)
        self.camera_legend = QLabel("Yashil nuqtalar: landmarklar. Yashil doira: iris. Pastdagi yozuv: EAR, bosh og'ishi va gaze koordinatalari.")
        self.camera_legend.setObjectName("muted")
        self.camera_legend.setWordWrap(True)
        self.camera_layout.addWidget(self.camera_legend)
        self.right_stack.addWidget(self.camera_page)

        self.body_layout.addWidget(self.left_panel, 0)
        self.body_layout.addWidget(self.right_panel, 1)

    def _section(self, title: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName("subPanel")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 12, 12, 12)
        label = QLabel(title)
        label.setObjectName("sectionTitle")
        layout.addWidget(label)
        grid = QGridLayout()
        grid.setSpacing(8)
        layout.addLayout(grid)
        self._section_grids[frame] = grid
        return frame

    def _new_button(self, text: str, role: str) -> QPushButton:
        button = QPushButton(text)
        button.setProperty("uiRole", role)
        button.setProperty("rawText", text)
        button.setProperty("secondaryText", "")
        button.setCursor(Qt.PointingHandCursor)
        button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        return button

    def _mark_target(self, button: QPushButton, action: str, label: str, value: str = "") -> None:
        button.setProperty("gazeTarget", True)
        button.setProperty("gazeAction", action)
        button.setProperty("gazeLabel", label)
        button.setProperty("gazeValue", value)
        button.setCursor(Qt.PointingHandCursor)

    def _responsive_metrics(self) -> dict[str, int]:
        width = max(self.root.width(), self.width(), 960)
        height = max(self.root.height(), self.height(), 680)
        short_side = min(width, height)
        left_width = self._clamp(width * 0.28, 320, 400)
        board_width = max(width - left_width - self._clamp(short_side * 0.04, 24, 48), width // 2)
        board_columns = 3 if board_width >= 760 else 2
        support_columns = 2 if left_width >= 320 else 1

        return {
            "outer_margin": self._clamp(short_side * 0.012, 8, 16),
            "gap": self._clamp(short_side * 0.010, 6, 12),
            "tight_gap": self._clamp(short_side * 0.007, 4, 8),
            "panel_pad": self._clamp(short_side * 0.012, 8, 14),
            "subpanel_pad": self._clamp(short_side * 0.010, 8, 12),
            "button_px": self._clamp(width * 0.008, 8, 12),
            "button_py": self._clamp(height * 0.007, 6, 10),
            "message_pad": self._clamp(short_side * 0.012, 10, 16),
            "message_min_h": self._clamp(height * 0.095, 70, 102),
            "brand_font": self._clamp(short_side * 0.024, 18, 24),
            "title_font": self._clamp(short_side * 0.028, 21, 28),
            "message_font": self._clamp(short_side * 0.021, 16, 22),
            "button_font": self._clamp(short_side * 0.016, 13, 16),
            "muted_font": self._clamp(short_side * 0.014, 12, 15),
            "section_font": self._clamp(short_side * 0.014, 12, 14),
            "control_h": self._clamp(height * 0.054, 38, 48),
            "compact_h": self._clamp(height * 0.060, 42, 58),
            "nav_h": self._clamp(height * 0.068, 44, 64),
            "tile_h": self._clamp(height * 0.132, 96, 132),
            "tile_max_h": self._clamp(height * 0.170, 124, 164),
            "pill_h": self._clamp(height * 0.048, 34, 42),
            "progress_h": self._clamp(short_side * 0.008, 8, 10),
            "board_columns": board_columns,
            "support_columns": support_columns,
        }

    def _apply_style(self) -> None:
        m = self._metrics
        self.setStyleSheet(f"""
            #root {{ background: #151617; color: #f6f1e8; }}
            QLabel {{ color: #f6f1e8; }}
            #brand {{ font-size: {m["brand_font"]}px; font-weight: 800; }}
            #status, #pill, #focus {{
                min-height: {m["pill_h"]}px;
                padding: {m["button_py"]}px {m["button_px"]}px;
                border-radius: 8px;
                background: #24282c; color: #c8c0b0; font-weight: 700;
            }}
            #panel {{
                background: #1e2225; border: 1px solid #343a40;
                border-radius: 8px;
            }}
            #toolPage, #viewStack {{
                background: transparent;
            }}
            #subPanel {{
                background: #252a2e; border: 1px solid #373e44;
                border-radius: 8px;
            }}
            #supportCanvas, #boardCanvas {{
                background: transparent;
            }}
            #cameraPreview, #calibrationSurface {{
                background: #111315;
                border: 1px solid #343a40;
                border-radius: 10px;
            }}
            #message {{
                min-height: {m["message_min_h"]}px;
                padding: {m["message_pad"]}px;
                border-radius: 8px;
                background: #111315; border: 1px solid #343a40;
                font-size: {m["message_font"]}px; font-weight: 800;
            }}
            #boardTitle {{ font-size: {m["title_font"]}px; font-weight: 900; }}
            #muted {{ color: #a9a196; font-size: {m["muted_font"]}px; padding-bottom: {m["tight_gap"]}px; }}
            #sectionTitle {{ color: #a9a196; font-size: {m["section_font"]}px; font-weight: 900; }}
            QPushButton {{
                background: #30363b; color: #f6f1e8;
                border: 1px solid #4a535b; border-radius: 8px;
                padding: {m["button_py"]}px {m["button_px"]}px;
                font-size: {m["button_font"]}px; font-weight: 800;
            }}
            QPushButton:hover {{ background: #3a4249; }}
            QPushButton[uiRole="nav"] {{
                background: #272d31; color: #d6cec1;
            }}
            QPushButton[uiRole="nav"]:checked {{
                background: #f0ebe1; color: #121416; border-color: #f0ebe1;
            }}
            QPushButton[uiRole="mode"] {{
                background: #272d31; color: #d6cec1;
            }}
            QPushButton[uiRole="mode"]:checked {{
                background: #f0ebe1; color: #121416; border-color: #f0ebe1;
            }}
            QPushButton[gazeActive="true"] {{
                border: 3px solid #f5c542; background: #40391e;
            }}
            QPushButton[tone="gold"] {{ background: #efd56b; color: #34280d; }}
            QPushButton[tone="mint"] {{ background: #9cdd9e; color: #18311c; }}
            QPushButton[tone="coral"] {{ background: #ef8f78; color: #33150f; }}
            QPushButton[tone="sky"] {{ background: #9fd2f7; color: #122b39; }}
            QPushButton[tone="rose"] {{ background: #efb2c7; color: #381423; }}
            QPushButton[tone="sand"] {{ background: #ddc39a; color: #372815; }}
            QPushButton[tone="slate"] {{ background: #c7d0dc; color: #1b2431; }}
            QPushButton[tone="lime"] {{ background: #bfdd79; color: #243011; }}
            QPushButton[tone="danger"] {{ background: #ff7162; color: #2e0a09; }}
            QScrollArea {{
                background: transparent;
                border: 0;
            }}
            QScrollArea > QWidget > QWidget {{
                background: transparent;
            }}
            QScrollBar:vertical {{
                width: 10px; margin: 2px 0 2px 0;
                background: #1d2125; border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background: #56616b; min-height: 26px; border-radius: 5px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: transparent;
            }}
            QProgressBar {{
                min-height: {m["progress_h"]}px; max-height: {m["progress_h"]}px;
                border-radius: {max(4, m["progress_h"] // 2)}px;
                background: #2c3136;
            }}
            QProgressBar::chunk {{ background: #f5c542; border-radius: {max(4, m["progress_h"] // 2)}px; }}
        """)

    def _apply_responsive_layout(self, force: bool = False) -> None:
        metrics = self._responsive_metrics()
        columns_changed = (
            force
            or metrics["board_columns"] != self._board_columns
            or metrics["support_columns"] != self._support_columns
        )

        self._metrics = metrics
        self._board_columns = metrics["board_columns"]
        self._support_columns = metrics["support_columns"]

        pad = metrics["panel_pad"]
        gap = metrics["gap"]
        tight_gap = metrics["tight_gap"]
        sub_pad = metrics["subpanel_pad"]
        left_min = self._clamp(self.root.width() * 0.23, 270, 350)
        left_max = self._clamp(self.root.width() * 0.31, 340, 420)
        right_min = self._clamp(self.root.width() * 0.56, 540, 980)

        self.root_layout.setContentsMargins(metrics["outer_margin"], metrics["outer_margin"], metrics["outer_margin"], metrics["outer_margin"])
        self.root_layout.setSpacing(gap)
        self.header_layout.setSpacing(tight_gap)
        self.mode_nav.setSpacing(tight_gap)
        self.body_layout.setSpacing(gap)
        self.left_layout.setContentsMargins(pad, pad, pad, pad)
        self.left_layout.setSpacing(gap)
        self.right_layout.setContentsMargins(pad, pad, pad, pad)
        self.right_layout.setSpacing(gap)
        self.actions_layout.setSpacing(tight_gap)
        self.communication_layout.setSpacing(gap)
        self.calibration_layout.setSpacing(gap)
        self.camera_layout.setSpacing(gap)
        self.calibration_actions.setSpacing(tight_gap)
        self.page_nav.setSpacing(tight_gap)
        self.board_header.setSpacing(max(2, tight_gap // 2))
        self.board_area.setSpacing(tight_gap)
        self.grid.setHorizontalSpacing(gap)
        self.grid.setVerticalSpacing(gap)
        self.support_layout.setSpacing(gap)
        self.left_panel.setMinimumWidth(left_min)
        self.left_panel.setMaximumWidth(left_max)
        self.right_panel.setMinimumWidth(right_min)
        self.body_layout.setStretch(0, 0)
        self.body_layout.setStretch(1, 1)

        for frame, grid in self._section_grids.items():
            layout = frame.layout()
            if layout is not None:
                layout.setContentsMargins(sub_pad, sub_pad, sub_pad, sub_pad)
                layout.setSpacing(tight_gap)
            grid.setHorizontalSpacing(tight_gap)
            grid.setVerticalSpacing(tight_gap)

        self._apply_style()
        if columns_changed:
            self.render_support_panels()
            self.render_page_nav()
            self.render_board()
        self._apply_button_metrics()
        QTimer.singleShot(0, self._refresh_button_texts)

    def render_all(self) -> None:
        self.render_support_panels()
        self.render_page_nav()
        self.render_board()
        self._sync_mode_controls()
        self.update_message()

    def set_mode(self, mode: str) -> None:
        if mode not in {"communication", "calibration", "camera"}:
            return
        self._mode = mode
        self.left_panel.setVisible(mode != "calibration")
        if mode == "communication":
            self.right_stack.setCurrentWidget(self.communication_page)
        elif mode == "calibration":
            self.right_stack.setCurrentWidget(self.calibration_page)
        else:
            self.right_stack.setCurrentWidget(self.camera_page)
        self._sync_mode_controls()
        self._apply_responsive_layout()
        self.clear_gaze_target()
        QTimer.singleShot(0, self.sync_surface_size)

    def toggle_camera_mode(self) -> None:
        self.set_mode("communication" if self._mode == "camera" else "camera")

    def _sync_mode_controls(self) -> None:
        for mode, button in self.mode_buttons.items():
            checked = mode == self._mode
            if button.isChecked() != checked:
                button.setChecked(checked)
        label = "Muloqot" if self._mode == "camera" else "Kamera"
        target_mode = "communication" if self._mode == "camera" else "camera"
        self.camera_toggle_btn.setProperty("rawText", label)
        self.camera_toggle_btn.setProperty("gazeLabel", label)
        self.camera_toggle_btn.setProperty("gazeValue", target_mode)
        self.camera_toggle_btn.setText(label)
        self._sync_button_views()

    def render_support_panels(self) -> None:
        self._fill_button_grid(self.prediction_frame, self.predictions(), "suggestion")
        self._fill_button_grid(self.quick_frame, QUICK_REPLIES, "phrase")
        self._fill_button_grid(self.emergency_frame, EMERGENCY_REPLIES, "emergency", tone="danger")
        self._fill_button_grid(self.phrase_frame, PHRASE_BANK, "phrase")
        self._sync_button_views()

    def _fill_button_grid(
        self,
        frame: QFrame,
        labels: list[str],
        action: str,
        tone: str = "neutral",
    ) -> None:
        grid = self._section_grids[frame]
        self._clear_layout(grid)
        columns = self._support_columns
        for index, label in enumerate(labels):
            button = self._new_button(label, "compact")
            button.setProperty("tone", tone)
            button.setProperty("rawText", label)
            self._mark_target(button, action, label, label)
            button.clicked.connect(lambda checked=False, b=button: self.perform_action(b))
            grid.addWidget(button, index // columns, index % columns)

    def render_page_nav(self) -> None:
        self._clear_layout(self.page_nav)
        for key, page in PATIENT_PAGES.items():
            button = self._new_button(page["title"], "nav")
            button.setCheckable(True)
            button.setChecked(key == self._current_page)
            self._mark_target(button, "page", page["title"], key)
            button.clicked.connect(lambda checked=False, b=button: self.perform_action(b))
            self.page_nav.addWidget(button)
        self.page_nav.addStretch(1)
        self._sync_button_views()

    def render_board(self) -> None:
        page = PATIENT_PAGES[self._current_page]
        self.board_title.setText(page["title"])
        self.board_note.setText(page["note"])
        self._clear_layout(self.grid)
        for index, tile in enumerate(page["tiles"]):
            button = self._new_button(tile.label, "tile")
            button.setProperty("tone", tile.tone)
            button.setProperty("rawText", tile.label)
            button.setProperty("secondaryText", tile.hint)
            self._mark_target(button, "word", tile.label, tile.label)
            button.clicked.connect(lambda checked=False, b=button: self.perform_action(b))
            self.grid.addWidget(button, index // self._board_columns, index % self._board_columns)
        self._sync_button_views()

    def predictions(self) -> list[str]:
        normalized = [self._normalize(word) for word in self._words]
        text = " ".join(normalized)
        candidates = []
        if not text:
            candidates.extend(PREDICTION_MAP["__start__"])
        if len(normalized) >= 2:
            candidates.extend(PREDICTION_MAP.get(" ".join(normalized[-2:]), []))
        if normalized:
            candidates.extend(PREDICTION_MAP.get(normalized[-1], []))
        candidates.extend(PREDICTION_MAP["__start__"])

        seen = set()
        result = []
        for item in candidates:
            key = self._normalize(item)
            if key and key not in seen:
                seen.add(key)
                result.append(item)
        return result[:6]

    def perform_action(self, button: QPushButton) -> None:
        action = button.property("gazeAction")
        value = str(button.property("gazeValue") or button.property("gazeLabel") or "")
        if action == "word":
            self.append_text(value)
        elif action in {"suggestion", "phrase"}:
            self.append_text(value)
        elif action == "emergency":
            self._words = value.split()
            self.update_message()
            self.worker.speak(value)
        elif action == "page":
            self._current_page = value
            self.clear_gaze_target()
            self.render_page_nav()
            self.render_board()
        elif action == "mode":
            self.set_mode(value)
        elif action == "camera":
            self.toggle_camera_mode()
        elif action == "backspace":
            self.backspace()
        elif action == "clear":
            self.clear_message()
        elif action == "speak":
            self.speak_message()
        elif action == "calibrate":
            self.start_calibration()
        elif action == "fullscreen":
            self.toggle_fullscreen()

    def append_text(self, text: str) -> None:
        words = [part for part in text.split() if part]
        if not words:
            return
        for word in words:
            if len(self._words) >= MAX_MESSAGE_WORDS:
                break
            self._words.append(word)
        self.update_message()

    def update_message(self) -> None:
        if self._words:
            self.message_label.setText(" ".join(self._words))
        else:
            self.message_label.setText("Tanlangan so'zlar shu yerda yig'iladi")
        self.render_support_panels()

    def backspace(self) -> None:
        if self._words:
            self._words.pop()
            self.update_message()

    def clear_message(self) -> None:
        self._words.clear()
        self.update_message()

    def speak_message(self) -> None:
        if self._words:
            self.worker.speak(" ".join(self._words))

    def start_calibration(self) -> None:
        self.set_mode("calibration")
        self.sync_surface_size()
        self.worker.start_calibration(self.root.width(), self.root.height())
        self.calibration_overlay.hide()

    def handle_tracking_update(self, data: dict[str, Any]) -> None:
        state = data.get("state", "IDLE")
        self.fps_label.setText(f"{data.get('fps', 0)} FPS")
        self.status_label.setText(self._state_label(state))

        calibration = data.get("calibration") or {}
        self.calibration_surface.set_data(
            calibration,
            data.get("surface") or {},
            data.get("gaze"),
            state,
        )
        self._update_calibration_page(state, calibration)
        self._update_camera_page(data)
        if self.calibration_overlay.isVisible():
            self.calibration_overlay.hide()

        gaze = data.get("gaze")
        if gaze:
            surface = data.get("surface") or {}
            width = max(1, int(surface.get("w") or self.root.width()))
            height = max(1, int(surface.get("h") or self.root.height()))
            x = int(gaze[0] / width * self.root.width())
            y = int(gaze[1] / height * self.root.height())
            self.move_gaze_dot(x, y)
            if state == "TRACKING":
                self.update_gaze_selection(x, y)
            else:
                self.clear_gaze_target()
                if state == "NEEDS_CALIBRATION":
                    self.focus_label.setText("Nishon: ko'z kursori tayyor")
        else:
            self.gaze_dot.hide()
            self.clear_gaze_target()
            self.focus_label.setText("Nishon: -")

    def move_gaze_dot(self, x: int, y: int) -> None:
        radius_x = self.gaze_dot.width() // 2
        radius_y = self.gaze_dot.height() // 2
        self.gaze_dot.move(max(0, x - radius_x), max(0, y - radius_y))
        self.gaze_dot.show()
        self.gaze_dot.raise_()

    def update_gaze_selection(self, x: int, y: int) -> None:
        now = time.monotonic()
        if now < self._cooldown_until:
            return

        target = self.target_at(x, y)
        if target is None:
            self.focus_label.setText("Nishon: -")
            self.dwell_bar.setValue(0)
            self.clear_gaze_target()
            return

        self.focus_label.setText(f"Nishon: {target.property('gazeLabel')}")
        if target is not self._active_target:
            self.clear_gaze_target()
            self._active_target = target
            self._target_started_at = now
            self._set_gaze_active(target, True)

        progress = min(1.0, (now - self._target_started_at) / AAC_DWELL_SEC)
        self.dwell_bar.setValue(int(progress * 100))
        if progress >= 1.0:
            fired = self._active_target
            self.clear_gaze_target()
            self._cooldown_until = now + AAC_ACTION_COOLDOWN_SEC
            if fired is not None:
                self.perform_action(fired)

    def target_at(self, x: int, y: int) -> QPushButton | None:
        global_point = self.root.mapToGlobal(QPoint(x, y))
        widget = QApplication.widgetAt(global_point)
        while widget is not None and widget is not self.root:
            if isinstance(widget, QPushButton) and widget.property("gazeTarget"):
                if widget.isEnabled() and widget.isVisible():
                    return widget
            widget = widget.parentWidget()
        return None

    def clear_gaze_target(self) -> None:
        if self._active_target is not None:
            self._set_gaze_active(self._active_target, False)
        self._active_target = None
        self._target_started_at = 0.0
        self.dwell_bar.setValue(0)

    def _set_gaze_active(self, button: QPushButton, active: bool) -> None:
        button.setProperty("gazeActive", active)
        button.style().unpolish(button)
        button.style().polish(button)

    def _update_calibration_page(self, state: str, calibration: dict[str, Any]) -> None:
        if calibration.get("active"):
            current = int(calibration.get("current") or 0)
            total = int(calibration.get("total") or 0)
            progress = int(float(calibration.get("progress") or 0.0) * 100)
            self.calibration_status.setText(f"Nuqta {current}/{total}  •  {progress}%")
        elif calibration.get("done") or state == "CALIBRATION_DONE":
            self.calibration_status.setText("Kalibratsiya tayyor")
        elif state == "CALIBRATION_FAILED":
            self.calibration_status.setText("Kalibratsiya tugamadi")
        elif state == "NEEDS_CALIBRATION":
            self.calibration_status.setText("Kursor ko'rinadi, aniqlik uchun kalibratsiya qiling")
        else:
            self.calibration_status.setText(self._state_label(state))

    def _update_camera_page(self, data: dict[str, Any]) -> None:
        frame = data.get("camera_frame")
        if frame is not None:
            self._last_camera_frame = frame
            self._set_camera_frame(frame)
        state = self._state_label(data.get("state", "IDLE"))
        fps = data.get("fps", 0)
        self.camera_status.setText(f"{state}  •  {fps} FPS")

    def _set_camera_frame(self, frame) -> None:
        if frame is None:
            return
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w = rgb.shape[:2]
        image = QImage(rgb.data, w, h, rgb.strides[0], QImage.Format_RGB888).copy()
        pixmap = QPixmap.fromImage(image)
        target = self.camera_preview.size()
        if target.width() > 0 and target.height() > 0:
            pixmap = pixmap.scaled(target, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.camera_preview.setPixmap(pixmap)
        self.camera_preview.setText("")

    def show_fatal_error(self, message: str) -> None:
        self.status_label.setText(f"Xato: {message}")

    def toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
            label = "To'liq ekran"
        else:
            self.showFullScreen()
            label = "Oyna"
        self.fullscreen_btn.setProperty("rawText", label)
        self.fullscreen_btn.setProperty("gazeLabel", label)
        self.fullscreen_btn.setText(label)
        self._sync_button_views()
        QTimer.singleShot(120, self.sync_surface_size)

    def sync_surface_size(self) -> None:
        size = self.root.size()
        if size.width() < 100 or size.height() < 100:
            return
        if size != self._last_surface:
            self._last_surface = size
            self.worker.set_surface_size(size.width(), size.height())

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.calibration_overlay.setGeometry(self.root.rect())
        self._apply_responsive_layout()
        if self._last_camera_frame is not None:
            self._set_camera_frame(self._last_camera_frame)
        QTimer.singleShot(60, self.sync_surface_size)

    def closeEvent(self, event) -> None:  # noqa: N802
        self.worker.stop()
        self.worker.wait(3000)
        super().closeEvent(event)

    @staticmethod
    def _state_label(state: str) -> str:
        return {
            "TRACKING": "Kuzatuv",
            "CALIBRATING": "Kalibratsiya",
            "CALIBRATION_DONE": "Tayyor",
            "CALIBRATION_FAILED": "Kalibratsiya xato",
            "NEEDS_CALIBRATION": "Kalibratsiya kerak",
            "NO_FACE": "Yuz yo'q",
            "HEAD_AWAY": "Bosh chetda",
            "LOW_QUALITY": "Past sifat",
            "CAMERA_ERROR": "Kamera xatosi",
            "IDLE": "Kutish",
        }.get(state, state)

    @staticmethod
    def _normalize(value: str) -> str:
        return value.strip().lower().replace("`", "'").replace("’", "'")

    def _apply_button_metrics(self) -> None:
        if not self._metrics:
            return

        m = self._metrics
        for button in self.root.findChildren(QPushButton):
            role = str(button.property("uiRole") or "control")
            if role == "tile":
                button.setMinimumHeight(m["tile_h"])
                button.setMaximumHeight(m["tile_max_h"])
                button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            elif role == "mode":
                button.setMinimumHeight(m["control_h"])
                button.setMaximumHeight(m["control_h"] + 18)
                button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            elif role == "nav":
                button.setMinimumHeight(m["nav_h"])
                button.setMaximumHeight(m["nav_h"] + 24)
                button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            elif role == "compact":
                button.setMinimumHeight(m["compact_h"])
                button.setMaximumHeight(m["compact_h"] + 24)
                button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            else:
                button.setMinimumHeight(m["control_h"])
                button.setMaximumHeight(m["control_h"] + 18)
                button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def _sync_button_views(self) -> None:
        if not self._metrics:
            return
        self._apply_button_metrics()
        QTimer.singleShot(0, self._refresh_button_texts)

    def _refresh_button_texts(self) -> None:
        if not self._metrics:
            return

        for button in self.root.findChildren(QPushButton):
            primary = str(button.property("rawText") or button.text() or "").strip()
            secondary = str(button.property("secondaryText") or "").strip()
            if not primary and not secondary:
                continue

            role = str(button.property("uiRole") or "control")
            current_width = max(72, button.contentsRect().width() - (self._metrics["button_px"] * 2))
            nav_width = max(
                110,
                (
                    max(self.right_panel.width(), self.right_panel.minimumWidth())
                    - self._metrics["gap"] * max(0, len(PATIENT_PAGES) - 1)
                    - self._metrics["button_px"] * 2 * len(PATIENT_PAGES)
                ) // max(1, len(PATIENT_PAGES)),
            )
            compact_width = max(
                96,
                ((max(self.left_panel.width(), self.left_panel.minimumWidth()) - self._metrics["gap"] * max(0, self._support_columns - 1)) // max(1, self._support_columns))
                - self._metrics["button_px"] * 2
                - 12,
            )
            mode_width = max(
                108,
                (
                    max(self.root.width(), self.width())
                    - self._metrics["outer_margin"] * 2
                    - self._metrics["gap"] * max(0, len(self.mode_buttons) - 1)
                ) // max(1, len(self.mode_buttons))
                - self._metrics["button_px"] * 2
                - 12,
            )
            tile_width = max(
                120,
                ((max(self.right_panel.width(), self.right_panel.minimumWidth()) - self._metrics["gap"] * max(0, self._board_columns - 1)) // max(1, self._board_columns))
                - self._metrics["button_px"] * 2
                - 12,
            )

            if role == "mode":
                content_width = min(current_width, mode_width)
            elif role == "nav":
                content_width = min(current_width, nav_width)
            elif role == "tile":
                content_width = min(current_width, tile_width)
            elif role == "compact":
                content_width = min(current_width, compact_width)
            else:
                content_width = min(current_width, max(110, self._clamp(self.width() * 0.16, 110, 180)))

            lines = self._wrap_text(primary, button.fontMetrics(), content_width)
            if secondary:
                lines.extend(self._wrap_text(secondary, button.fontMetrics(), content_width))
            button.setText("\n".join(lines))
            line_count = max(1, len(lines))
            line_step = max(12, button.fontMetrics().lineSpacing())
            if role == "tile":
                height = min(
                    self._metrics["tile_max_h"],
                    max(self._metrics["tile_h"], self._metrics["tile_h"] + max(0, line_count - 2) * line_step),
                )
            elif role == "mode":
                height = min(
                    self._metrics["control_h"] + 18,
                    self._metrics["control_h"] + max(0, line_count - 1) * line_step,
                )
            elif role == "nav":
                height = min(self._metrics["nav_h"] + 24, self._metrics["nav_h"] + max(0, line_count - 1) * line_step)
            elif role == "compact":
                height = min(
                    self._metrics["compact_h"] + 24,
                    self._metrics["compact_h"] + max(0, line_count - 1) * line_step,
                )
            else:
                height = min(
                    self._metrics["control_h"] + 18,
                    self._metrics["control_h"] + max(0, line_count - 1) * line_step,
                )
            button.setFixedHeight(height)

    def _wrap_text(self, text: str, metrics, max_width: int) -> list[str]:
        clean = " ".join(text.replace("\n", " ").split())
        if not clean:
            return []

        words = clean.split(" ")
        lines: list[str] = []
        current = ""
        for word in words:
            candidate = word if not current else f"{current} {word}"
            if current and metrics.horizontalAdvance(candidate) > max_width:
                lines.append(current)
                current = word
                if metrics.horizontalAdvance(current) > max_width:
                    parts = self._split_long_word(current, metrics, max_width)
                    lines.extend(parts[:-1])
                    current = parts[-1]
            else:
                current = candidate

        if current:
            lines.append(current)
        return lines

    def _split_long_word(self, word: str, metrics, max_width: int) -> list[str]:
        parts: list[str] = []
        current = ""
        for char in word:
            candidate = current + char
            if current and metrics.horizontalAdvance(candidate) > max_width:
                parts.append(current)
                current = char
            else:
                current = candidate
        if current:
            parts.append(current)
        return parts or [word]

    @staticmethod
    def _clamp(value: float, low: int, high: int) -> int:
        return max(low, min(high, int(round(value))))

    @staticmethod
    def _clear_layout(layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
            elif child_layout is not None:
                MainWindow._clear_layout(child_layout)


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--version", action="store_true")
    args, qt_args = parser.parse_known_args(sys.argv[1:])

    if args.version:
        print(APP_VERSION)
        return 0

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if args.self_check:
        return run_self_check()

    ensure_runtime_dirs()
    app = QApplication([sys.argv[0], *qt_args])
    app.setApplicationName(APP_NAME)
    window = MainWindow()
    window.show()
    return app.exec()


def run_self_check() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    ensure_runtime_dirs()

    try:
        import edge_tts
        import mediapipe as mp
    except Exception as exc:
        print(f"SELF-CHECK FAIL: import error: {exc}")
        return 1

    app = QApplication([APP_NAME, "-platform", "offscreen"])
    app.setApplicationName(APP_NAME)

    errors: list[str] = []
    warnings: list[str] = []
    tracker: FaceTracker | None = None
    strict_tracker_check = str(os.getenv("GAZESPEAK_SELF_CHECK_TRACKER", "")).strip().lower() in {"1", "true", "yes", "on"}

    model_path = Path(runtime_snapshot()["active_model"])
    if not model_path.exists():
        errors.append(f"model missing: {model_path}")

    try:
        tracker = FaceTracker(enable_blendshapes=False)
    except Exception as exc:
        message = f"FaceTracker init failed: {exc}"
        if strict_tracker_check:
            errors.append(message)
        else:
            warnings.append(message)

    try:
        import pyttsx3  # noqa: F401
    except Exception as exc:
        warnings.append(f"pyttsx3 unavailable: {exc}")

    print(f"SELF-CHECK APP={APP_NAME} VERSION={APP_VERSION}")
    print(f"SELF-CHECK OPENCV={cv2.__version__}")
    print(f"SELF-CHECK MEDIAPIPE={mp.__version__}")
    print(f"SELF-CHECK EDGE_TTS={getattr(edge_tts, '__version__', 'unknown')}")
    for key, value in runtime_snapshot().items():
        print(f"SELF-CHECK PATH {key}={value}")
    for warning in warnings:
        print(f"SELF-CHECK WARN: {warning}")

    if tracker is not None:
        tracker.close()
    app.quit()

    if errors:
        for item in errors:
            print(f"SELF-CHECK FAIL: {item}")
        return 1

    print("SELF-CHECK OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
