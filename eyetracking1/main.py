"""
3-4 qadam: calibration + zones + output polish.

Ishga tushirish:
    python3 main.py

Tugmalar:
    Q / ESC  - chiqish
    C        - qayta kalibrasiya
    D        - debug landmark on/off
    M        - cursor harakatini on/off
    R        - zona timer reset
"""

import logging
import sys
import time
from logging.handlers import RotatingFileHandler

import cv2
import numpy as np

from camera import CameraManager, CameraError
from calibration import CalibrationManager
from face_tracker import FaceTracker
from gaze_mapper import GazeMapper
from mouse_controller import MouseController
from notifier import Notifier
from overlay_ui import OverlayUI
from state_machine import State, StateMachine
from tts_engine import TTSEngine
from zone_analyzer import ZoneAnalyzer
from settings import (
    CAMERA_HEIGHT,
    CAMERA_READ_FAIL_LIMIT,
    CAMERA_WIDTH,
    CURSOR_ENABLED_DEFAULT,
    DEBUG_MODE,
    LOG_FILE,
    LOG_BACKUP_COUNT,
    LOG_MAX_BYTES,
    OVERLAY_WINDOW_NAME,
    PREVIEW_MIRROR,
    ZONE_FIRED_BANNER_SEC,
)


logging.basicConfig(
    level=logging.DEBUG if DEBUG_MODE else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        RotatingFileHandler(
            LOG_FILE,
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger(__name__)


def _draw_shortcuts(frame, cursor_enabled: bool, debug: bool) -> None:
    h = frame.shape[0]
    status = "Pointer ON" if cursor_enabled else "AAC ON"
    dbg = "Debug ON" if debug else "Debug OFF"
    cv2.putText(
        frame,
        f"Q exit  C calib  R reset  M {status}  D {dbg}",
        (12, h - 16),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (160, 160, 160),
        1,
    )


def _safe_cleanup(name: str, func) -> None:
    try:
        func()
    except BaseException as exc:
        logger.warning("%s cleanup xatosi: %s", name, exc)


def _set_window_mode(calibrating: bool) -> None:
    cv2.namedWindow(OVERLAY_WINDOW_NAME, cv2.WINDOW_NORMAL)
    if calibrating:
        cv2.setWindowProperty(
            OVERLAY_WINDOW_NAME,
            cv2.WND_PROP_FULLSCREEN,
            cv2.WINDOW_FULLSCREEN,
        )
    else:
        cv2.setWindowProperty(
            OVERLAY_WINDOW_NAME,
            cv2.WND_PROP_FULLSCREEN,
            cv2.WINDOW_NORMAL,
        )
        cv2.resizeWindow(OVERLAY_WINDOW_NAME, CAMERA_WIDTH, CAMERA_HEIGHT)


def main() -> int:
    logger.info("=" * 50)
    logger.info("GazeSpeak step 3-4 ishga tushdi.")

    camera = CameraManager()
    tracker = None
    empty_frames = 0
    mouse = None
    tts = None
    notifier = None

    try:
        tracker = FaceTracker()
        mapper = GazeMapper()
        calib_mgr = CalibrationManager(mapper.screen_w, mapper.screen_h)
        mouse = MouseController()
        zones = ZoneAnalyzer(mapper.screen_w, mapper.screen_h)
        overlay = OverlayUI()
        overlay.set_screen_size(mapper.screen_w, mapper.screen_h)
        state_m = StateMachine()
        tts = TTSEngine()
        notifier = Notifier(tts)
        state_m.transition(State.INIT)

        saved_model = CalibrationManager.load_saved(mapper.screen_w, mapper.screen_h)
        has_valid_calibration = saved_model is not None and mapper.set_calibration(saved_model)

        camera.open()

        if has_valid_calibration:
            state_m.transition(State.TRACKING)
            _set_window_mode(calibrating=False)
            overlay.show_banner("Kalibrasiya yuklandi", 1.5)
        else:
            state_m.transition(State.CALIBRATING)
            calib_mgr.start()
            _set_window_mode(calibrating=True)
            overlay.show_banner("Kalibrasiya boshlandi", 1.5)

        debug = DEBUG_MODE
        cursor_enabled = CURSOR_ENABLED_DEFAULT
        gaze_screen = None
        zone_idx = -1
        zone_progress = 0.0
        dwell_progress = 0.0
        zone_fired_until = 0.0

        while True:
            frame = camera.read()
            if frame is None:
                empty_frames += 1
                if empty_frames >= CAMERA_READ_FAIL_LIMIT:
                    state_m.transition(State.CAM_ERROR)
                    raise CameraError(
                        "Kamera frame bermayapti. Ruxsatlarni va boshqa camera "
                        "ishlatayotgan dasturlarni tekshiring."
                    )
                time.sleep(0.01)
                continue

            empty_frames = 0
            if PREVIEW_MIRROR:
                frame = cv2.flip(frame, 1)

            face_data = tracker.process(frame)
            iris_found = face_data.left_iris.found or face_data.right_iris.found
            gaze_ready = (
                face_data.found
                and iris_found
                and not camera.is_low_light()
                and not face_data.head_away
            )

            if debug and face_data.found:
                tracker.draw_debug(frame, face_data)

            if state_m.state == State.CALIBRATING:
                gaze_screen = None
                zone_idx = -1
                zone_progress = 0.0
                dwell_progress = 0.0
                mouse.reset_dwell()
                zones.reset_zone()
                done = calib_mgr.update(face_data.gaze_norm if gaze_ready else None)
                if done and calib_mgr.get_model() is not None:
                    if mapper.set_calibration(calib_mgr.get_model()):
                        state_m.transition(State.TRACKING)
                        _set_window_mode(calibrating=False)
                        overlay.show_banner("Kalibrasiya tugadi!", 2.0)
                        tts.speak("Kalibrasiya tugadi")
                    else:
                        calib_mgr.start()
                        overlay.show_banner("Kalibrasiya yaroqsiz, qayta urinib ko'ring", 2.0)
                calib_canvas = np.zeros((mapper.screen_h, mapper.screen_w, 3), dtype=np.uint8)
                frame = calib_mgr.draw(calib_canvas, preview=frame)
            else:
                state_m.update_from_frame(
                    face_found=face_data.found,
                    iris_found=iris_found,
                    low_light=camera.is_low_light(),
                    cam_ok=True,
                    head_away=face_data.head_away,
                )

                if state_m.state == State.ZONE_FIRED and time.time() >= zone_fired_until:
                    state_m.transition(State.TRACKING)

                if state_m.is_tracking and gaze_ready:
                    sx, sy = mapper.map(face_data.gaze_norm)
                    gaze_screen = (sx, sy)
                    blink = tracker.blink_detector

                    if cursor_enabled:
                        zones.reset_zone()
                        zone_idx = -1
                        zone_progress = 0.0
                        if state_m.state in (State.DWELL_ZONE, State.ZONE_FIRED):
                            state_m.transition(State.TRACKING)

                        if mapper.has_moved(sx, sy):
                            mouse.move(sx, sy)

                        dwell_progress = mouse.update_dwell(sx, sy)

                        action_fired = False
                        if blink.double_blink:
                            action_fired = mouse.blink_click(double=True)
                            if action_fired:
                                overlay.show_banner("Double click", 1.0)
                        elif blink.single_blink:
                            action_fired = mouse.blink_click(double=False)
                        elif blink.long_blink:
                            action_fired = mouse.right_click()
                            if action_fired:
                                overlay.show_banner("Right click", 1.0)

                        if action_fired:
                            mouse.suppress_dwell(sx, sy)
                            dwell_progress = 0.0

                    else:
                        dwell_progress = 0.0
                        mouse.reset_dwell()

                        zone_result = zones.update(sx, sy)
                        zone_idx, zone_progress = zones.get_progress(sx, sy)

                        if zone_result:
                            state_m.transition(State.ZONE_FIRED)
                            zone_fired_until = time.time() + ZONE_FIRED_BANNER_SEC
                            notifier.notify(zone_result)
                            overlay.show_banner(zone_result["message"], 4.0)
                        elif zone_idx >= 0 and zone_progress > 0.0:
                            if state_m.state == State.TRACKING:
                                state_m.transition(State.DWELL_ZONE)
                        elif state_m.state == State.DWELL_ZONE:
                            state_m.transition(State.TRACKING)
                else:
                    gaze_screen = None
                    zone_idx = -1
                    zone_progress = 0.0
                    dwell_progress = 0.0
                    zones.reset_zone()
                    mouse.reset_dwell()

            frame = overlay.draw(
                frame,
                state=state_m.state,
                gaze_screen=gaze_screen,
                zone_idx=zone_idx,
                zone_progress=zone_progress,
                fps=camera.fps,
                brightness=camera.brightness,
                dwell_progress=dwell_progress,
                show_zones=not cursor_enabled,
            )
            _draw_shortcuts(frame, cursor_enabled, debug)
            cv2.imshow(OVERLAY_WINDOW_NAME, frame)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                logger.info("Foydalanuvchi ilovani yopdi.")
                return 0
            if key == ord("c"):
                logger.info("Qayta kalibrasiya boshlandi.")
                state_m.transition(State.CALIBRATING)
                calib_mgr.start()
                _set_window_mode(calibrating=True)
                gaze_screen = None
                zone_idx = -1
                zone_progress = 0.0
                dwell_progress = 0.0
                mouse.reset_dwell()
                zones.reset_zone()
                overlay.show_banner("Qayta kalibrasiya", 1.5)
            if key == ord("d"):
                debug = not debug
                logger.info("Debug overlay: %s", debug)
            if key == ord("m"):
                cursor_enabled = not cursor_enabled
                mouse.reset_dwell()
                zones.reset_zone()
                zone_idx = -1
                zone_progress = 0.0
                dwell_progress = 0.0
                if state_m.state in (State.DWELL_ZONE, State.ZONE_FIRED):
                    state_m.transition(State.TRACKING)
                logger.info("Pointer mode: %s", cursor_enabled)
                overlay.show_banner(
                    "Pointer ON" if cursor_enabled else "AAC mode",
                    1.0,
                )
            if key == ord("r"):
                zones.reset_zone()
                zone_idx = -1
                zone_progress = 0.0
                overlay.show_banner("Zona reset", 1.0)

    except CameraError as exc:
        logger.error(str(exc))
        print(f"\nXATO: {exc}\n")
        return 1
    except KeyboardInterrupt:
        logger.info("Foydalanuvchi Ctrl+C bilan to'xtatdi.")
        return 130
    except Exception as exc:
        logger.error("Ilova xatosi: %s", exc)
        print(f"\nXATO: {exc}\n")
        return 1
    finally:
        _safe_cleanup("camera", camera.close)
        if tracker is not None:
            _safe_cleanup("tracker", tracker.close)
        if notifier is not None:
            _safe_cleanup("notifier", notifier.stop)
        if tts is not None:
            _safe_cleanup("tts", tts.stop)
        _safe_cleanup("opencv", cv2.destroyAllWindows)
        logger.info("GazeSpeak step 3-4 to'xtatildi.")


if __name__ == "__main__":
    raise SystemExit(main())
